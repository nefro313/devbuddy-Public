package devbuddy.schemas;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * Current build health of the service.
 *
 * <p>Cross-field invariant (mirrors Pydantic {@code @field_validator} /
 * Zod {@code .refine()}): if {@code status} is {@code degraded} or
 * {@code down}, {@code failingSince} must be present.</p>
 */
public record BuildStatus(
        Status status,
        String lastDeploy,
        String failingSince
) {

    public BuildStatus {
        if ((status == Status.DEGRADED || status == Status.DOWN)
                && (failingSince == null || failingSince.isBlank())) {
            throw new IllegalArgumentException(
                    "failing_since is required when status is '" + status.value()
                            + "'. Provide an ISO timestamp.");
        }
    }

    public enum Status {
        HEALTHY("healthy"), DEGRADED("degraded"), DOWN("down"), UNKNOWN("unknown");

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
            throw new IllegalArgumentException("Invalid build status: '" + v
                    + "'. Expected one of healthy/degraded/down/unknown.");
        }
    }
}
