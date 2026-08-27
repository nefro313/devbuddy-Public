package devbuddy.scripts.week03;

import devbuddy.rag.EmbeddingService;
import devbuddy.rag.RagService;

import java.util.ArrayList;
import java.util.List;

/**
 * Week 3 — Demo 3: Chunking — how chunk size changes what gets retrieved.
 *
 * <p>Indexes the same documents three times — chunk size 256, 512, 1024 — and
 * retrieves the top-3 chunks for the SAME question each time. Only the chunk
 * size changes; the question, the embeddings, and the retriever are identical.</p>
 *
 * <p>Watch two things at each size: how many chunks the index holds, and which
 * documents the retrieved chunks come from (and how long they are).</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo03ChunkSize}</p>
 */
public class Demo03ChunkSize {

    public static void main(String[] args) {
        // No LLM calls in this demo — build the RAG pipeline directly (no API key needed).
        try (RagService rag = new RagService(null, "openai/gpt-4o-mini",
                new EmbeddingService(), "localhost", 6334)) {

            String question = "How do I set up DevBuddy?";
            // The answer to this question lives in CONTRIBUTING.md — so chunks
            // from other files are noise. (A fact about the corpus, not a verdict.)
            String answerDoc = "CONTRIBUTING.md";
            int k = 3;
            int[] sizes = {256, 512, 1024};

            System.out.println("=".repeat(72));
            System.out.println("  Demo 3: Chunk Size — Same Question, Different Retrieval");
            System.out.println("=".repeat(72));
            System.out.println();
            System.out.println("  Question: \"" + question + "\"");
            System.out.println();
            System.out.println("  The documents are indexed three times, once per chunk size.");
            System.out.println("  The question and the retriever do not change — only chunk size.");
            System.out.println();
            System.out.println("  The answer to this question lives in " + answerDoc + ";");
            System.out.println("  chunks from other files are noise.");
            System.out.println();

            // Why do unrelated docs (e.g. payment-api-spec.md) appear in the results?
            //
            // The retriever is a top-k nearest-neighbour search: it must return
            // exactly K chunks and has NO relevance gate. For this question the
            // genuinely close chunks are all in CONTRIBUTING.md (see the scores
            // printed below). Once those run out, slot K gets filled by whatever
            // is vector-closest next — and that is payment-api-spec.md.
            //
            // Chunk size decides HOW the noise leaks in:
            //   • 256 → a payment-api chunk slips into the top-3 next to the right doc.
            //   • 1024 → the whole 828-char payment spec rides along in slot 3.
            //   • 512 → the top-3 all come from CONTRIBUTING.md.
            System.out.println("  ⏸  PAUSE & PREDICT: at which chunk size does a non-CONTRIBUTING");
            System.out.println("     document first leak into the top-3? Guess before reading.");
            pause("  ⏸  Press Enter to continue… ");
            System.out.println();

            List<int[]> summary = new ArrayList<>(); // {size, count, avgLen}

            for (int size : sizes) {
                int count = rag.indexDocuments(null, size, 64);
                List<RagService.RetrievedChunk> chunks = rag.retrieveWithSources(question, k);
                int avgLen = chunks.isEmpty() ? 0
                        : chunks.stream().mapToInt(c -> c.content().length()).sum() / chunks.size();
                summary.add(new int[]{size, count, avgLen});

                System.out.println("  ── chunk_size = " + size + "   (" + count + " chunks indexed) ──");
                System.out.println();
                for (int i = 0; i < chunks.size(); i++) {
                    RagService.RetrievedChunk c = chunks.get(i);
                    String note = c.source().equals(answerDoc) ? "" : "   ← other document";
                    System.out.printf("  [%d] %s  (%d chars, score=%.3f)%s%n",
                            i + 1, c.source(), c.content().length(), c.score(), note);
                    System.out.println("      " + c.content());
                    System.out.println();
                }
                System.out.println();
            }

            // ── Summary ──────────────────────────────────────
            System.out.println("=".repeat(72));
            System.out.println("  SUMMARY");
            System.out.println("=".repeat(72));
            System.out.println();
            System.out.printf("  %-12s %-16s %-20s%n", "chunk_size", "chunks indexed", "avg retrieved len");
            System.out.printf("  %-12s %-16s %-20s%n", "─".repeat(12), "─".repeat(16), "─".repeat(20));
            for (int[] row : summary) {
                System.out.printf("  %-12d %-16d %-20d%n", row[0], row[1], row[2]);
            }
            System.out.println();
            System.out.println("  The tradeoff, in general:");
            System.out.println("    smaller → more chunks, each tighter, but context can be split");
            System.out.println("              (e.g. a heading separated from its body).");
            System.out.println("    larger  → fewer chunks, but unrelated content can ride along");
            System.out.println("              (e.g. a whole payment API spec in a setup answer).");
            System.out.println();
            System.out.println("  Look back at the sources and lengths above and decide where the");
            System.out.println("  balance sits for THESE documents. There is no universal answer.");
            System.out.println();
            System.out.println("  YOUR TURN:");
            System.out.println("    • Change QUESTION to 'What is the payment API SLA?' and re-run.");
            System.out.println("      Which chunk size keeps the answer self-contained? Why?");
            System.out.println("    • Add chunk_size=2048 to SIZES. Predict what happens to the");
            System.out.println("      'unrelated content rides along' problem before you run.");
            System.out.println("=".repeat(72));
        }
    }

    private static void pause(String msg) {
        var console = System.console();
        if (console != null) {
            console.readLine(msg);
        }
    }
}
