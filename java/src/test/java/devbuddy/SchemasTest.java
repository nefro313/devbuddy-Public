package devbuddy;

import devbuddy.schemas.*;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Week 2 — Pure schema validation tests (no API calls, instant).
 *
 * <p>Equivalent to the pure-Pydantic / pure-Zod portions of
 * {@code tests/test_schemas.py} / {@code tests/test_schemas.js}.</p>
 *
 * <p>Run: {@code mvn test -Dtest=SchemasTest}</p>
 */
class SchemasTest {

    // ── BuildCheck ────────────────────────────────────────────

    @Test
    @DisplayName("BuildCheck validates a valid object")
    void buildCheckValid() {
        BuildCheck bc = new BuildCheck(
                "auth-service",
                BuildCheck.Severity.HIGH,
                "Fixed login redirect loop",
                java.util.List.of("src/auth.py", "tests/test_auth.py")
        );
        assertEquals("auth-service", bc.project());
        assertEquals(BuildCheck.Severity.HIGH, bc.severity());
    }

    @Test
    @DisplayName("BuildCheck rejects invalid severity")
    void buildCheckRejectsInvalidSeverity() {
        assertThrows(IllegalArgumentException.class,
                () -> Json.parse("{\"project\":\"auth-service\",\"severity\":\"INVALID\",\"summary\":\"test\",\"affected_files\":[\"app.js\"]}",
                        BuildCheck.class));
    }

    @Test
    @DisplayName("BuildCheck rejects missing fields")
    void buildCheckRejectsMissingFields() {
        assertThrows(IllegalArgumentException.class,
                () -> Json.parse("{\"project\":\"auth-service\",\"summary\":\"test\",\"affected_files\":[\"app.js\"]}",
                        BuildCheck.class));
    }

    // ── ServiceReadinessReport — happy paths ─────────────────

    @Test
    @DisplayName("validates the healthy reference scenario")
    void healthyScenario() {
        ServiceReadinessReport report = loadReport("service-readiness-healthy.json");
        assertEquals("auth-service", report.service().name());
        assertEquals(BuildStatus.Status.HEALTHY, report.build().status());
        assertTrue(report.verdict().ready());
        assertEquals(ReadinessVerdict.Confidence.HIGH, report.verdict().confidence());
        assertEquals(0, report.verdict().blockers().size());
        assertEquals(2, report.evidence().size());
    }

    @Test
    @DisplayName("validates the degraded scenario")
    void degradedScenario() {
        ServiceReadinessReport report = loadReport("service-readiness-degraded.json");
        assertEquals(BuildStatus.Status.DEGRADED, report.build().status());
        assertNotNull(report.build().failingSince());
        assertFalse(report.verdict().ready());
        assertTrue(report.verdict().blockers().size() > 0);
    }

    @Test
    @DisplayName("validates the unknown scenario")
    void unknownScenario() {
        ServiceReadinessReport report = loadReport("service-readiness-unknown.json");
        assertEquals(BuildStatus.Status.UNKNOWN, report.build().status());
        assertEquals(ReadinessVerdict.Confidence.LOW, report.verdict().confidence());
    }

    // ── Cross-field invariants ────────────────────────────────

