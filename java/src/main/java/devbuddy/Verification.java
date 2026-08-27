package devbuddy;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import devbuddy.config.AppConfig;
import devbuddy.cost.CostTracker;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import org.springframework.ai.retry.NonTransientAiException;

import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;

/**
 * DevBuddy Verification — Week 0 (Java CLI)
 *
 * <p>Bootstraps a minimal Spring IoC container (no Boot, no web server),
 * wires Spring AI to OpenRouter, and runs the 3-project verification loop.</p>
 *
 * <p>Usage:
 * <pre>{@code
 * export OPENROUTER_API_KEY=sk-or-...
 * ./mvnw compile exec:java
 * }</pre></p>
 */
public class Verification {

    /**
     * Week 0 build-status check schema — defined inline, exactly like Python's
     * {@code verification.py} and Node.js's {@code verification.js}.
     * (Distinct from {@code devbuddy.schemas.BuildCheck}, the Week 2 PR schema.)
     */
    public record BuildCheck(
            String project,
            Status status,
            double confidence,
            String explanation
    ) {
        public enum Status {
            PASSING("passing"), FAILING("failing"), IN_PROGRESS("in_progress"), UNKNOWN("unknown");

            private final String value;

            Status(String value) {
                this.value = value;
            }

            @JsonValue
            public String value() {
                return value;
            }

            @JsonCreator
            public static Status fromValue(String v) {
                for (Status s : values()) {
                    if (s.value.equalsIgnoreCase(v)) {
                        return s;
                    }
                }
                throw new IllegalArgumentException("Invalid build status: " + v);
            }
        }
    }

    private static final Logger log = LoggerFactory.getLogger(Verification.class);

    private static final String[] PROJECTS = {"auth-service", "api-gateway", "user-service"};

    private static final String SYSTEM_PROMPT = """
            You are a build status checker.
            You are being evaluated on your ability to return valid, typed JSON.
            Be honest: you don't have real CI access, so set confidence appropriately.
            Explain WHY you picked the status you did.

            Return ONLY a JSON object with these exact fields — no markdown fences, no extra text:
            {
              "project": "string (exact project name)",
              "status": "passing | failing | in_progress | unknown",
              "confidence": number between 0.0 and 1.0,
              "explanation": "one sentence explaining the result"
            }""";

    private static final String BORDER = "=".repeat(60);

    private final ChatClient chatClient;
    private final String model;
    private final ObjectMapper objectMapper;

