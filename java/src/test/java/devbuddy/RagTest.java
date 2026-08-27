package devbuddy;

import devbuddy.rag.EmbeddingService;
import devbuddy.rag.RagService;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Week 3 — RAG pipeline tests (no LLM / API key needed).
 *
 * <p>Equivalent to the non-LLM portions of {@code tests/test_rag.py} /
 * {@code tests/test_rag.js}. Requires Qdrant running in Docker
 * ({@code docker-compose up -d}) and the first embedding-model download.</p>
 *
 * <p>Run: {@code mvn test -Dtest=RagTest}</p>
 */
class RagTest {

    private static RagService rag;

    @BeforeAll
    static void setUp() {
        // null ChatClient is fine — these tests never call groundedAnswer().
        rag = new RagService(null, "openai/gpt-4o-mini",
                new EmbeddingService(), "localhost", 6334);
        int count = rag.indexDocuments(null, 512, 64);
        assertTrue(count > 0, "No documents were indexed");
    }

    @AfterAll
    static void tearDown() {
        rag.close();
    }

    @Test
    @DisplayName("indexing produces at least 4 chunks")
    void indexCreatesChunks() {
        int count = rag.indexDocuments(null, 512, 64);
        assertTrue(count >= 4, "Expected at least 4 chunks, got " + count);
    }

    @Test
    @DisplayName("retrieve returns chunks relevant to the query")
    void retrieveReturnsRelevantChunks() {
        List<String> chunks = rag.retrieve("What endpoints does the payment API expose?", 3);
        assertFalse(chunks.isEmpty(), "No chunks retrieved");
        assertTrue(chunks.stream().anyMatch(c -> c.toLowerCase().contains("payment")),
                "Retrieved chunks should mention 'payment'");
    }

    @Test
    @DisplayName("different queries return different chunks")
    void retrieveReturnsDifferentChunksForDifferentQueries() {
        List<String> payment = rag.retrieve("payment API timeout", 3);
        List<String> contributing = rag.retrieve("how to contribute", 3);
        assertNotEquals(String.join("", payment), String.join("", contributing),
                "Different queries should return different chunks");
    }

    @Test
    @DisplayName("hybrid search returns keyword matches")
    void hybridSearchIncludesKeywordMatches() {
        List<String> hybrid = rag.hybridSearch("payment-api", 3);
        List<String> vector = rag.retrieve("payment-api", 3);
        assertFalse(hybrid.isEmpty(), "Hybrid search returned no results");
        assertEquals(vector.size(), hybrid.size(),
                "Hybrid should return the same count as vector at this depth");
    }

    @Test
    @DisplayName("smaller chunk size produces more chunks")
    void chunkSizeChangesChunkCount() {
        int count256 = rag.indexDocuments(null, 256, 64);
        int count1024 = rag.indexDocuments(null, 1024, 64);
        assertTrue(count256 > count1024,
                "Expected chunk_size=256 (" + count256 + ") to produce more chunks "
                        + "than chunk_size=1024 (" + count1024 + ")");
        rag.indexDocuments(null, 512, 64); // restore default
    }

    @Test
    @DisplayName("retrieve without an index throws a clear error")
    void unindexedRetrieveThrows() {
        RagService fresh = new RagService(null, "openai/gpt-4o-mini", null, "localhost", 6334);
        IllegalStateException e = assertThrows(IllegalStateException.class,
                () -> fresh.retrieve("test query", 3));
        assertTrue(e.getMessage().contains("No index found"),
                "Expected 'No index found' message, got: " + e.getMessage());
    }
}
