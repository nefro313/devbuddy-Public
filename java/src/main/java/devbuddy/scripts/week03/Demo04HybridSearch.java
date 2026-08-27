package devbuddy.scripts.week03;

import devbuddy.rag.EmbeddingService;
import devbuddy.rag.RagService;

import java.util.List;

/**
 * Week 3 — Demo 4: Hybrid Search — the RRF fusion table.
 *
 * <p>Vector search matches MEANING; BM25 matches EXACT TERMS (IDs, codes,
 * names). Hybrid runs both and merges the rankings with RRF. This demo prints
 * the fusion table so you can see each retriever's rank for every result — and
 * where each side has a blind spot.</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo04HybridSearch}</p>
 */
public class Demo04HybridSearch {

    public static void main(String[] args) {
        // No LLM calls in this demo — build the RAG pipeline directly (no API key needed).
        try (RagService rag = new RagService(null, "openai/gpt-4o-mini",
                new EmbeddingService(), "localhost", 6334)) {
            rag.indexDocuments(null, 512, 64);

            // Add your own queries here to explore the tradeoff.
            String[][] queries = {
                    {"how do I set up DevBuddy?", "natural language"},
                    {"INC-799", "exact ticket ID"},
            };

            System.out.println("=".repeat(72));
            System.out.println("  Demo 4: Hybrid Search — the RRF fusion table");
            System.out.println("=".repeat(72));
            System.out.println();

            System.out.println("  ⏸  PAUSE & PREDICT: for 'INC-799', will vector-only find the");
            System.out.println("     exact ticket? Will hybrid rank it #1? Guess before reading.");
            pause("  ⏸  Press Enter to continue… ");
            System.out.println();

            for (String[] q : queries) {
                String question = q[0];
                String kind = q[1];
                List<String> vec = rag.retrieve(question, 5);
                List<RagService.HybridResult> fused = rag.hybridSearchWithScores(question, 5);

                System.out.println("  Query: \"" + question + "\"   (" + kind + ")");
                System.out.println();

                System.out.println("  ▸ VECTOR ONLY (semantic) — what the vector search alone returns:");
                for (int i = 0; i < vec.size(); i++) {
                    System.out.println("    [" + (i + 1) + "] " + firstLine(vec.get(i)));
                }
                System.out.println();

                System.out.println("  ▸ THE FUSION TABLE — how hybrid re-ranks the results.");
                System.out.println("    vec = rank in the vector top-10, bm25 = rank in the BM25 top-10,");
                System.out.println("    '—' = that retriever never ranked this chunk (a blind spot).");
                System.out.println("    rrf = sum of 1/(" + (int) RagService.RRF_K + " + rank) across both sides.");
                System.out.println();
                for (int i = 0; i < fused.size(); i++) {
                    RagService.HybridResult r = fused.get(i);
                    String vr = r.vecRank() != null ? String.valueOf(r.vecRank()) : "—";
                    String br = r.bm25Rank() != null ? String.valueOf(r.bm25Rank()) : "—";
                    System.out.printf("    [%d] vec=%-3s bm25=%-4s rrf=%.4f   %s%n",
                            i + 1, vr, br, r.rrfScore(), firstLine(r.content()));
                    System.out.println("          source: " + r.source());
                }
                System.out.println();

                // Spell out the math for every row where one retriever had a blind spot.
                boolean anyBlind = fused.stream()
                        .anyMatch(r -> r.vecRank() == null || r.bm25Rank() == null);
                if (anyBlind) {
                    System.out.println("  Blind spots (this is why hybrid exists):");
                    for (RagService.HybridResult r : fused) {
                        if (r.vecRank() != null && r.bm25Rank() != null) {
                            continue;
                        }
                        String vr = r.vecRank() != null ? String.valueOf(r.vecRank()) : "—";
                        String br = r.bm25Rank() != null ? String.valueOf(r.bm25Rank()) : "—";
                        String vc = r.vecRank() != null
                                ? String.format("1/%d = %.4f", (int) (RagService.RRF_K + r.vecRank()), rrf(r.vecRank()))
                                : "nothing (vector missed it)";
                        String bc = r.bm25Rank() != null
                                ? String.format("1/%d = %.4f", (int) (RagService.RRF_K + r.bm25Rank()), rrf(r.bm25Rank()))
                                : "nothing (BM25 missed it)";
                        System.out.println("    • " + firstLine(r.content()));
                        System.out.printf("      vector %s → %s;  BM25 %s → %s;  total rrf = %.4f%n",
                                vr, vc, br, bc, r.rrfScore());
                    }
                    System.out.println();
                }
                System.out.println();
            }

            System.out.println("=".repeat(72));
            System.out.println("  PRACTICAL GUIDE");
            System.out.println("=".repeat(72));
            System.out.println();
            System.out.println("  • Vector-only is fine when users ask natural-language questions");
            System.out.println("    with synonyms and paraphrases (\"how do I set this up?\").");
            System.out.println();
            System.out.println("  • Hybrid earns its keep when queries carry exact tokens:");
            System.out.println("    ticket IDs, error codes, service names, version strings");
            System.out.println("    (\"INC-799\", \"auth-service\", \"v1.8.2\") — terms with no");
            System.out.println("    semantic neighbours that vector ranking buries. It surfaces");
            System.out.println("    them, though RRF may not promote them to #1 when the vector");
            System.out.println("    side strongly disagrees.");
            System.out.println();
            System.out.println("  • RRF needs no tuning (K=" + (int) RagService.RRF_K + " is a good default) and BM25 is");
            System.out.println("    cheap to run offline — hybrid is the safe default in");
            System.out.println("    production retrieval.");
            System.out.println();
            System.out.println("  YOUR TURN:");
            System.out.println("    • Add a query for an exact version string ('v1.8.2') or error");
            System.out.println("      code ('402'). Predict which retriever wins the #1 slot.");
            System.out.println("    • The INC-799 exact match may land below #1 because vector ranked");
            System.out.println("      it low. What change would push it to #1 — and what's the cost?");
            System.out.println("=".repeat(72));
        }
    }

    private static double rrf(int rank) {
        return 1.0 / (RagService.RRF_K + rank);
    }

    private static String firstLine(String text) {
        return text.strip().split("\n")[0];
    }

    private static void pause(String msg) {
        var console = System.console();
        if (console != null) {
            console.readLine(msg);
        }
    }
}
