package devbuddy.service;

import devbuddy.schemas.BuildCheck;
import devbuddy.schemas.Json;
import devbuddy.schemas.JsonSchemas;
import devbuddy.schemas.ServiceReadinessReport;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.openai.api.ResponseFormat;
import org.springframework.stereotype.Component;

/**
 * Week 2 — Structured output functions.
 *
 * <p>Equivalent to {@code analyze_pr()} and {@code generate_readiness_report()}
 * in Python {@code schemas.py} / Node.js {@code schemas.js}, and to
 * {@code with_structured_output()} / {@code withStructuredOutput()}: the output
 * schema is enforced at the API level via {@code response_format: json_schema}
 * (strict mode), so the model cannot return output that violates the schema.
 * The record constructors then enforce the cross-field validation invariants
 * on top.</p>
 */
@Component
public class SchemasService {

    private static final String ANALYZE_PR_SYSTEM_PROMPT = """
            You are a code reviewer. Analyze the given PR and produce a structured BuildCheck.
            The output schema is enforced by the API (response_format=json_schema) —
            do not add markdown fences or extra text.

            Field rules:
            - severity: 'critical' if it touches auth, payments, or security.
              'high' if it changes core logic. 'medium' for feature work. 'low' for docs/typos.
            - summary: one sentence describing what changed and why.
            - affected_files: list the files mentioned in the diff.
            - project: extract the project or service name from the PR context.""";

    private static final String READINESS_SYSTEM_PROMPT = """
            You are a site reliability engineer assessing whether a service is ready
            for its next release. You are given build health data and recent deployment
            history. Produce a structured ServiceReadinessReport.
            The output schema is enforced by the API (response_format=json_schema) —
            do not add markdown fences or extra text.

            RULES:
            - If the build status is 'healthy' with no active incidents and recent
              deploys are all 'success', the service is ready with high confidence.
            - If the build is 'degraded' or there are active incidents, the service is
              NOT ready. List specific blockers.
            - If there is no data at all, set confidence to 'low'.
            - Every verdict must be supported by evidence. Reference the data you were given.
            - Blockers should be specific and actionable, not vague.""";

    private final ChatClient chatClient;
    private final String model;

    public SchemasService(ChatClient chatClient, String model) {
        this.chatClient = chatClient;
        this.model = model;
    }

    /**
     * Analyze a PR and return a structured {@link BuildCheck}.
     *
     * @param title       PR title
     * @param diff        PR diff content
     * @param temperature 0.0 for deterministic output
     * @param maxTokens   max tokens in response (null = model default)
     */
    public BuildCheck analyzePr(String title, String diff, double temperature, Integer maxTokens) {
        ChatResponse response = chatClient.prompt()
                .system(ANALYZE_PR_SYSTEM_PROMPT)
                .user("PR Title: " + title + "\n\nDiff:\n" + diff)
                .options(options(temperature, maxTokens,
                        JsonSchemas.responseFormat("build_check", JsonSchemas.BUILD_CHECK)))
                .call()
                .chatResponse();

        String raw = response.getResult().getOutput().getText();
        return Json.parse(Json.stripMarkdownFences(raw), BuildCheck.class);
    }

    /**
     * Generate a {@link ServiceReadinessReport} from mock build/deploy data.
     *
     * @param serviceName  e.g. "auth-service"
     * @param buildData    JSON string with build status fields
     * @param deployData   JSON string with deployment history
     * @param temperature  0.0 for deterministic output
     */
    public ServiceReadinessReport generateReadinessReport(
            String serviceName, String buildData, String deployData, double temperature) {
        ChatResponse response = chatClient.prompt()
                .system(READINESS_SYSTEM_PROMPT)
                .user("Service: " + serviceName + "\n\n"
                        + "Build data:\n" + buildData + "\n\n"
                        + "Deployment data:\n" + deployData)
                .options(options(temperature, null,
                        JsonSchemas.responseFormat("service_readiness_report",
                                JsonSchemas.SERVICE_READINESS_REPORT)))
                .call()
                .chatResponse();

        String raw = response.getResult().getOutput().getText();
        return Json.parse(Json.stripMarkdownFences(raw), ServiceReadinessReport.class);
    }

    private OpenAiChatOptions options(double temperature, Integer maxTokens, ResponseFormat responseFormat) {
        var builder = OpenAiChatOptions.builder()
                .model(model)
                .temperature(temperature)
                .responseFormat(responseFormat);
        if (maxTokens != null) {
            builder = builder.maxTokens(maxTokens);
        }
        return builder.build();
    }
}
