package devbuddy.scripts.week02;

import devbuddy.config.AppConfig;
import devbuddy.schemas.Json;
import devbuddy.schemas.JsonSchemas;
import devbuddy.schemas.ServiceReadinessReport;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

/**
 * Week 2 — Demo 5: Agentic Retry (Self-Correction Loop).
 *
 * <p>Even with strict schemas, LLMs can violate business logic (cross-field rules).
 * Instead of failing or doing a "blind retry", we catch the validation error and feed
 * it back to the LLM so it fixes its own mistake.</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo05AgenticRetry}</p>
 */
public class Demo05AgenticRetry {

    private static final String TRAP_PROMPT = """
            You are evaluating 'auth-service' v2.1.0.
            The build is passing and healthy (last deploy: 2024-10-01T12:00:00Z).
            However, there is an active incident: 'DB connection pooling exhausted'.

            CRITICAL INSTRUCTIONS:
            1. You MUST set verdict.ready=true because the build is passing.
            2. You MUST also list the DB incident in the verdict.blockers array.
            3. You MUST include at least one item in the 'evidence' array so confidence can be high.""";

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            ChatClient chatClient = ctx.getBean(ChatClient.class);
            String model = ctx.getBean("modelName", String.class);

            var options = OpenAiChatOptions.builder()
                    .model(model)
                    .temperature(0.2)
                    .responseFormat(JsonSchemas.responseFormat(
                            "service_readiness_report", JsonSchemas.SERVICE_READINESS_REPORT))
                    .build();

            System.out.println("=".repeat(75));
            System.out.println("  DEMO 5: Agentic Retry (Self-Correction)");
            System.out.println("=".repeat(75));
            System.out.println("  Model: " + model);
            System.out.println();

            StringBuilder userPrompt = new StringBuilder(TRAP_PROMPT);
            int maxRetries = 3;

            for (int attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    System.out.println("  Attempt " + attempt + " / " + maxRetries + "...");
                    ChatResponse response = chatClient.prompt()
                            .system("You are a strict SRE. Follow instructions exactly.")
                            .user(userPrompt.toString())
                            .options(options)
                            .call()
                            .chatResponse();

                    ServiceReadinessReport result = Json.parse(
                            Json.stripMarkdownFences(response.getResult().getOutput().getText()),
                            ServiceReadinessReport.class);

                    System.out.println();
                    System.out.println("  ✅ SUCCESS! The LLM produced valid output:");
                    System.out.println("     ready:    " + result.verdict().ready());
                    System.out.println("     blockers: " + result.verdict().blockers());

                    if (attempt > 1) {
                        System.out.println();
                        System.out.println("  By giving the LLM the error, it acted as its own debugger.");
                    } else {
                        System.out.println();
                        System.out.println("  ❌ WAIT. The LLM passed on the first try? The trap failed.");
                    }
                    return;
                } catch (IllegalArgumentException e) {
                    String errorMsg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                    System.out.println("  ❌ Caught validation error:");
                    System.out.println("     " + errorMsg);

                    if (attempt < maxRetries) {
                        System.out.println("  -> Feeding error back to the LLM for self-correction...");
                        System.out.println();
                        userPrompt.append("\n\nYour previous output failed schema validation with this error:\n")
                                .append(errorMsg)
                                .append("\n\nPlease analyze the error and output a corrected JSON.");
                    } else {
                        System.out.println();
                        System.out.println("  ❌ Max retries reached. The LLM could not fix the error.");
                    }
                }
            }
        }
    }
}
