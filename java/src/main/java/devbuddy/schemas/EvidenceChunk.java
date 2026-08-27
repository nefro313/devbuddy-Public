package devbuddy.schemas;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * A piece of supporting context retrieved or produced during analysis.
 */
public record EvidenceChunk(
        Source source,
        String content,
        Double relevanceScore
) {

    /** Required-field validation (relevance_score stays optional/nullable). */
    public EvidenceChunk {
        if (source == null) {
            throw new IllegalArgumentException("source is required");
        }
        if (content == null) {
            throw new IllegalArgumentException("content is required");
        }
    }

    public enum Source {
        RAG("rag"), TOOL("tool"), USER("user");

        private final String value;

        Source(String value) {
            this.value = value;
        }

        @JsonValue
        public String value() {
            return value;
        }

        @JsonCreator
        public static Source fromValue(String v) {
            for (Source s : values()) {
                if (s.value.equalsIgnoreCase(v)) {
                    return s;
                }
            }
            throw new IllegalArgumentException("Invalid evidence source: '" + v
                    + "'. Expected one of rag/tool/user.");
        }
    }
}
