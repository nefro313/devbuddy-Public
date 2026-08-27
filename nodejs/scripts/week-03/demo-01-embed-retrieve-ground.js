/**
 * Demo 1: Embed → Retrieve → Ground
 *
 * The full RAG loop, made inspectable:
 *
 *   1. EMBED    — every chunk becomes a vector (a point in space)
 *   2. RETRIEVE — the query is embedded, the closest chunks are returned
 *   3. GROUND   — those SAME chunks are injected into the prompt, and the
 *                 LLM must answer from them
 *
 * The point of this demo is not just to see an answer — it is to see the
 * evidence. Every chunk that grounds the answer is printed with its source
 * and score, the prompt the model actually receives is shown, and two checks
 * separate grounding (precision) from recall (completeness).
 *
 * Run: node scripts/week-03/demo-01-embed-retrieve-ground.js
 */
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import readline from "readline/promises";
import { stdin as input, stdout as output } from "process";
import {
  EMBEDDING_MODEL,
  SYSTEM_PROMPT,
  embedText,
  groundedAnswerFromChunks,
  indexDocuments,
  retrieveWithSources,
} from "../../src/rag.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SPEC_PATH = resolve(__dirname, "../../../shared/data/payment-api-spec.md");

const QUESTION = "What endpoints does the payment API expose?";
const K = 4;
const BORDER = "=".repeat(72);

async function pause(msg = "  ⏸  Press Enter to continue… ") {
  if (!process.stdin.isTTY) return;
  const rl = readline.createInterface({ input, output });
  await rl.question(msg);
  rl.close();
}

console.log(BORDER);
console.log("  Demo 1: Embed → Retrieve → Ground");
console.log(BORDER);
console.log();
console.log("  The RAG loop, step by step:");
console.log("    1. EMBED    — each chunk → a vector (a point in space)");
console.log(`                   model: ${EMBEDDING_MODEL} (384-dim vectors)`);
console.log("    2. RETRIEVE — embed the query, return the closest chunks");
console.log("    3. GROUND   — inject those chunks into the prompt, answer");
console.log();
console.log(`  Question: ${QUESTION}`);
console.log();

// ── Step 1: Embed + index ─────────────────────────────────────
console.log("  ── Step 1: Embed & index ────────────────────────────────");
console.log();
console.log("  Each document is split into chunks. Each chunk is embedded");
console.log("  into a vector and stored in Qdrant.");
console.log();
const count = await indexDocuments(null, 512, 64);
console.log(`  ✅ Indexed ${count} chunks → collection 'devbuddy-docs'`);
console.log();

// ── Step 2: Retrieve ──────────────────────────────────────────
console.log("  ── Step 2: Retrieve (top-k by vector similarity) ────────");
console.log();
console.log("  The request — the query — is also embedded into a vector:");
console.log();
console.log(`    "${QUESTION}"`);
const queryVector = await embedText(QUESTION);
const preview = queryVector
  .slice(0, 5)
  .map((v) => Math.round(v * 10000) / 10000);
console.log(
  `    → ${queryVector.length}-dim vector: ${JSON.stringify(preview)} ...`
);
console.log();
console.log(`  Qdrant returns the ${K} chunks whose vectors are closest to`);
console.log("  that query vector, most relevant first. The source and similarity");
console.log("  score of each chunk are shown so you can trace it back:");
console.log();
const chunks = await retrieveWithSources(QUESTION, K);
chunks.forEach((chunk, i) => {
  console.log(`  [${i + 1}] ${chunk.source}  (score=${chunk.score.toFixed(3)})`);
  console.log(`      ${chunk.content}`);
  console.log();
});

console.log("  ⏸  PAUSE & PREDICT:");
console.log("     The payment API spec actually defines 4 endpoints. Look at the");
console.log(`     ${K} chunks above — which endpoint is MISSING from the retrieval?`);
console.log("     Will the answer mention it? Predict, then continue.");
await pause();
console.log();

// ── Step 3: Ground ────────────────────────────────────────────
console.log("  ── Step 3: Ground (chunks → prompt → LLM) ───────────────");
console.log();
console.log("  The chunks above are injected VERBATIM into the system prompt");
console.log("  as CONTEXT. This is the exact prompt the model receives:");
console.log();
const promptPreview = SYSTEM_PROMPT.replace(
  "{context}",
  chunks.map((c) => c.content).join("\n\n---\n\n")
);
for (const line of promptPreview.split("\n")) {
  console.log(`  │ ${line}`);
}
console.log();
console.log("  ── user message ──");
console.log(`  │ ${QUESTION}`);
console.log();

const answer = await groundedAnswerFromChunks(
  QUESTION,
  chunks.map((c) => c.content),
  0.0
);
console.log("  ── answer ──");
console.log(`  │ ${answer}`);
console.log();

// ── Verify ────────────────────────────────────────────────────
const context = chunks.map((c) => c.content).join("\n");
const claims = [
  ...answer.matchAll(/\b(?:GET|POST|PUT|DELETE|PATCH)\s+(\/[^\s,`*]+)/g),
].map((m) => m[1]);

console.log(BORDER);
console.log("  Verify the grounding (automated):");
if (claims.length === 0) {
  console.log("  ⚠️  No endpoint paths detected in the answer — verify by hand.");
} else {
  const ungrounded = claims.filter((p) => !context.includes(p.replace(/\.$/, "")));
  if (ungrounded.length) {
    console.log(
      `  ❌ ${ungrounded.length}/${claims.length} endpoint claim(s) NOT in retrieved context:`
    );
    ungrounded.forEach((p) => console.log(`      - ${p}`));
  } else {
    console.log(
      `  ✅ All ${claims.length} endpoint claim(s) appear in the retrieved context.`
    );
  }
}

// ── Recall check ──────────────────────────────────────────────
const specText = readFileSync(SPEC_PATH, "utf-8");
const allEndpoints = [
  ...specText.matchAll(/\b(?:GET|POST|PUT|DELETE|PATCH)\s+(\/[^\s,`*]+)/g),
].map((m) => m[1]);
const missing = allEndpoints.filter((e) => !context.includes(e.replace(/\.$/, "")));

console.log();
console.log("  Recall check — grounding ≠ completeness:");
if (missing.length) {
  console.log(
    `  ⚠️  ${missing.length} of ${allEndpoints.length} spec endpoint(s) were never retrieved:`
  );
  missing.forEach((e) => console.log(`      - ${e}`));
  console.log("     The model didn't hallucinate — it never SAW these. This is a");
  console.log("     RECALL gap (retrieval missed evidence), not a grounding failure");
  console.log("     (answer claims evidence that isn't there). Different bug, different fix.");
} else {
  console.log(`  ✅ All ${allEndpoints.length} spec endpoint(s) were retrieved.`);
}
console.log(BORDER);
