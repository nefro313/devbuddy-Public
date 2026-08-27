package devbuddy.scripts.week02;

import devbuddy.config.AppConfig;
import devbuddy.schemas.BuildCheck;
import devbuddy.service.SchemasService;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Week 2 — Demo 6: Prompt Engineering + Promptfoo Evaluation.
 *
 * <p>Same PR, same schema, different prompt strategies:</p>
 * <ul>
 *   <li>zero-shot</li>
 *   <li>few-shot</li>
 *   <li>chain-of-thought</li>
 * </ul>
 *
 * <p>Run: mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo06PromptEngineering</p>
 */
public class Demo06PromptEngineering {

    private static final String PR_TITLE = "Fix login redirect loop in auth-service";
    private static final String PR_DIFF = """
            Updated session token validation in auth.py. Expired tokens now return 401 instead of looping.
            Files: src/auth.py, tests/test_auth.py""";

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            SchemasService schemas = ctx.getBean(SchemasService.class);
            String model = ctx.getBean("modelName", String.class);

            var promptDir = Path.of("../../shared/prompts").toAbsolutePath().normalize();
            System.out.println("=".repeat(80));
            System.out.println("  Demo 6: Prompt Engineering + Promptfoo Evaluation");
            System.out.println("=".repeat(80));
            System.out.println("  Model: " + model);
            System.out.println("  Task: same PR, same schema, different prompt strategy");
            System.out.println();

            for (var entry : new String[]{"zero-shot", "few-shot", "chain-of-thought"}) {
                String template = readPrompt(promptDir, entry);
                try {
                    BuildCheck result = schemas.analyzePrWithPrompt(PR_TITLE, PR_DIFF, template, 0.0, 512);
                    System.out.println("[" + entry + "]");
                    System.out.println("  project: " + result.project());
                    System.out.println("  severity: " + result.severity().value());
                    System.out.println("  summary: " + result.summary());
                    System.out.println("  affected_files: " + result.affectedFiles());
                } catch (Exception e) {
                    System.out.println("[" + entry + "] ERROR: " + e.getMessage());
                }
            }

            System.out.println();
            System.out.println("-".repeat(80));
            System.out.println("  Why this matters:");
            System.out.println("  - zero-shot is the shortest, but often least robust");
            System.out.println("  - few-shot adds examples and improves format adherence");
            System.out.println("  - chain-of-thought may improve reasoning but can be verbose");
            System.out.println("  Promptfoo helps compare these systematically across models and prompts.");
            System.out.println("-".repeat(80));
        }
    }

    private static String readPrompt(Path promptDir, String name) {
        try {
            return Files.readString(promptDir.resolve(name + ".txt"), StandardCharsets.UTF_8).trim();
        } catch (IOException e) {
            throw new IllegalStateException("Unable to read prompt file: " + name, e);
        }
    }
}
