package devbuddy.scripts.week03;

import devbuddy.config.AppConfig;
import devbuddy.rag.RagService;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import java.util.List;

/**
 * Week 3 — Demo 2: Hallucinate → Ground.
 *
 * <p>Holds the question and retrieved chunks fixed, then changes only the
 * system around them: out-of-corpus retrieval, a {@code minScore} relevance
 * gate, the guardrail prompt, the unguarded prompt, and an in-corpus
 * question. Each answer gets a {@code Verdict:} line that classifies what the
 * model actually did — the behaviour depends on the model, so classify, don't
 * assert.</p>
 *
 * <p>Run: {@code mvn -q compile exec:java -Dexec.mainClass=devbuddy.scripts.week03.Demo02HallucinateGround}</p>
 */
public class Demo02HallucinateGround {

    public static void main(String[] args) {
        try (var ctx = new AnnotationConfigApplicationContext(AppConfig.class)) {
            RagService rag = ctx.getBean(RagService.class);

            String outOfCorpus = "What's the revenue forecast for Q4 2028?";
            String inCorpus = "How do I contribute code to DevBuddy?";
            int k = 3;

            System.out.println("=".repeat(72));
            System.out.println("  Demo 2: Hallucinate → Ground");
            System.out.println("=".repeat(72));
            System.out.println();

            rag.indexDocuments(null, 512, 64);
            System.out.println("  ✅ Index ready");
            System.out.println();

            // ── The out-of-corpus retrieval ───────────────────
            // WHY does the retriever return "random" info for an out-of-corpus
            // question ("Q4 2028 revenue") instead of nothing?
            //
            // Because vector search is a top-k nearest-neighbour query: it ALWAYS
            // returns k chunks and has no "not found" concept and no relevance
            // cutoff. For this question the query vector points into an empty
            // region of vector space, so the "nearest" chunks are still far away
            // (see the scores printed below) and happen to be about payments,
            // incidents and SLAs.
            System.out.println("  Out-of-corpus question: \"" + outOfCorpus + "\"");
            System.out.println();
            System.out.println("  The retriever always returns its top-" + k + " chunks — even when none");
            System.out.println("  of them answer the question:");
            System.out.println();

            List<RagService.RetrievedChunk> chunks = rag.retrieveWithSources(outOfCorpus, k);
            for (int i = 0; i < chunks.size(); i++) {
                System.out.printf("  [%d] %s  (score=%.3f)%n", i + 1, chunks.get(i).source(), chunks.get(i).score());
                System.out.println("      " + chunks.get(i).content());
                System.out.println();
            }
            System.out.println("  None of these mention Q4 2028 revenue. Retrieval can't return");
            System.out.println("  \"nothing\" — it returns its best (irrelevant) guess.");
            System.out.println();

            // ── The relevance gate ────────────────────────────
            System.out.println("  ── The relevance gate (minScore) ────────────────────────");
            System.out.println();
            System.out.println("  Now set a cutoff: minScore=0.35. The same query returns");
            List<RagService.RetrievedChunk> gated = rag.retrieveWithSources(outOfCorpus, k, 0.35);
            System.out.println("  " + gated.size() + " chunk(s) — 'no match' becomes a first-class answer");
            System.out.println("  instead of a best guess.");
            System.out.println();

            // ── With the guardrail ────────────────────────────
            System.out.println("  ── With the guardrail ───────────────────────────────────");
            System.out.println();
            System.out.println("  The system prompt tells the model to decline when the context");
            System.out.println("  doesn't contain the answer:");
            System.out.println();
            printPrompt(RagService.SYSTEM_PROMPT.formatted("<the " + k + " chunks above>"));
            System.out.println();
            String guarded = rag.answerWithContext(
                    outOfCorpus, chunkContents(chunks), RagService.SYSTEM_PROMPT, 0.0);
            System.out.println("  Answer: " + guarded);
            System.out.println("  Verdict: " + classifyAnswer(guarded, chunkContents(chunks)));
            System.out.println();

            // ── Without the guardrail ─────────────────────────
            System.out.println("  ── Without the guardrail ────────────────────────────────");
            System.out.println();
            System.out.println("  Same question, same chunks — but the prompt no longer grounds the");
            System.out.println("  model to the context and invites it to make assumptions.");
            System.out.println();
            System.out.println("  ⏸  PAUSE & PREDICT: will it invent an answer, or refuse anyway?");
            pause("  ⏸  Press Enter to continue… ");
            System.out.println();
            printPrompt(RagService.NO_GUARDRAIL_PROMPT.formatted("<the " + k + " chunks above>"));
            System.out.println();
            String unguarded = rag.answerWithContext(
                    outOfCorpus, chunkContents(chunks), RagService.NO_GUARDRAIL_PROMPT, 0.0);
            System.out.println("  Answer: " + unguarded);
            System.out.println("  Verdict: " + classifyAnswer(unguarded, chunkContents(chunks)));
            System.out.println();

            // ── In-corpus ─────────────────────────────────────
            System.out.println("  ── In-corpus (grounded) ─────────────────────────────────");
            System.out.println();
            System.out.println("  Question: \"" + inCorpus + "\"");
            System.out.println();
            List<RagService.RetrievedChunk> groundedChunks = rag.retrieveWithSources(inCorpus, k);
            for (int i = 0; i < groundedChunks.size(); i++) {
                System.out.printf("  [%d] %s  (score=%.3f)%n",
                        i + 1, groundedChunks.get(i).source(), groundedChunks.get(i).score());
                System.out.println("      " + groundedChunks.get(i).content());
                System.out.println();
            }
            String grounded = rag.answerWithContext(
                    inCorpus, chunkContents(groundedChunks), RagService.SYSTEM_PROMPT, 0.0);
            System.out.println("  Answer: " + grounded);
            System.out.println("  Verdict: " + classifyAnswer(grounded, chunkContents(groundedChunks)));
            System.out.println();

            System.out.println("=".repeat(72));
            System.out.println("  Same retriever. Same chunks. Only the prompt — or the score");
            System.out.println("  cutoff — changed. Read the Verdict lines above: with the current");
            System.out.println("  model the guarded prompt produces a terse refusal, while the");
            System.out.println("  unguarded prompt may refuse more helpfully or — if the model follows");
            System.out.println("  the invitation — invent an answer. Classify, don't assume.");
            System.out.println();
            System.out.println("  YOUR TURN:");
            System.out.println("    • Change OUT_OF_CORPUS to something plausible but absent");
            System.out.println("      (e.g. 'What is the auth-service SLA?') and re-run. Predict");
            System.out.println("      the verdict for each prompt before reading it.");
            System.out.println("    • Point .env at a smaller local model. Does the unguarded");
            System.out.println("      prompt finally hallucinate? Why does model size matter here?");
            System.out.println("=".repeat(72));
        }
    }