    @Test
    @DisplayName("rejects ready=true with blockers")
    void rejectsReadyWithBlockers() {
        String json = """
                {
                  "service": {"name":"test-svc","version":"1.0.0","owner_team":"qa"},
                  "build": {"status":"healthy","last_deploy":"2026-06-28T00:00:00Z","failing_since":null},
                  "deployment": {"recent_deploys":[],"active_incidents":[]},
                  "verdict": {"ready":true,"confidence":"high","blockers":["build is red"],"recommended_next_steps":[]},
                  "evidence": [{"source":"tool","content":"build=green","relevance_score":null}]
                }""";
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> Json.parse(json, ServiceReadinessReport.class));
        assertTrue(e.getMessage().contains("Contradiction"));
    }

    @Test
    @DisplayName("rejects ready=false with high confidence and no blockers")
    void rejectsNotReadyHighConfidenceNoBlockers() {
        String json = """
                {
                  "service": {"name":"test-svc","version":"1.0.0","owner_team":"qa"},
                  "build": {"status":"healthy","last_deploy":"2026-06-28T00:00:00Z","failing_since":null},
                  "deployment": {"recent_deploys":[],"active_incidents":[]},
                  "verdict": {"ready":false,"confidence":"high","blockers":[],"recommended_next_steps":[]},
                  "evidence": []
                }""";
        assertThrows(IllegalArgumentException.class,
                () -> Json.parse(json, ServiceReadinessReport.class));
    }

    @Test
    @DisplayName("rejects degraded status with no failing_since")
    void rejectsDegradedNoFailingSince() {
        String json = """
                {
                  "service": {"name":"test-svc","version":"1.0.0","owner_team":"qa"},
                  "build": {"status":"degraded","last_deploy":"2026-06-28T00:00:00Z","failing_since":null},
                  "deployment": {"recent_deploys":[],"active_incidents":[]},
                  "verdict": {"ready":false,"confidence":"low","blockers":["build degraded"],"recommended_next_steps":[]},
                  "evidence": []
                }""";
        IllegalArgumentException e = assertThrows(IllegalArgumentException.class,
                () -> Json.parse(json, ServiceReadinessReport.class));
        assertTrue(e.getMessage().contains("failing_since"));
    }

    @Test
    @DisplayName("rejects invalid DeployRecord status")
    void rejectsInvalidDeployStatus() {
        assertThrows(IllegalArgumentException.class,
                () -> Json.parse("{\"sha\":\"abc123\",\"author\":\"test\",\"timestamp\":\"2026-06-28T00:00:00Z\",\"status\":\"in_progress\"}",
                        DeployRecord.class));
    }

    @Test
    @DisplayName("round-trips through JSON")
    void roundTripsThroughJson() {
        ServiceReadinessReport report = loadReport("service-readiness-healthy.json");
        String dumped = Json.toJson(report);
        ServiceReadinessReport reloaded = Json.parse(dumped, ServiceReadinessReport.class);
        assertEquals(report.service().name(), reloaded.service().name());
        assertEquals(report.verdict().ready(), reloaded.verdict().ready());
    }

    // ── Required-field validation on nested records ──────────

    @Test
    @DisplayName("ServiceInfo rejects null required fields")
    void serviceInfoRejectsNullFields() {
        assertThrows(IllegalArgumentException.class,
                () -> new ServiceInfo(null, "1.0.0", "qa"));
        assertThrows(IllegalArgumentException.class,
                () -> new ServiceInfo("svc", null, "qa"));
        assertThrows(IllegalArgumentException.class,
                () -> new ServiceInfo("svc", "1.0.0", null));
    }

    @Test
    @DisplayName("DeployRecord rejects null required fields")
    void deployRecordRejectsNullFields() {
        assertThrows(IllegalArgumentException.class,
                () -> new DeployRecord(null, "a", "2026-01-01T00:00:00Z", DeployRecord.Status.SUCCESS));
        assertThrows(IllegalArgumentException.class,
                () -> new DeployRecord("abc", null, "2026-01-01T00:00:00Z", DeployRecord.Status.SUCCESS));
        assertThrows(IllegalArgumentException.class,
                () -> new DeployRecord("abc", "a", null, DeployRecord.Status.SUCCESS));
        assertThrows(IllegalArgumentException.class,
                () -> new DeployRecord("abc", "a", "2026-01-01T00:00:00Z", null));
    }

    @Test
    @DisplayName("EvidenceChunk rejects null required fields but allows null relevance_score")
    void evidenceChunkRejectsNullFields() {
        assertThrows(IllegalArgumentException.class,
                () -> new EvidenceChunk(null, "content", null));
        assertThrows(IllegalArgumentException.class,
                () -> new EvidenceChunk(EvidenceChunk.Source.RAG, null, null));
        // relevance_score is optional/nullable
        assertEquals(EvidenceChunk.Source.RAG,
                new EvidenceChunk(EvidenceChunk.Source.RAG, "content", null).source());
    }

    // ── Native structured output wiring ──────────────────────

    @Test
    @DisplayName("JsonSchemas.responseFormat builds a strict json_schema")
    void jsonSchemasBuildsStrictJsonSchema() {
        var rf = JsonSchemas.responseFormat("build_check", JsonSchemas.BUILD_CHECK);
        assertEquals(org.springframework.ai.openai.api.ResponseFormat.Type.JSON_SCHEMA, rf.getType());
        assertEquals("build_check", rf.getJsonSchema().getName());
        assertEquals(Boolean.TRUE, rf.getJsonSchema().getStrict());
        assertTrue(rf.getJsonSchema().getSchema().containsKey("properties"));
    }

    // ── Helpers ───────────────────────────────────────────────

    private static ServiceReadinessReport loadReport(String filename) {
        try {
            Path path = Path.of("../shared/data", filename);
            String json = Files.readString(path);
            return Json.parse(json, ServiceReadinessReport.class);
        } catch (java.io.IOException e) {
            throw new IllegalStateException("Failed to read " + filename, e);
        }
    }
}
