/**
 * Demo 4: Hybrid Search — the RRF fusion table
 *
 * Vector search matches MEANING; BM25 matches EXACT TERMS (IDs, codes,
 * names). Hybrid runs both and merges the rankings with RRF. This demo
 * prints the fusion table so you can see each retriever's rank for every
 * result — and where each side has a blind spot.
 *
 * Run: node scripts/week-03/demo-04-hybrid-search.js
 */
import readline from "readline/promises";
import { stdin as input, stdout as output } from "process";
import {
  RRF_K,
  hybridSearchWithScores,
  indexDocuments,
  retrieve,
} from "../../src/rag.js";

await indexDocuments(null, 512, 64);

// Add your own queries here to explore the tradeoff.
const QUERIES = [
  ["how do I set up DevBuddy?", "natural language"],
  ["INC-799", "exact ticket ID"],
];

const firstLine = (text) => text.trim().split("\n")[0];

/** One retriever's contribution to the fused score (0 if it missed the chunk). */
const rrf = (rank) => (rank ? 1.0 / (RRF_K + rank) : 0.0);

async function pause(msg = "  ⏸  Press Enter to continue… ") {
  if (!process.stdin.isTTY) return;
  const rl = readline.createInterface({ input, output });
  await rl.question(msg);
  rl.close();
}

console.log("=".repeat(72));
console.log("  Demo 4: Hybrid Search — the RRF fusion table");
console.log("=".repeat(72));
console.log();

console.log("  ⏸  PAUSE & PREDICT: for 'INC-799', will vector-only find the");
console.log("     exact ticket? Will hybrid rank it #1? Guess before reading.");
await pause();
console.log();

for (const [question, kind] of QUERIES) {
  const vec = await retrieve(question, 5);
  const fused = await hybridSearchWithScores(question, 5);

  console.log(`  Query: "${question}"   (${kind})`);
  console.log();

  console.log("  ▸ VECTOR ONLY (semantic) — what the vector search alone returns:");
  vec.forEach((c, i) => {
    console.log(`    [${i + 1}] ${firstLine(c)}`);
  });
  console.log();

  console.log("  ▸ THE FUSION TABLE — how hybrid re-ranks the results.");
  console.log("    vec = rank in the vector top-10, bm25 = rank in the BM25 top-10,");
  console.log("    '—' = that retriever never ranked this chunk (a blind spot).");
  console.log(`    rrf = sum of 1/(${RRF_K} + rank) across both sides.`);
  console.log();
  fused.forEach((r, i) => {
    const vr = r.vecRank ? String(r.vecRank) : "—";
    const br = r.bm25Rank ? String(r.bm25Rank) : "—";
    console.log(
      `    [${i + 1}] vec=${vr.padEnd(3)} bm25=${br.padEnd(4)} ` +
        `rrf=${r.rrfScore.toFixed(4)}   ${firstLine(r.content)}`
    );
    console.log(`          source: ${r.source}`);
  });
  console.log();

  // Spell out the math for every row where one retriever had a blind spot.
  const blind = fused.filter((r) => !r.vecRank || !r.bm25Rank);
  if (blind.length > 0) {
    console.log("  Blind spots (this is why hybrid exists):");
    for (const r of blind) {
      const vr = r.vecRank ? String(r.vecRank) : "—";
      const br = r.bm25Rank ? String(r.bm25Rank) : "—";
      const vc = r.vecRank
        ? `1/${RRF_K + r.vecRank} = ${rrf(r.vecRank).toFixed(4)}`
        : "nothing (vector missed it)";
      const bc = r.bm25Rank
        ? `1/${RRF_K + r.bm25Rank} = ${rrf(r.bm25Rank).toFixed(4)}`
        : "nothing (BM25 missed it)";
      console.log(`    • ${firstLine(r.content)}`);
      console.log(
        `      vector ${vr} → ${vc};  BM25 ${br} → ${bc};  ` +
          `total rrf = ${r.rrfScore.toFixed(4)}`
      );
    }
    console.log();
  }
  console.log();
}

console.log("=".repeat(72));
console.log("  PRACTICAL GUIDE");
console.log("=".repeat(72));
console.log();
console.log("  • Vector-only is fine when users ask natural-language questions");
console.log('    with synonyms and paraphrases ("how do I set this up?").');
console.log();
console.log("  • Hybrid earns its keep when queries carry exact tokens:");
console.log("    ticket IDs, error codes, service names, version strings");
console.log('    ("INC-799", "auth-service", "v1.8.2") — terms with no');
console.log("    semantic neighbours that vector ranking buries. It surfaces");
console.log("    them, though RRF may not promote them to #1 when the vector");
console.log("    side strongly disagrees.");
console.log();
console.log(`  • RRF needs no tuning (K=${RRF_K} is a good default) and BM25 is`);
console.log("    cheap to run offline — hybrid is the safe default in");
console.log("    production retrieval.");
console.log();
console.log("  YOUR TURN:");
console.log("    • Add a query for an exact version string ('v1.8.2') or error");
console.log("      code ('402'). Predict which retriever wins the #1 slot.");
console.log("    • The INC-799 exact match may land below #1 because vector ranked");
console.log("      it low. What change would push it to #1 — and what's the cost?");
console.log("=".repeat(72));
