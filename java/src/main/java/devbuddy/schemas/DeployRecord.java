package devbuddy.schemas;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * A single deployment event.
 */
public record DeployRecord(
        String sha,
        String author,
        String timestamp,
        Status status
) {

    /** Required-field validation (mirrors Pydantic/Zod required fields). */
    public DeployRecord {
        if (sha == null) {
            throw new IllegalArgumentException("sha is required");
        }
        if (author == null) {
            throw new IllegalArgumentException("author is required");
        }
        if (timestamp == null) {
            throw new IllegalArgumentException("timestamp is required");
        }
        if (status == null) {
            throw new IllegalArgumentException("status is required");
        }
    }

    public enum Status {
        SUCCESS("success"), FAILED("failed"), ROLLING_BACK("rolling_back");

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
            throw new IllegalArgumentException("Invalid deploy status: '" + v
                    + "'. Expected one of success/failed/rolling_back.");
        }
    }
}