    private static String classifyAnswer(String answer, List<String> chunks) {
        String joined = String.join("\n", chunks).toLowerCase();
        String low = answer.toLowerCase();
        String[] refusals = {
                "don't have information", "don't have any information",
                "do not have information", "does not contain", "no information",
                "no financial", "i don't know", "cannot answer", "can't answer",
        };
        for (String t : refusals) {
            if (low.contains(t)) {
                return "REFUSAL — declines to answer";
            }
        }
        String[] invented = {"revenue", "forecast", "2028", "q4"};
        boolean mentions = false;
        for (String t : invented) {
            if (low.contains(t)) {
                mentions = true;
                break;
            }
        }
        if (mentions && !joined.contains("2028")) {
            return "HALLUCINATION — claims something the context never mentions";
        }
        return "GROUNDED / OTHER — answer appears tied to context";
    }

    private static List<String> chunkContents(List<RagService.RetrievedChunk> chunks) {
        return chunks.stream().map(RagService.RetrievedChunk::content).toList();
    }

    private static void printPrompt(String prompt) {
        for (String line : prompt.split("\n")) {
            System.out.println("  │ " + line);
        }
    }

    private static void pause(String msg) {
        var console = System.console();
        if (console != null) {
            console.readLine(msg);
        }
    }
}
