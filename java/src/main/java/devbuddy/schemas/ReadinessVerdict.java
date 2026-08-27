package devbuddy.schemas;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.List;

/**
 * Final verdict: is this service ready for the target version?
 */
public record ReadinessVerdict(
        boolean ready,
        Confidence confidence,
        List<String> blockers,
        List<String> recommendedNextSteps
) {

    public ReadinessVerdict {
        blockers = blockers == null ? List.of() : blockers;
        recommendedNextSteps = recommendedNextSteps == null ? List.of() : recommendedNextSteps;
    }

    public enum Confidence {
        LOW("low"), MEDIUM("medium"), HIGH("high");

        private final String value;

        Confidence(String value) {
            this.value = value;
        }

        @JsonValue
        public String value() {
            return value;
        }

        @JsonCreator
        public static Confidence fromValue(String v) {
            for (Confidence c : values()) {
                if (c.value.equalsIgnoreCase(v)) {
                    return c;
                }
            }
            throw new IllegalArgumentException("Invalid confidence: '" + v
                    + "'. Expected one of low/medium/high.");
        }
    }
}
