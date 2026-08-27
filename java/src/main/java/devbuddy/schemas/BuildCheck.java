package devbuddy.schemas;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * A structured analysis of a PR or code change.
 *
 * <p>Equivalent to:
 * <ul>
 *   <li>Python: {@code BuildCheck(BaseModel)} in {@code schemas.py}</li>
 *   <li>Node.js: {@code BuildCheckSchema} Zod schema in {@code schemas.js}</li>
 * </ul></p>
 */
public record BuildCheck(
        String project,
        Severity severity,
        String summary,
        java.util.List<String> affectedFiles
) {

    /** Required-field validation (mirrors Pydantic/Zod required fields). */
    public BuildCheck {
        if (project == null) {
            throw new IllegalArgumentException("project is required");
        }
        if (severity == null) {
            throw new IllegalArgumentException("severity is required");
        }
        if (summary == null) {
            throw new IllegalArgumentException("summary is required");
        }
        if (affectedFiles == null) {
            throw new IllegalArgumentException("affected_files is required");
        }
    }

    public enum Severity {
        LOW("low"), MEDIUM("medium"), HIGH("high"), CRITICAL("critical");

        private final String value;

        Severity(String value) {
            this.value = value;
        }

        @JsonValue
        public String value() {
            return value;
        }

        @JsonCreator
        public static Severity fromValue(String v) {
            for (Severity s : values()) {
                if (s.value.equalsIgnoreCase(v)) {
                    return s;
                }
            }
            throw new IllegalArgumentException("Invalid severity: '" + v
                    + "'. Expected one of low/medium/high/critical.");
        }
    }
}
