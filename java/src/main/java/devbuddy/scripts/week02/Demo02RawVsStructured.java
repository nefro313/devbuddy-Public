package devbuddy.scripts.week02;

import devbuddy.config.AppConfig;
import devbuddy.schemas.Json;
import devbuddy.schemas.JsonSchemas;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.util.List;

/**
 * Week 2 — Demo 2: Raw JSON Prompting vs. Native Structured Output.
 *
 * <p>Same as Python {@code demo-02-raw-vs-pydantic.py} / Node
 * {@code demo-02-raw-vs-zod.js}: raw JSON prompting is a polite request (the
 * model may wrap output in markdown fences or invent field names), while native
 * structured output (response_format=json_schema) is a contract. Uses the same
 * nested {@code DiffAnalysis} schema (change + details + technical).</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week02.Demo02RawVsStructured}</p>
 */
public class Demo02RawVsStructured {

    private static final String DIFF = """
            Fix login redirect loop in auth-service (PROJ-421)
            Changed session token validation in src/auth.py lines 42-58.
            Previously expired tokens caused infinite redirect for 15% of users.
            Now returns 401 with clear error. No DB changes. Rollback: revert commit.
            Files: src/auth.py, tests/test_auth.py""";

    // ── The nested schema (mirrors Python DiffAnalysis / Node DiffAnalysisSchema) ──
    // Parsed with Json.MAPPER (SNAKE_CASE), so filesChanged ↔ files_changed etc.

    public record Change(String type, String severity, String ticket) {}

    public record Technical(List<String> filesChanged, boolean dbChanged, String rollback) {}

    public record Details(String summary, String rootCause, Integer userImpactPct) {}

    public record DiffAnalysis(Change change, Details details, Technical technical) {}

    /** snake_case JSON schema for native structured output (strict). */
    private static final String DIFF_ANALYSIS_SCHEMA = """
            {
              "type": "object",
              "properties": {
                "change": {
                  "type": "object",
                  "properties": {
                    "type": { "type": "string", "enum": ["bug", "feature", "refactor", "hotfix"] },
                    "severity": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
                    "ticket": { "type": ["string", "null"] }
                  },
                  "required": ["type", "severity", "ticket"],
                  "additionalProperties": false
                },
                "details": {
                  "type": "object",
                  "properties": {
                    "summary": { "type": "string" },
                    "root_cause": { "type": "string" },
                    "user_impact_pct": { "type": ["integer", "null"] }
                  },
                  "required": ["summary", "root_cause", "user_impact_pct"],
                  "additionalProperties": false
                },
                "technical": {
                  "type": "object",
                  "properties": {
                    "files_changed": { "type": "array", "items": { "type": "string" } },
                    "db_changed": { "type": "boolean" },
                    "rollback": { "type": "string" }
                  },
                  "required": ["files_changed", "db_changed", "rollback"],
                  "additionalProperties": false
                }
              },
              "required": ["change", "details", "technical"],
              "additionalProperties": false
            }""";

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            ChatClient chatClient = ctx.getBean(ChatClient.class);
            String model = ctx.getBean("modelName", String.class);

            System.out.println("=".repeat(75));
            System.out.println("  DEMO: Raw JSON Prompting (Request) vs. Structured Output (Contract)");
            System.out.println("=".repeat(75));
            System.out.println("  Model: " + model);
            System.out.println();
            System.out.println("  THE INPUT (same for both approaches):");
            System.out.println("  " + "-".repeat(55));
            for (String line : DIFF.strip().split("\n")) {
                System.out.println("  | " + line);
            }
            System.out.println("  " + "-".repeat(55));
            System.out.println();

            // ── Approach A: raw prompting — "the request" ─────────────
            System.out.println("=".repeat(75));
            System.out.println("  APPROACH A: Raw JSON Prompting");
            System.out.println("  Strategy: Ask the model nicely to return JSON.");
            System.out.println("  Problem:  It's a request, not a contract.");
            System.out.println("=".repeat(75));
            System.out.println();

            String rawPrompt = """
                    Analyze this code change and extract details. Return a JSON object matching this schema:
                    {
                      "change": { "type": "bug|feature|refactor|hotfix", "severity": "low|medium|high|critical", "ticket": "string" },
                      "details": { "summary": "string", "root_cause": "string", "user_impact_pct": integer },
                      "technical": { "files_changed": ["string"], "db_changed": boolean, "rollback": "string" }
                    }

                    DIFF:
                    """ + DIFF;

            String raw = chatClient.prompt()
                    .user(rawPrompt)
                    .call()
                    .chatResponse().getResult().getOutput().getText();

            System.out.println("  Raw response:");
            for (String line : raw.strip().split("\n")) {
                System.out.println("  | " + line);
            }
            System.out.println();

            System.out.println("  Attempting Json.parse() on the raw text...");
            try {
                DiffAnalysis parsed = Json.parse(raw, DiffAnalysis.class);
                System.out.println("  OK (no fences this time) -> change.type=" + parsed.change().type());
            } catch (RuntimeException e) {
                System.out.println("  ✗ PARSE FAILED: " + e.getMessage());
                System.out.println("    A stray ```json fence or a chatty sentence breaks the pipeline.");
            }
            System.out.println();

            // ── Approach B: native structured output — "the contract" ──
            System.out.println("=".repeat(75));
            System.out.println("  APPROACH B: response_format=json_schema (native structured output)");
            System.out.println("  Result:   The model CANNOT return output that violates the schema.");
            System.out.println("=".repeat(75));
            System.out.println();

            var options = OpenAiChatOptions.builder()
                    .model(model)
                    .temperature(0.0)
                    .responseFormat(JsonSchemas.responseFormat("diff_analysis", DIFF_ANALYSIS_SCHEMA))
                    .build();

            ChatResponse response = chatClient.prompt()
                    .system("Analyze the diff and return a valid DiffAnalysis object.")
                    .user("Analyze this diff:\n" + DIFF)
                    .options(options)
                    .call()
                    .chatResponse();

            DiffAnalysis result = Json.parse(
                    Json.stripMarkdownFences(response.getResult().getOutput().getText()),
                    DiffAnalysis.class);

            System.out.println("  Returned: " + result.getClass().getSimpleName() + " (typed record, not a String)");
            System.out.println("    change.type:        " + result.change().type());
            System.out.println("    change.severity:    " + result.change().severity());
            System.out.println("    change.ticket:      " + result.change().ticket());
            System.out.println("    details.summary:    " + result.details().summary());
            System.out.println("    details.root_cause: " + result.details().rootCause());
            System.out.println("    details.user_impact_pct: " + result.details().userImpactPct());
            System.out.println("    technical.files_changed: " + result.technical().filesChanged());
            System.out.println("    technical.db_changed:    " + result.technical().dbChanged());
            System.out.println("    technical.rollback:      " + result.technical().rollback());
            System.out.println();
            System.out.println("  Raw JSON prompting = hope-based architecture.");
            System.out.println("  Native json_schema = engineering.");
            System.out.println("=".repeat(75));
        }
    }
}
