package devbuddy;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import devbuddy.config.AppConfig;
import devbuddy.cost.CostTracker;
import org.junit.jupiter.api.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.time.Duration;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.*;

/**
 * DevBuddy Integration Test — Week 0 (Java)
 *
 * <p>Validates the full setup end-to-end — same 5 tests as Python and Node.js:</p>
 * <ol>
 *   <li>Environment configured</li>
 *   <li>OpenRouter connectivity</li>
 *   <li>Structured output</li>
 *   <li>Cost tracking</li>
 *   <li>Model swap (optional)</li>
 * </ol>
 *
 * <p>Run: {@code mvn test}</p>
 */
class IntegrationTest {

    private static final Logger log = LoggerFactory.getLogger(IntegrationTest.class);

    private static AnnotationConfigApplicationContext ctx;
    private static ChatClient chatClient;
    private static String model;
    private static String modelAlt;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    @BeforeAll
    static void setUp() {
        ctx = new AnnotationConfigApplicationContext(AppConfig.class);
        chatClient = ctx.getBean(ChatClient.class);
        model = ctx.getBean("modelName", String.class);
        modelAlt = ctx.getBean("modelAlt", String.class);
    }

    @AfterAll
    static void tearDown() {
        if (ctx != null) {
            ctx.close();
        }
    }

    // ─── SmokeTest record (used by test 3) ───────────────────

    record SmokeTest(
            @JsonProperty("status") String status,
            @JsonProperty("model_used") String modelUsed
    ) {}

    // ─── Test 1: Environment ─────────────────────────────────

    @Test
    @DisplayName("Environment is configured")
    void environmentIsConfigured() {
        String apiKey = ctx.getBean("apiKey", String.class);
        assertNotNull(apiKey, "openrouter.api.key not set in application.properties");
        assertTrue(apiKey.contains("sk-or-"),
                "API key doesn't look like an OpenRouter key: " + mask(apiKey));

        assertNotNull(model, "devbuddy.model not set");

        log.info("  ✅ .env configured: model={}, key={}", model, mask(apiKey));
    }

    // ─── Test 2: OpenRouter Connectivity ─────────────────────

    @Test
    @DisplayName("OpenRouter responds to a basic prompt within 30s")
    void openRouterResponds() {
        Instant start = Instant.now();

        ChatResponse response = chatClient.prompt()
                .user("Say 'connected' and nothing else.")
                .options(OpenAiChatOptions.builder()
                        .model(model)
                        .temperature(0.0)
                        .build())
                .call()
                .chatResponse();

        Duration elapsed = Duration.between(start, Instant.now());

        assertNotNull(response, "No response from OpenRouter");
        String content = response.getResult().getOutput().getText().toLowerCase();
        assertTrue(content.contains("connected"),
                "Unexpected response: " + content.substring(0, Math.min(50, content.length())));
        assertTrue(elapsed.getSeconds() < 30,
                "Response took " + elapsed.getSeconds() + "s (expected < 30s)");

        Usage usage = response.getMetadata().getUsage();
        long inputTokens = usage != null && usage.getPromptTokens() != null
                ? usage.getPromptTokens() : 0L;
        long outputTokens = usage != null && usage.getCompletionTokens() != null
                ? usage.getCompletionTokens() : 0L;

        log.info("  ✅ OpenRouter connected: {}s, tokens={}+{}",
                String.format("%.1f", elapsed.toMillis() / 1000.0), inputTokens, outputTokens);
    }

    // ─── Test 3: Structured Output ───────────────────────────

    @Test
    @DisplayName("Returns a typed object from structured prompt")
    void returnsTypedObject() throws Exception {
        ChatResponse response = chatClient.prompt()
                .system("Return valid JSON only. Respond with this exact JSON format: " +
                        "{\"status\": \"ok\", \"model_used\": \"the model name\"}")
                .user("Set status='ok'. Include the model you're running on.")
                .options(OpenAiChatOptions.builder()
                        .model(model)
                        .temperature(0.0)
                        .build())
                .call()
                .chatResponse();

        String raw = response.getResult().getOutput().getText();
        SmokeTest result = objectMapper.readValue(stripMarkdownFences(raw.trim()), SmokeTest.class);

        assertEquals("ok", result.status(),
                "Expected status='ok', got '" + result.status() + "'");
        assertNotNull(result.modelUsed(), "model_used field is empty");

        log.info("  ✅ Structured output: SmokeTest(status='{}')", result.status());
    }

    // ─── Test 4: Cost Tracking ───────────────────────────────

    @Test
    @DisplayName("Captures token usage and calculates cost")
    void capturesTokenUsage() {
        ChatResponse response = chatClient.prompt()
                .user("One word: hello")
                .options(OpenAiChatOptions.builder()
                        .model(model)
                        .temperature(0.0)
                        .build())
                .call()
                .chatResponse();

        Usage usage = response.getMetadata().getUsage();
        assertNotNull(usage, "Usage metadata is missing");
        long inputTokens = usage.getPromptTokens() != null ? usage.getPromptTokens() : 0L;
        long outputTokens = usage.getCompletionTokens() != null ? usage.getCompletionTokens() : 0L;

        assertTrue(inputTokens > 0, "input_tokens is 0");
        assertTrue(outputTokens > 0, "output_tokens is 0");

        double cost = CostTracker.calculateCost(model, inputTokens, outputTokens);
        assertTrue(cost > 0, "cost should be > 0");

        log.info("  ✅ Cost tracked: {}+{} tokens, ~${}", inputTokens, outputTokens,
                String.format("%.6f", cost));
    }

    // ─── Test 5: Model Swap (Optional) ───────────────────────

    @Test
    @DisplayName("Model swap works with DEVBUDDY_MODEL_ALT")
    void modelSwapWorks() {
        if (modelAlt == null || modelAlt.isBlank()) {
            log.info("  ⏭️  Model swap skipped (set DEVBUDDY_MODEL_ALT in .env to test)");
            return;
        }

        var altApi = OpenAiApi.builder()
                .baseUrl("https://openrouter.ai/api")
                .apiKey(ctx.getBean("apiKey", String.class))
                .build();
        var altModel = OpenAiChatModel.builder()
                .openAiApi(altApi)
                .defaultOptions(OpenAiChatOptions.builder()
                        .model(modelAlt)
                        .temperature(0.0)
                        .build())
                .build();
        var altClient = ChatClient.builder(altModel).build();

        Instant start = Instant.now();
        ChatResponse response = altClient.prompt()
                .user("Say 'ok'")
                .call()
                .chatResponse();
        Duration elapsed = Duration.between(start, Instant.now());

        assertNotNull(response, "No response from " + modelAlt);
        assertTrue(elapsed.getSeconds() < 30,
                modelAlt + " took " + elapsed.getSeconds() + "s");

        log.info("  ✅ Model swap: {} responded in {}s",
                modelAlt, String.format("%.1f", elapsed.toMillis() / 1000.0));
    }

    // ─── Helpers ─────────────────────────────────────────────

    private static String mask(String key) {
        if (key == null || key.length() <= 12) return key;
        return "*".repeat(8) + key.substring(key.length() - 4);
    }

    private static String stripMarkdownFences(String text) {
        if (text.startsWith("```")) {
            int newline = text.indexOf('\n');
            text = newline >= 0 ? text.substring(newline + 1) : text.substring(3);
        }
        if (text.endsWith("```")) {
            text = text.substring(0, text.length() - 3).trim();
        }
        return text;
    }
}