    public Verification(ChatClient chatClient, String model) {
        this.chatClient = chatClient;
        this.model = model;
        this.objectMapper = new ObjectMapper();
    }

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            ChatClient chatClient = ctx.getBean(ChatClient.class);
            String model = ctx.getBean("modelName", String.class);
            new Verification(chatClient, model).run();
        }
    }

    private void run() {
        log.info(BORDER);
        log.info("  DevBuddy Verification — Week 0 (Java)");
        log.info(BORDER);
        log.info("");

        double totalCost = 0.0;
        long totalTokens = 0;

        for (int i = 0; i < PROJECTS.length; i++) {
            String project = PROJECTS[i];
            log.info("[{}/{}] Checking: {}...", i + 1, PROJECTS.length, project);

            Instant start = Instant.now();

            // ── Call the LLM via OpenRouter ──────────────────
            ChatResponse response;
            try {
                response = chatClient.prompt()
                        .system(SYSTEM_PROMPT)
                        .user(String.format("""
                                Check the build status of '%s'.
                                Return a BuildCheck JSON object with:
                                - project: exactly '%s'
                                - status: one of passing/failing/in_progress/unknown
                                - confidence: 0-1 (be honest — you don't have real CI access)
                                - explanation: one sentence""", project, project))
                        .options(OpenAiChatOptions.builder()
                                .model(model)
                                .temperature(0.0)
                                .build())
                        .call()
                        .chatResponse();
            } catch (NonTransientAiException e) {
                log.error("  OpenRouter call failed — {}", summarizeError(e));
                log.error("");
                log.error("  Check your OPENROUTER_API_KEY is valid and network is reachable.");
                System.exit(1);
                return; // unreachable, but keeps compiler happy
            } catch (Exception e) {
                log.error("  Unexpected error: {}", e.getMessage());
                System.exit(1);
                return;
            }

            Duration elapsed = Duration.between(start, Instant.now());

            // ── Parse the typed result ───────────────────────
            String rawContent = response.getResult().getOutput().getText();
            BuildCheck result = parseBuildCheck(rawContent);

            // ── Extract token usage (defensive) ──────────────
            Usage usage = response.getMetadata().getUsage();
            long promptTokens = usage != null && usage.getPromptTokens() != null
                    ? usage.getPromptTokens() : 0L;
            long completionTokens = usage != null && usage.getCompletionTokens() != null
                    ? usage.getCompletionTokens() : 0L;
            long callTokens = promptTokens + completionTokens;
            totalTokens += callTokens;

            // ── Cost ─────────────────────────────────────────
            double cost = CostTracker.calculateCost(model, promptTokens, completionTokens);
            totalCost += cost;

            // ── Log per-call results ─────────────────────────
            double elapsedSec = elapsed.toMillis() / 1000.0;

            log.info("  Status:      {}", result.status());
            log.info("  Confidence:  {}", toPercent(result.confidence()));
            log.info("  Reason:      {}", result.explanation());
            log.info("  Tokens:      {} ({} in / {} out)", callTokens, promptTokens, completionTokens);
            log.info("  Cost:        ${}", formatDollars(cost));
            log.info("  Time:        {}", formatSeconds(elapsedSec));
            log.info("  Type:        {} ← typed record, not a string!", BuildCheck.class.getSimpleName());
            log.info("");
        }

        // ── Summary ──────────────────────────────────────────
        String timestamp = ZonedDateTime.now().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME);
        String javaVersion = System.getProperty("java.version");

        log.info(BORDER);
        log.info("  ✅ VERIFICATION PASSED");
        log.info("  Java:       {}", javaVersion);
        log.info("  Model:      {}", model);
        log.info("  Total tokens: {}", totalTokens);
        log.info("  Total cost:   ${}", formatDollars(totalCost));
        log.info("  Date:       {}", timestamp);
        log.info("");
        log.info("  Your environment is ready for Week 1.");
        log.info("  Post this output to #devbuddy-series to confirm.");
        log.info("");
        log.info("  What do you want DevBuddy to help you with?");
        log.info("  _______________________________________________");
        log.info(BORDER);
    }

    // ── Formatting helpers ───────────────────────────────────

    private static String toPercent(double value) {
        return String.format("%.0f%%", value * 100);
    }

    private static String formatDollars(double value) {
        return String.format("%.6f", value);
    }

    private static String formatSeconds(double value) {
        return String.format("%.2fs", value);
    }

    // ── Error handling ──────────────────────────────────────

    /**
     * Extracts a clean one-line summary from a Spring AI exception.
     * The raw message contains the HTTP status plus the full HTML
     * response body — we only surface the status with a hint.
     */
    private static String summarizeError(NonTransientAiException e) {
        String msg = e.getMessage();
        if (msg == null) {
            return "unknown error (no details)";
        }
        // Message format: "404 - <!DOCTYPE html>..."
        int dash = msg.indexOf(" - ");
        String code = dash > 0 ? msg.substring(0, dash) : msg.lines().findFirst().orElse("error");
        return switch (code.trim()) {
            case "401" -> "HTTP 401 — invalid or missing API key";
            case "402" -> "HTTP 402 — account balance exhausted";
            case "404" -> "HTTP 404 — check API key and model name";
            case "429" -> "HTTP 429 — rate limited, wait and retry";
            case "500", "502", "503" -> "HTTP " + code + " — OpenRouter server error, retry later";
            default -> "HTTP " + code + " — " + msg.lines().skip(1).findFirst().orElse("unexpected error");
        };
    }

    // ── JSON parsing ─────────────────────────────────────────

    private BuildCheck parseBuildCheck(String raw) {
        String json = stripMarkdownFences(raw.trim());
        try {
            return objectMapper.readValue(json, BuildCheck.class);
        } catch (JsonProcessingException e) {
            log.error("Failed to parse LLM output as BuildCheck.\nRaw:\n{}\nError: {}",
                    raw, e.getMessage());
            return new BuildCheck("unknown", BuildCheck.Status.UNKNOWN, 0.0,
                    "Parse error — see logs; " + e.getMessage());
        }
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
