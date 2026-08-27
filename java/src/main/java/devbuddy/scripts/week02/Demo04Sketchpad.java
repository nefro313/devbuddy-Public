package devbuddy.scripts.week02;

import devbuddy.config.AppConfig;
import devbuddy.schemas.Json;
import devbuddy.schemas.JsonSchemas;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

/**
 * Week 2 — Demo 4: The &lt;Sketchpad&gt; Pattern (Chain-of-Thought in Structured Outputs).
 *
 * <p>Modern models are smart enough to catch obvious bugs even without time to think.
 * But a direct verdict is a BLACK BOX — if it's wrong, you have no idea why. Adding a
 * {@code thought_process} string as the VERY FIRST field forces the LLM to emit its
 * step-by-step reasoning, giving you an AUDIT TRAIL for debugging and evals. It's not
 * just about accuracy; it's about observability.</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo04Sketchpad}</p>
 */
public class Demo04Sketchpad {

    public record DirectVerdict(String severity, String summary) {}

    public record ReasonedVerdict(String thoughtProcess, String severity, String summary) {}

    private static final String DIRECT_VERDICT_SCHEMA = """
            {
              "type": "object",
              "properties": {
                "severity": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
                "summary": { "type": "string" }
              },
              "required": ["severity", "summary"],
              "additionalProperties": false
            }""";

    private static final String REASONED_VERDICT_SCHEMA = """
            {
              "type": "object",
              "properties": {
                "thought_process": { "type": "string" },
                "severity": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
                "summary": { "type": "string" }
              },
              "required": ["thought_process", "severity", "summary"],
              "additionalProperties": false
            }""";

    // A tricky PR that looks like a simple feature addition (adding a shipping fee),
    // but contains a subtle revenue-loss math bug (subtracting instead of adding).
    private static final String TRICKY_PR_DIFF = """
            PR Title: Add shipping fee for small orders
            Description: We are losing margin on small orders. This PR adds a $5 shipping fee to orders under $50.

            Files: src/checkout.py

            diff --git a/src/checkout.py b/src/checkout.py
            @@ -12,6 +12,10 @@
             def calculate_final_total(order):
                 total = order.subtotal

            +    # Add $5 shipping fee for small orders
            +    if total < 50.00:
            +        total -= 5.00

                 if order.has_vip_pass:
                     total *= 0.90

                 return total""";

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            ChatClient chatClient = ctx.getBean(ChatClient.class);
            String model = ctx.getBean("modelName", String.class);

            System.out.println("=".repeat(75));
            System.out.println("  DEMO 4: The <Sketchpad> Pattern");
            System.out.println("=".repeat(75));
            System.out.println("  Model: " + model);

            System.out.println();
            System.out.println("  APPROACH A: Direct Verdict (No Sketchpad)");
            System.out.println("  The model must decide 'severity' on token #1.");
            System.out.println("  " + "-".repeat(55));

            DirectVerdict r1 = run(chatClient, model, "direct_verdict", DIRECT_VERDICT_SCHEMA, DirectVerdict.class);
            System.out.println("  Severity: " + r1.severity().toUpperCase());
            System.out.println("  Summary:  " + r1.summary());
            System.out.println("  (The model likely caught the bug. But if it was wrong, we'd have ZERO visibility into why.)");

            System.out.println();
            System.out.println("=".repeat(75));

            System.out.println();
            System.out.println("  APPROACH B: Reasoned Verdict (With Sketchpad)");
            System.out.println("  The model generates 'thought_process' first, conditioning its final verdict.");
            System.out.println("  " + "-".repeat(55));

            ReasonedVerdict r2 = run(chatClient, model, "reasoned_verdict", REASONED_VERDICT_SCHEMA, ReasonedVerdict.class);
            System.out.println("  Thought Process:");
            for (String line : r2.thoughtProcess().split("\\. ")) {
                if (!line.isBlank()) {
                    System.out.println("    - " + line.trim());
                }
            }
            System.out.println();
            System.out.println("  Severity: " + r2.severity().toUpperCase());
            System.out.println("  Summary:  " + r2.summary());
            System.out.println();
            System.out.println("  (Both models got it right, but this one gave us an AUDIT TRAIL. This is how you bridge the 'valid vs. right' gap!)");
            System.out.println("=".repeat(75));
        }
    }

    private static <T> T run(ChatClient chatClient, String model, String name, String schema, Class<T> type) {
        var options = OpenAiChatOptions.builder()
                .model(model)
                .temperature(0.4)
                .responseFormat(JsonSchemas.responseFormat(name, schema))
                .build();
        ChatResponse response = chatClient.prompt()
                .system("You are a strict code reviewer. Analyze the PR diff for bugs or logic flaws.")
                .user(TRICKY_PR_DIFF)
                .options(options)
                .call()
                .chatResponse();
        return Json.parse(Json.stripMarkdownFences(response.getResult().getOutput().getText()), type);
    }
}
