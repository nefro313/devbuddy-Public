package devbuddy.scripts.week03;

import devbuddy.config.AppConfig;
import devbuddy.rag.RagService;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Week 3 — Demo 1: Embed → Retrieve → Ground.
 *
 * <p>The full RAG loop, made inspectable: every chunk is printed with its
 * source and score, the query vector is shown, the exact system prompt the
 * model receives is displayed, and two checks separate grounding (precision)
 * from recall (completeness).</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo01EmbedRetrieveGround}</p>
 */
public class Demo01EmbedRetrieveGround {

    private static final Pattern ENDPOINT =
            Pattern.compile("\\b(?:GET|POST|PUT|DELETE|PATCH)\\s+(/[^\\s,`*]+)");

    public static void main(String[] args) throws Exception {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            RagService rag = ctx.getBean(RagService.class);

            String question = "What endpoints does the payment API expose?";
            int k = 4;

            System.out.println("=".repeat(72));
            System.out.println("  Demo 1: Embed → Retrieve → Ground");
            System.out.println("=".repeat(72));
            System.out.println();
            System.out.println("  The RAG loop, step by step:");
            System.out.println("    1. EMBED    — each chunk → a vector (a point in space)");
            System.out.printf("                   model: %s (384-dim vectors)%n", RagService.EMBEDDING_MODEL);
            System.out.println("    2. RETRIEVE — embed the query, return the closest chunks");
            System.out.println("    3. GROUND   — inject those chunks into the prompt, answer");
            System.out.println();
            System.out.println("  Question: " + question);
            System.out.println();

            // ── Step 1: Embed + index ─────────────────────────
            System.out.println("  ── Step 1: Embed & index ────────────────────────────────");
            System.out.println();
            System.out.println("  Each document is split into chunks. Each chunk is embedded");
            System.out.println("  into a vector and stored in Qdrant.");
            System.out.println();
            int count = rag.indexDocuments(null, 512, 64);
            System.out.println("  ✅ Indexed " + count + " chunks → collection 'devbuddy-docs'");
            System.out.println();

            // ── Step 2: Retrieve ──────────────────────────────
            System.out.println("  ── Step 2: Retrieve (top-k by vector similarity) ────────");
            System.out.println();
            System.out.println("  The request — the query — is also embedded into a vector:");
            System.out.println();
            System.out.println("    \"" + question + "\"");
            float[] queryVector = rag.embedText(question);
            StringBuilder preview = new StringBuilder("[");
            for (int i = 0; i < Math.min(5, queryVector.length); i++) {
                if (i > 0) {
                    preview.append(", ");
                }
                preview.append(String.format("%.4f", queryVector[i]));
            }
            preview.append("] ...");
            System.out.println("    → " + queryVector.length + "-dim vector: " + preview);
            System.out.println();
            System.out.println("  Qdrant returns the " + k + " chunks whose vectors are closest to");
            System.out.println("  that query vector, most relevant first. The source and similarity");
            System.out.println("  score of each chunk are shown so you can trace it back:");
            System.out.println();

            List<RagService.RetrievedChunk> chunks = rag.retrieveWithSources(question, k);
            for (int i = 0; i < chunks.size(); i++) {
                RagService.RetrievedChunk c = chunks.get(i);
                System.out.printf("  [%d] %s  (score=%.3f)%n", i + 1, c.source(), c.score());
                System.out.println("      " + c.content());
                System.out.println();
            }

            System.out.println("  ⏸  PAUSE & PREDICT:");
            System.out.println("     The payment API spec actually defines 4 endpoints. Look at the");
            System.out.println("     " + k + " chunks above — which endpoint is MISSING from the retrieval?");
            System.out.println("     Will the answer mention it? Predict, then continue.");
            pause("  ⏸  Press Enter to continue… ");

            // ── Step 3: Ground ────────────────────────────────
            System.out.println("  ── Step 3: Ground (chunks → prompt → LLM) ───────────────");
            System.out.println();
            System.out.println("  The chunks above are injected VERBATIM into the system prompt");
            System.out.println("  as CONTEXT. This is the exact prompt the model receives:");
            System.out.println();
            String promptPreview = RagService.SYSTEM_PROMPT.formatted(
                    chunkContents(chunks).stream().collect(Collectors.joining("\n\n---\n\n")));
            for (String line : promptPreview.split("\n")) {
                System.out.println("  │ " + line);
            }
            System.out.println();
            System.out.println("  ── user message ──");
            System.out.println("  │ " + question);
            System.out.println();

            String answer = rag.groundedAnswerFromChunks(question, chunkContents(chunks), 0.0);
            System.out.println("  ── answer ──");
            System.out.println("  │ " + answer);
            System.out.println();

            // ── Verify ────────────────────────────────────────
            String context = String.join("\n", chunkContents(chunks));
            List<String> claims = extractPaths(answer);

            System.out.println("=".repeat(72));
            System.out.println("  Verify the grounding (automated):");
            if (claims.isEmpty()) {
                System.out.println("  ⚠️  No endpoint paths detected in the answer — verify by hand.");
            } else {
                List<String> ungrounded = claims.stream()
                        .filter(p -> !context.contains(p.replaceAll("\\.$", "")))
                        .toList();
                if (!ungrounded.isEmpty()) {
                    System.out.println("  ❌ " + ungrounded.size() + "/" + claims.size()
                            + " endpoint claim(s) NOT in retrieved context:");
                    for (String p : ungrounded) {
                        System.out.println("      - " + p);
                    }
                } else {
                    System.out.println("  ✅ All " + claims.size()
                            + " endpoint claim(s) appear in the retrieved context.");
                }
            }

            // ── Recall check ──────────────────────────────────
            String specText = Files.readString(Path.of("..", "shared", "data", "payment-api-spec.md"));
            List<String> allEndpoints = extractPaths(specText);
            List<String> missing = allEndpoints.stream()
                    .filter(e -> !context.contains(e.replaceAll("\\.$", "")))
                    .toList();

            System.out.println();
            System.out.println("  Recall check — grounding ≠ completeness:");
            if (!missing.isEmpty()) {
                System.out.println("  ⚠️  " + missing.size() + " of " + allEndpoints.size()
                        + " spec endpoint(s) were never retrieved:");
                for (String e : missing) {
                    System.out.println("      - " + e);
                }
                System.out.println("     The model didn't hallucinate — it never SAW these. This is a");
                System.out.println("     RECALL gap (retrieval missed evidence), not a grounding failure");
                System.out.println("     (answer claims evidence that isn't there). Different bug, different fix.");
            } else {
                System.out.println("  ✅ All " + allEndpoints.size() + " spec endpoint(s) were retrieved.");
            }
            System.out.println("=".repeat(72));
        }
    }

    private static List<String> extractPaths(String text) {
        List<String> out = new ArrayList<>();
        Matcher m = ENDPOINT.matcher(text);
        while (m.find()) {
            out.add(m.group(1));
        }
        return out;
    }

    private static List<String> chunkContents(List<RagService.RetrievedChunk> chunks) {
        return chunks.stream().map(RagService.RetrievedChunk::content).toList();
    }

    private static void pause(String msg) {
        var console = System.console();
        if (console != null) {
            console.readLine(msg);
        }
    }
}
