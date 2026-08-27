package devbuddy.config;

import devbuddy.service.SchemasService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;

/**
 * Spring IoC configuration — wires OpenRouter via Spring AI.
 *
 * <p>Reads settings from {@code application.properties} (classpath)
 * with system environment variables as fallback via {@code ${VAR:default}}
 * syntax.</p>
 *
 * <p>Equivalent to:
 * <ul>
 *   <li>Python: {@code config.py} + {@code llm.py}</li>
 *   <li>Node.js: {@code config.js} + {@code llm.js}</li>
 * </ul>
 */
@Configuration
@PropertySource("classpath:application.properties")
public class AppConfig {

    private static final Logger log = LoggerFactory.getLogger(AppConfig.class);

    // Spring AI appends /v1/chat/completions to the base URL internally.
    // Setting base to /api/v1 would double-up: /api/v1/v1/chat/completions → 404.
    private static final String OPENROUTER_BASE_URL = "https://openrouter.ai/api";

    @Value("${openrouter.api.key}")
    private String apiKey;

    @Value("${devbuddy.model}")
    private String model;

    @Value("${devbuddy.model-alt:#{null}}")
    private String modelAlt;

    /**
     * Required for {@code @Value} resolution in {@code @Configuration} classes
     * when not using Spring Boot auto-configuration.
     */
    @Bean
    public static PropertySourcesPlaceholderConfigurer propertyConfigurer() {
        return new PropertySourcesPlaceholderConfigurer();
    }

    @Bean
    public OpenAiApi openAiApi() {
        if (apiKey == null || apiKey.isBlank()) {
            throw new IllegalStateException(
                    "openrouter.api.key is not set.\n" +
                    "Either set it in application.properties or export OPENROUTER_API_KEY.");
        }
        log.debug("OpenAiApi configured → {}", OPENROUTER_BASE_URL);
        return OpenAiApi.builder()
                .baseUrl(OPENROUTER_BASE_URL)
                .apiKey(apiKey)
                .build();
    }

    @Bean
    public OpenAiChatModel chatModel(OpenAiApi openAiApi) {
        log.info("Chat model: {} (temperature=0.0)", model);
        return OpenAiChatModel.builder()
                .openAiApi(openAiApi)
                .defaultOptions(OpenAiChatOptions.builder()
                        .model(model)
                        .temperature(0.0)
                        .build())
                .build();
    }

    @Bean
    public ChatClient chatClient(ChatModel chatModel) {
        return ChatClient.builder(chatModel).build();
    }

    /** Week 2 — structured output functions (analyzePr + generateReadinessReport). */
    @Bean
    public SchemasService schemasService(ChatClient chatClient) {
        return new SchemasService(chatClient, model);
    }

    /** Exposed as a named bean so other components can reference the model name. */
    @Bean
    public String modelName() {
        return model;
    }

    /** Optional alternate model for provider swap tests. Empty string when unset
     *  (returning null would register a Spring {@code NullBean}, which breaks
     *  {@code ctx.getBean("modelAlt", String.class)} lookups). */
    @Bean
    public String modelAlt() {
        return modelAlt == null ? "" : modelAlt;
    }

    /** Exposed for tests that need to create a second client for model swap. */
    @Bean
    public String apiKey() {
        return apiKey;
    }
}
