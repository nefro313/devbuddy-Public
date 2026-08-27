package devbuddy;

import devbuddy.config.AppConfig;
import devbuddy.rag.RagService;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Week 3 — grounded-answer LLM tests (requires OpenRouter API key + Qdrant).
 *
 * <p>Equivalent to the grounded_answer portions of {@code tests/test_rag.py} /
 * {@code tests/test_rag.js}. These make real API calls and require the index
 * to be built, so they're slower than {@link RagTest}.</p>
 *
 * <p>Run: {@code mvn test -Dtest=RagLlmTest}</p>
 */
class RagLlmTest {

    private static AnnotationConfigApplicationContext ctx;
    private static RagService rag;

    @BeforeAll
    static void setUp() {
        ctx = new AnnotationConfigApplicationContext(AppConfig.class);
        rag = ctx.getBean(RagService.class);
        rag.indexDocuments(null, 512, 64);
    }

    @AfterAll
    static void tearDown() {
        if (ctx != null) {
            ctx.close();
        }
    }

    @Test
    @DisplayName("groundedAnswer answers from retrieved context")
    void groundedAnswerUsesContext() {
        String answer = rag.groundedAnswer("What is the SLA for the payment API?", 3, 0.0);
        assertTrue(answer.length() > 10, "Answer is too short");
        String lower = answer.toLowerCase();
        assertTrue(lower.contains("99.95") || lower.contains("sla") || lower.contains("uptime"),
                "Answer doesn't reference the payment API SLA: " + answer.substring(0, Math.min(100, answer.length())));
    }

    @Test
    @DisplayName("groundedAnswerWithChunks returns answer + chunks")
    void groundedAnswerWithChunksReturnsBoth() {
        RagService.GroundedResult result = rag.groundedAnswerWithChunks(
                "What is the SLA for the payment API?", 3, 0.0);
        assertTrue(result.answer().length() > 10);
        assertFalse(result.chunks().isEmpty());
        assertTrue(result.chunks().stream().anyMatch(c -> c.contains("99.95") || c.contains("SLA")),
                "Chunks should contain SLA information");
    }

    @Test
    @DisplayName("out-of-corpus question does not hallucinate")
    void outOfCorpusQuestionSaysNoInformation() {
        String answer = rag.groundedAnswer("What's the revenue forecast for Q4 2028?", 3, 0.0);
        String lower = answer.toLowerCase();
        assertTrue(lower.contains("don't have") || lower.contains("no information"),
                "Model should decline to answer, got: " + answer.substring(0, Math.min(100, answer.length())));
    }
}
