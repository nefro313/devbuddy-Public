package devbuddy.schemas;

import java.util.List;

/**
 * The structured output DevBuddy produces for a service readiness check.
 *
 * <p>This is what the capstone delivers — it composes context (RAG), live data
 * (tools), and reasoning into one typed, validated contract.</p>
 *
 * <p>Cross-field invariants (mirror Pydantic {@code @model_validator} /
 * Zod {@code .refine()}):</p>
 * <ol>
 *   <li>{@code ready=true} + non-empty {@code blockers} → reject</li>
 *   <li>{@code ready=false} + {@code confidence != low} + no blockers → reject</li>
 *   <li>no evidence + {@code confidence != low} → reject</li>
 * </ol>
 */
public record ServiceReadinessReport(
        ServiceInfo service,
        BuildStatus build,
        DeploymentInfo deployment,
        ReadinessVerdict verdict,
        List<EvidenceChunk> evidence
) {

    public ServiceReadinessReport {
        evidence = evidence == null ? List.of() : evidence;

        if (verdict.ready() && !verdict.blockers().isEmpty()) {
            throw new IllegalArgumentException(
                    "Contradiction: verdict.ready=true but blockers=" + verdict.blockers()
                            + ". If there are blockers, ready must be false.");
        }
        if (!verdict.ready() && verdict.confidence() != ReadinessVerdict.Confidence.LOW
                && verdict.blockers().isEmpty()) {
            throw new IllegalArgumentException(
                    "verdict.ready=false with confidence='" + verdict.confidence().value()
                            + "' but no blockers listed. Either lower confidence to 'low' or add blockers.");
        }
        if (evidence.isEmpty() && verdict.confidence() != ReadinessVerdict.Confidence.LOW) {
            throw new IllegalArgumentException(
                    "No evidence provided but confidence='" + verdict.confidence().value()
                            + "'. Without evidence, confidence must be 'low'.");
        }
    }
}
