/**
 * Demo 2: Hallucinate → Ground
 *
 * The system prompt is the guardrail. This demo holds the question AND the
 * retrieved chunks fixed and changes only the system around them, then
 * classifies what the model actually does:
 *
 *   1. OUT-OF-CORPUS retrieval       → returns its best (irrelevant) guess
 *   2. OUT-OF-CORPUS + relevance gate → 0 chunks: "no match" is first-class
 *   3. OUT-OF-CORPUS + guardrail      → expected: the model declines
 *   4. OUT-OF-CORPUS, no guardrail    → may refuse or invent (read Verdict:)
 *   5. IN-CORPUS + guardrail          → expected: answers from the chunks
 *
 * The demo prints a Verdict for each answer instead of assuming a narrative —
 * the actual behaviour depends on the model in .env, so classify, don't assert.
 *
 * Run: node scripts/week-03/demo-02-hallucinate-ground.js
 */
import readline from "readline/promises";
import { stdin as input, stdout as output } from "process";
import {
  NO_GUARDRAIL_PROMPT,
  SYSTEM_PROMPT,
  answerWithContext,
  indexDocuments,
  retrieveWithSources,
} from "../../src/rag.js";

const OUT_OF_CORPUS = "What's the revenue forecast for Q4 2028?";
const IN_CORPUS = "How do I contribute code to DevBuddy?";
const K = 3;
const BORDER = "=".repeat(72);

async function pause(msg = "  ⏸  Press Enter to continue… ") {
  if (!process.stdin.isTTY) return;
  const rl = readline.createInterface({ input, output });
  await rl.question(msg);
  rl.close();
}

function classifyAnswer(answer, chunks) {
  /** Classify what the model actually did, instead of asserting a narrative. */
  const joined = chunks.join("\n").toLowerCase();
  const low = answer.toLowerCase();
  if (
    [
      "don't have information",
      "don't have any information",
      "do not have information",
      "does not contain",
      "no information",
      "no financial",
      "i don't know",
      "cannot answer",
      "can't answer",
    ].some((t) => low.includes(t))
  ) {
    return "REFUSAL — declines to answer";
  }
  if (
    ["revenue", "forecast", "2028", "q4"].some((t) => low.includes(t)) &&
    !joined.includes("2028")
  ) {
    return "HALLUCINATION — claims something the context never mentions";
  }
  return "GROUNDED / OTHER — answer appears tied to context";
}

console.log(BORDER);
console.log("  Demo 2: Hallucinate → Ground");
console.log(BORDER);
console.log();

await indexDocuments(null, 512, 64);
console.log("  ✅ Index ready");
console.log();

// ── The out-of-corpus retrieval ───────────────────────────────
// WHY does the retriever return "random" info for an out-of-corpus
// question ("Q4 2028 revenue") instead of nothing?
//
// Because vector search is a top-k nearest-neighbour query: it ALWAYS
// returns k chunks and has no "not found" concept and no relevance
// cutoff. For this question the query vector points into an empty
// region of vector space, so the "nearest" chunks are still far away
// (see the scores printed below — roughly 0.27 / 0.23 / 0.21, versus
// ~0.35+ for an in-corpus question) and happen to be about payments,
// incidents and SLAs.
console.log(`  Out-of-corpus question: "${OUT_OF_CORPUS}"`);
console.log();
console.log(`  The retriever always returns its top-${K} chunks — even when none`);
console.log("  of them answer the question:");
console.log();
const chunks = await retrieveWithSources(OUT_OF_CORPUS, K);
chunks.forEach((chunk, i) => {
  console.log(`  [${i + 1}] ${chunk.source}  (score=${chunk.score.toFixed(3)})`);
  console.log(`      ${chunk.content}`);
  console.log();
});
console.log('  None of these mention Q4 2028 revenue. Retrieval can\'t return');
console.log('  "nothing" — it returns its best (irrelevant) guess.');
console.log();

// ── The relevance gate ────────────────────────────────────────
console.log("  ── The relevance gate (minScore) ────────────────────────");
console.log();
console.log("  Now set a cutoff: minScore=0.35. The same query returns");
const gated = await retrieveWithSources(OUT_OF_CORPUS, K, 0.35);
console.log(`  ${gated.length} chunk(s) — 'no match' becomes a first-class answer`);
console.log("  instead of a best guess.");
console.log();

// ── With the guardrail ────────────────────────────────────────
console.log("  ── With the guardrail ───────────────────────────────────");
console.log();
console.log("  The system prompt tells the model to decline when the context");
console.log("  doesn't contain the answer:");
console.log();
for (const line of SYSTEM_PROMPT.replace(
  "{context}",
  `<the ${K} chunks above>`
).split("\n")) {
  console.log(`  │ ${line}`);
}
console.log();
const guarded = await answerWithContext(
  OUT_OF_CORPUS,
  chunks.map((c) => c.content),
  SYSTEM_PROMPT
);
console.log(`  Answer: ${guarded}`);
console.log(`  Verdict: ${classifyAnswer(guarded, chunks.map((c) => c.content))}`);
console.log();

// ── Without the guardrail ─────────────────────────────────────
console.log("  ── Without the guardrail ────────────────────────────────");
console.log();
console.log("  Same question, same chunks — but the prompt no longer grounds the");
console.log("  model to the context and invites it to make assumptions.");
console.log();
console.log("  ⏸  PAUSE & PREDICT: will it invent an answer, or refuse anyway?");
await pause();
console.log();
for (const line of NO_GUARDRAIL_PROMPT.replace(
  "{context}",
  `<the ${K} chunks above>`
).split("\n")) {
  console.log(`  │ ${line}`);
}
console.log();
const unguarded = await answerWithContext(
  OUT_OF_CORPUS,
  chunks.map((c) => c.content),
  NO_GUARDRAIL_PROMPT
);
console.log(`  Answer: ${unguarded}`);
console.log(`  Verdict: ${classifyAnswer(unguarded, chunks.map((c) => c.content))}`);
console.log();

// ── In-corpus ─────────────────────────────────────────────────
console.log("  ── In-corpus (grounded) ─────────────────────────────────");
console.log();
console.log(`  Question: "${IN_CORPUS}"`);
console.log();
const groundedChunks = await retrieveWithSources(IN_CORPUS, K);
groundedChunks.forEach((chunk, i) => {
  console.log(`  [${i + 1}] ${chunk.source}  (score=${chunk.score.toFixed(3)})`);
  console.log(`      ${chunk.content}`);
  console.log();
});
const grounded = await answerWithContext(
  IN_CORPUS,
  groundedChunks.map((c) => c.content),
  SYSTEM_PROMPT
);
console.log(`  Answer: ${grounded}`);
console.log(
  `  Verdict: ${classifyAnswer(grounded, groundedChunks.map((c) => c.content))}`
);
console.log();

console.log(BORDER);
console.log("  Same retriever. Same chunks. Only the prompt — or the score");
console.log("  cutoff — changed. Read the Verdict lines above: with the current");
console.log("  model the guarded prompt produces a terse refusal, while the");
console.log("  unguarded prompt may refuse more helpfully or — if the model follows");
console.log("  the invitation — invent an answer. Classify, don't assume.");
console.log();
console.log("  YOUR TURN:");
console.log("    • Change OUT_OF_CORPUS to something plausible but absent");
console.log("      (e.g. 'What is the auth-service SLA?') and re-run. Predict");
console.log("      the verdict for each prompt before reading it.");
console.log("    • Point .env at a smaller local model. Does the unguarded");
console.log("      prompt finally hallucinate? Why does model size matter here?");
console.log(BORDER);
