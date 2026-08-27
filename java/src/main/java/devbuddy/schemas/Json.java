package devbuddy.schemas;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;

/**
 * Shared JSON support for the schema records.
 *
 * <p>Uses SNAKE_CASE naming so the Java records (camelCase components) map
 * to the snake_case fields in {@code shared/data/*.json} and the LLM prompts.</p>
 */
public final class Json {

    /** Snake-case aware mapper. Enums serialize via their {@code @JsonValue}. */
    public static final ObjectMapper MAPPER = new ObjectMapper()
            .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);

    private Json() {
        // utility class
    }

    /**
     * Parse a JSON string into a record, running the record's compact-constructor
     * validation (cross-field invariants). Throws on invalid JSON or invalid state.
     */
    public static <T> T parse(String json, Class<T> type) {
        try {
            return MAPPER.readValue(json, type);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("Invalid JSON for " + type.getSimpleName() + ": " + e.getMessage(), e);
        }
    }

    /** Serialize a record back to pretty JSON. */
    public static String toJson(Object value) {
        try {
            return MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("Failed to serialize " + value.getClass().getSimpleName(), e);
        }
    }

    /** Strip markdown code fences (```json ... ```) from LLM output before parsing. */
    public static String stripMarkdownFences(String text) {
        String t = text.trim();
        if (t.startsWith("```")) {
            int newline = t.indexOf('\n');
            t = newline >= 0 ? t.substring(newline + 1) : t.substring(3);
        }
        if (t.endsWith("```")) {
            t = t.substring(0, t.length() - 3).trim();
        }
        return t;
    }
}
