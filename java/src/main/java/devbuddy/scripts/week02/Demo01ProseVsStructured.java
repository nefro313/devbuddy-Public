package devbuddy.scripts.week02;

import devbuddy.config.AppConfig;
import devbuddy.schemas.BuildCheck;
import devbuddy.schemas.Json;
import devbuddy.service.SchemasService;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

/**
 * Week 2 — Demo 1: Unstructured request → crash, then Schema → guaranteed.
 *
 * <p>The moderator's "Demo 1": ask the LLM for the fields you want — but with
 * NO schema. The model gives you those fields back as prose, so parsing crashes.
 * Then add a schema constraint (analyzePr) and get a typed record that ALWAYS
 * parses. A request is not a contract.</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo01ProseVsStructured}</p>
 */
public class Demo01ProseVsStructured {

    private static final String PR_TITLE = "Fix login redirect loop in auth-service";
    private static final String PR_DIFF = """
            Changed session token validation in src/auth.py lines 42-58.
            Previously expired tokens caused infinite redirect for 15% of users.
            Now returns 401 with clear error. No DB changes. Rollback: revert commit.
            Files: src/auth.py, tests/test_auth.py""";

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            ChatClient chatClient = ctx.getBean(ChatClient.class);
            SchemasService schemas = ctx.getBean(SchemasService.class);
            String model = ctx.getBean("modelName", String.class);

            System.out.println("=".repeat(70));
            System.out.println("  Demo 1: Prose → crash, then Schema → success");
            System.out.println("=".repeat(70));
            System.out.println("  Model: " + model);
            System.out.println();
            System.out.println("  INPUT: " + PR_TITLE);
            for (String line : PR_DIFF.split("\n")) {
                System.out.println("         " + line);
            }
            System.out.println();

            // ── Step 1: ask for the fields (no schema) → prose ──────
            System.out.println("-".repeat(70));
            System.out.println("  STEP 1: ask for the fields (no schema) → prose");
            System.out.println("-".repeat(70));
            System.out.println();

            String raw = chatClient.prompt()
                    .user("Analyze this PR and return its severity, a one-sentence summary, "
                            + "and the affected files.\n\n"
                            + "PR Title: " + PR_TITLE + "\n\nDiff:\n" + PR_DIFF)
                    .call()
                    .chatResponse().getResult().getOutput().getText();

            System.out.println("  Raw response:");
            for (String line : raw.strip().split("\n")) {
                System.out.println("  | " + line);
            }
            System.out.println();

            // ── Step 2: Json.parse → crash ────────────────────────
            System.out.println("-".repeat(70));
            System.out.println("  STEP 2: Json.parse(raw) → crash");
            System.out.println("-".repeat(70));
            System.out.println();

            try {
                BuildCheck parsed = Json.parse(raw, BuildCheck.class);
                System.out.println("  ✅ parsed unexpectedly: " + parsed.project());
            } catch (RuntimeException e) {
                System.out.println("  ❌ CRASHED: " + e.getMessage());
                System.out.println();
                System.out.println("  You asked for the severity, summary, and affected files.");
                System.out.println("  The model gave them to you — as prose. With no schema,");
                System.out.println("  the model picks the format, and it picked prose.");
                System.out.println("  Free text breaks pipelines. Let's fix it.");
            }
            System.out.println();

            // ── Step 3: schema constraint → typed record ──────────
            System.out.println("-".repeat(70));
            System.out.println("  STEP 3: analyzePr (schema-constrained) → typed record");
            System.out.println("-".repeat(70));
            System.out.println();

            BuildCheck result = schemas.analyzePr(PR_TITLE, PR_DIFF, 0.0, null);

            System.out.println("  type: " + result.getClass().getSimpleName() + "  ← typed record, not prose!");
            System.out.println();
            System.out.println("  " + Json.toJson(result).replace("\n", "\n  "));
            System.out.println();

            System.out.println("=".repeat(70));
            System.out.println("  The LLM is now a typed function.");
            System.out.println("  Input → BuildCheck. Your code consumes it directly.");
            System.out.println("=".repeat(70));
        }
    }
}
