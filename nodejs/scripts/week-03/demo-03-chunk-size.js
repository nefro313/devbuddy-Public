/**
 * Demo 3: Chunking — how chunk size changes what gets retrieved
 *
 * Indexes the same documents three times — chunk size 256, 512, 1024 — and
 * retrieves the top-3 chunks for the SAME question each time. Only the chunk
 * size changes; the question, the embeddings, and the retriever are identical.
 *
 * Watch two things at each size:
 *   • how many chunks the index holds (smaller chunks → more chunks)
 *   • which documents the retrieved chunks come from, and how long they are
 *
 * Run: node scripts/week-03/demo-03-chunk-size.js
 */
import readline from "readline/promises";
import { stdin as input, stdout as output } from "process";
import { indexDocuments, retrieveWithSources } from "../../src/rag.js";

const QUESTION = "How do I set up DevBuddy?";
// The answer to this question lives in CONTRIBUTING.md — so chunks from
// other files are noise. (This is a fact about the corpus, not a verdict.)
const ANSWER_DOC = "CONTRIBUTING.md";
const K = 3;
const SIZES = [256, 512, 1024];

async function pause(msg = "  ⏸  Press Enter to continue… ") {
  if (!process.stdin.isTTY) return;
  const rl = readline.createInterface({ input, output });
  await rl.question(msg);
  rl.close();
}

console.log("=".repeat(72));
console.log("  Demo 3: Chunk Size — Same Question, Different Retrieval");
console.log("=".repeat(72));
console.log();
console.log(`  Question: "${QUESTION}"`);
console.log();
console.log("  The documents are indexed three times, once per chunk size.");
console.log("  The question and the retriever do not change — only chunk size.");
console.log();
console.log(`  The answer to this question lives in ${ANSWER_DOC};`);
console.log("  chunks from other files are noise.");
console.log();

// Why do unrelated docs (e.g. payment-api-spec.md) appear in the results?
//
// The retriever is a top-k nearest-neighbour search: it must return exactly
// K chunks and has NO relevance gate. For this question the genuinely close
// chunks are all in CONTRIBUTING.md (see the scores printed below). Once
// those run out, slot K gets filled by whatever is vector-closest next — and
// that is payment-api-spec.md.
//
// "Closest in embedding space" ≠ "topically relevant". The score cliff is
// the retriever's way of saying "best I have left".
//
// Chunk size decides HOW the noise leaks in:
//   • 256 → a payment-api chunk slips into the top-3 next to the right doc.
//   • 1024 → the whole 828-char payment spec rides along in slot 3.
//   • 512 → the top-3 all come from CONTRIBUTING.md.
console.log("  ⏸  PAUSE & PREDICT: at which chunk size does a non-CONTRIBUTING");
console.log("     document first leak into the top-3? Guess before reading.");
await pause();
console.log();

const summary = [];

for (const size of SIZES) {
  const count = await indexDocuments(null, size, 64);
  const chunks = await retrieveWithSources(QUESTION, K);
  const avgLen = chunks.length
    ? Math.floor(
        chunks.reduce((sum, c) => sum + c.content.length, 0) / chunks.length
      )
    : 0;

  summary.push({ size, count, avgLen });

  console.log(`  ── chunk_size = ${size}   (${count} chunks indexed) ──`);
  console.log();
  chunks.forEach((chunk, i) => {
    const note = chunk.source === ANSWER_DOC ? "" : "   ← other document";
    console.log(
      `  [${i + 1}] ${chunk.source}  (${chunk.content.length} chars, score=${chunk.score.toFixed(3)})${note}`
    );
    console.log(`      ${chunk.content}`);
    console.log();
  });
  console.log();
}

// ── Summary ──────────────────────────────────────────────────
console.log("=".repeat(72));
console.log("  SUMMARY");
console.log("=".repeat(72));
console.log();
console.log(
  `  ${"chunk_size".padEnd(12)} ${"chunks indexed".padEnd(16)} ${"avg retrieved len".padEnd(20)}`
);
console.log(
  `  ${"─".repeat(12)} ${"─".repeat(16)} ${"─".repeat(20)}`
);
for (const { size, count, avgLen } of summary) {
  console.log(
    `  ${String(size).padEnd(12)} ${String(count).padEnd(16)} ${String(avgLen).padEnd(20)}`
  );
}
console.log();
console.log("  The tradeoff, in general:");
console.log("    smaller → more chunks, each tighter, but context can be split");
console.log("              (e.g. a heading separated from its body).");
console.log("    larger  → fewer chunks, but unrelated content can ride along");
console.log("              (e.g. a whole payment API spec in a setup answer).");
console.log();
console.log("  Look back at the sources and lengths above and decide where the");
console.log("  balance sits for THESE documents. There is no universal answer.");
console.log();
console.log("  YOUR TURN:");
console.log("    • Change QUESTION to 'What is the payment API SLA?' and re-run.");
console.log("      Which chunk size keeps the answer self-contained? Why?");
console.log("    • Add chunk_size=2048 to SIZES. Predict what happens to the");
console.log("      'unrelated content rides along' problem before you run.");
console.log("=".repeat(72));
