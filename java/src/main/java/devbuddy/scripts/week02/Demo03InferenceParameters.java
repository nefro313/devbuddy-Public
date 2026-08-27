package devbuddy.scripts.week02;

import devbuddy.config.AppConfig;
import devbuddy.schemas.BuildCheck;
import devbuddy.service.SchemasService;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

/**
 * Week 2 — Demo 3: Inference Parameters (temperature + max_tokens).
 *
 * <p>Same PR. Same schema. Vary temperature and maxTokens to show what changes
 * (judgment) and what holds (validity — the contract).</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo03InferenceParameters}</p>
 */
public class Demo03InferenceParameters {

    private static final String PR_TITLE = "Consolidate error handling across user profile module";
    private static final String PR_DIFF = """
            Moved duplicate try/except blocks from 6 profile endpoints into a shared
            error_handler.py decorator. No behavior changes — same errors, same messages.
            Added unit tests for the new decorator. This is prep work for the v2 profiles API.
            Files: src/profiles/error_handler.py (+80, new), src/profiles/views.py (-120),
                   tests/test_error_handler.py (+45, new)""";

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            SchemasService schemas = ctx.getBean(SchemasService.class);
            String model = ctx.getBean("modelName", String.class);

            System.out.println("=".repeat(65));
            System.out.println("  Demo 3: Inference Parameters — Temp, Max Tokens");
            System.out.println("=".repeat(65));
            System.out.println("  Model: " + model);
            System.out.println();

            // ── Part 1: temperature — determinism vs. judgment ──
            System.out.println("-".repeat(65));
            System.out.println("  PART 1: Temperature — determinism vs. judgment");
            System.out.println("-".repeat(65));
            System.out.println();

            System.out.println("  temp=0.0 (deterministic) — same input, run twice:");
            for (int i = 1; i <= 2; i++) {
                BuildCheck r = schemas.analyzePr(PR_TITLE, PR_DIFF, 0.0, 512);
                System.out.printf("    run %d: severity=%s  summary=\"%s\"%n",
                        i, r.severity().value(), r.summary());
            }
            System.out.println("    → same verdict, consistent phrasing.");
            System.out.println();

            System.out.println("  temp=1.0 (creative) — same input, run twice:");
            for (int i = 1; i <= 2; i++) {
                BuildCheck r = schemas.analyzePr(PR_TITLE, PR_DIFF, 1.0, 512);
                System.out.printf("    run %d: severity=%s  summary=\"%s\"%n",
                        i, r.severity().value(), r.summary());
            }
            System.out.println("    → same verdict, but the phrasing drifts more.");
            System.out.println();

            System.out.println("  Key: every run returned a VALID BuildCheck — the schema guarantees");
            System.out.println("  validity at ANY temperature. Temperature only nudges how much the");
            System.out.println("  phrasing varies; on short fields that effect is subtle. temp=0 is a");
            System.out.println("  reproducibility choice (tests, CI, caching), not a correctness rule.");
            System.out.println();

            // ── Part 2: max_tokens — truncation kills structured output ──
            System.out.println("-".repeat(65));
            System.out.println("  PART 2: Max Tokens — cost guard or truncation risk?");
            System.out.println("-".repeat(65));
            System.out.println();

            for (int limit : new int[]{512, 200, 50, 15, 8}) {
                try {
                    BuildCheck r = schemas.analyzePr(PR_TITLE, PR_DIFF, 0.0, limit);
                    System.out.printf("  maxTokens=%3d: ✓ %s%n", limit, r.severity().value());
                } catch (Exception e) {
                    System.out.printf("  maxTokens=%3d: ✗ %s%n", limit,
                            e.getMessage() == null ? e.getClass().getSimpleName()
                                    : e.getMessage().replace("\n", " "));
                }
            }
            System.out.println();
            System.out.println("  maxTokens=512 → safe. maxTokens=200 may still fail depending on model/provider.");
            System.out.println("  maxTokens=8 → truncated, validation fails.");
            System.out.println("  Rule: maxTokens must fit your schema. Measure, don't guess.");
            System.out.println();
            System.out.println("=".repeat(65));
            System.out.println("  Inference parameters are architectural decisions, not knobs.");
            System.out.println("=".repeat(65));
        }
    }
}
