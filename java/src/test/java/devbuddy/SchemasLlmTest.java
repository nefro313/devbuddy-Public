package devbuddy;

import devbuddy.config.AppConfig;
import devbuddy.schemas.BuildCheck;
import devbuddy.service.SchemasService;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Week 2 — analyzePr LLM tests (requires OpenRouter API key).
 *
 * <p>Equivalent to the analyze_pr tests in Python/Node.js.
 * These make real API calls, so they're slower than {@link SchemasTest}.</p>
 *
 * <p>Run: {@code mvn test -Dtest=SchemasLlmTest}</p>
 */
class SchemasLlmTest {

    private static AnnotationConfigApplicationContext ctx;
    private static SchemasService schemas;

    @BeforeAll
    static void setUp() {
        ctx = new AnnotationConfigApplicationContext(AppConfig.class);
        schemas = ctx.getBean(SchemasService.class);
    }

    @AfterAll
    static void tearDown() {
        if (ctx != null) {
            ctx.close();
        }
    }

    @Test
    @DisplayName("analyzePr returns a typed BuildCheck, not prose")
    void analyzePrReturnsTypedObject() {
        String diff = "Fix login bug\n\nChanged auth.py line 42";
        BuildCheck result = schemas.analyzePr("Fix login bug", diff, 0.0, null);

        assertNotNull(result, "Expected BuildCheck, got null");
        assertNotNull(result.project(), "project field is empty");
        assertTrue(java.util.List.of("low", "medium", "high", "critical")
                        .contains(result.severity().value()),
                "Invalid severity: " + result.severity());
        assertNotNull(result.summary(), "summary field is empty");
        assertFalse(result.affectedFiles().isEmpty(), "affected_files is empty");
    }

    @Test
    @DisplayName("is deterministic at temperature=0")
    void deterministicAtZero() {
        String diff = "Fix login bug\n\nChanged auth.py line 42";
        BuildCheck r1 = schemas.analyzePr("Fix login bug", diff, 0.0, null);
        BuildCheck r2 = schemas.analyzePr("Fix login bug", diff, 0.0, null);
        assertEquals(r1.severity(), r2.severity(), "temperature=0 should be deterministic");
    }

    @Test
    @DisplayName("is valid at high temperature (schema = validity, temperature = judgment)")
    void validAtHighTemperature() {
        String diff = "Fix login bug\n\nChanged auth.py line 42";
        BuildCheck result = schemas.analyzePr("Fix login bug", diff, 0.7, null);

        assertNotNull(result, "Expected BuildCheck at temp=0.7, got null");
        assertNotNull(result.project(), "project field is empty");
        assertTrue(java.util.List.of("low", "medium", "high", "critical")
                        .contains(result.severity().value()),
                "Invalid severity: " + result.severity());
        assertNotNull(result.summary(), "summary field is empty");
        assertFalse(result.affectedFiles().isEmpty(), "affected_files is empty");
    }

    @Test
    @DisplayName("works with the sample diff from shared/data")
    void worksWithSampleDiff() throws Exception {
        String diff = Files.readString(Path.of("../shared/data/sample-diff.txt"));
        BuildCheck result = schemas.analyzePr(
                "Fix login redirect loop in auth-service", diff, 0.0, 200);
        assertNotNull(result.project());
        assertNotNull(result.severity());
    }
}
