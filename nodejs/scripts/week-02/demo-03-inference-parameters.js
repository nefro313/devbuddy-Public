/**
 * Demo 3: Inference Parameters — Temperature, Max Tokens, Cost
 *
 * Same PR. Same Zod schema. Vary temperature, maxTokens.
 * Shows what changes and what stays the same.
 *
 * Run: node scripts/week-02/demo-03-inference-parameters.js
 */
import { HumanMessage } from "@langchain/core/messages";
import { analyzePr } from "../../src/llm_functions.js";
import { getLlm } from "../../src/llm.js";
import { calculateCost, config } from "../../src/config.js";

const PR_TITLE = "Consolidate error handling across user profile module";
const PR_DIFF = [
  "Moved duplicate try/except blocks from 6 profile endpoints into a shared",
  "error_handler.py decorator. No behavior changes — same errors, same messages.",
  "Added unit tests for the new decorator. This is prep work for the v2 profiles API.",
  "Files: src/profiles/error_handler.py (+80, new), src/profiles/views.py (-120),",
  "       tests/test_error_handler.py (+45, new)",
].join("\n");

console.log("=".repeat(65));
console.log("  Demo 3: Inference Parameters — Temp, Max Tokens, Cost");
console.log("=".repeat(65));
console.log(`  Model: ${config.model}`);
console.log();
console.log(`  INPUT: ${PR_TITLE}`);
for (const line of PR_DIFF.split("\n")) {
  console.log(`         ${line}`);
}
console.log();

// ═══════════════════════════════════════════════════════════════
// Part 1: Temperature — determinism vs. judgment
// ═══════════════════════════════════════════════════════════════
console.log("─".repeat(65));
console.log("  PART 1: Temperature — determinism vs. judgment");
console.log("─".repeat(65));
console.log();

console.log("  temp=0.0 (deterministic) — same input, run twice:");
for (let i = 1; i <= 2; i++) {
  const r = await analyzePr({
    title: PR_TITLE,
    diff: PR_DIFF,
    temperature: 0.0,
    maxTokens: 200,
  });
  console.log(`    run ${i}: severity=${r.severity}  summary="${r.summary}"`);
}
console.log("    → same verdict, consistent phrasing.");
console.log();

console.log("  temp=1.0 (creative) — same input, run twice:");
for (let i = 1; i <= 2; i++) {
  const r = await analyzePr({
    title: PR_TITLE,
    diff: PR_DIFF,
    temperature: 1.0,
    maxTokens: 200,
  });
  console.log(`    run ${i}: severity=${r.severity}  summary="${r.summary}"`);
}
console.log("    → same verdict, but the phrasing drifts more.");
console.log();

console.log("  Key: every run returned a VALID BuildCheck — the schema guarantees");
console.log("  validity at ANY temperature. Temperature only nudges how much the");
console.log("  phrasing varies; on short fields that effect is subtle. temp=0 is a");
console.log("  reproducibility choice (tests, CI, caching), not a correctness rule.");
console.log();

// ═══════════════════════════════════════════════════════════════
// Part 2: Max Tokens — truncation kills structured output
// ═══════════════════════════════════════════════════════════════
console.log("─".repeat(65));
console.log("  PART 2: Max Tokens — cost guard or truncation risk?");
console.log("─".repeat(65));
console.log();

for (const limit of [512, 200, 50, 15, 8]) {
  try {
    const result = await analyzePr({
      title: PR_TITLE,
      diff: PR_DIFF,
      temperature: 0.0,
      maxTokens: limit,
    });
    console.log(`  maxTokens=${String(limit).padStart(3)}: ✅ ${result.severity}`);
  } catch (e) {
    const msg = e.message.replace(/\n/g, " ");
    console.log(`  maxTokens=${String(limit).padStart(3)}: ❌ ${msg}`);
  }
}

console.log();
console.log("  Set maxTokens=512 → safe. Cost ceiling: moderate.");
console.log("  Set maxTokens=200 → still may fail depending on model/provider.");
console.log("  Set maxTokens=8   → truncated. Validation fails.");
console.log("  Rule: maxTokens must fit your schema. Measure, don't guess.");
console.log();

// ═══════════════════════════════════════════════════════════════
// Part 3: Cost at different temperatures
// ═══════════════════════════════════════════════════════════════
console.log("─".repeat(65));
console.log("  PART 3: Cost — same task, different temperatures");
console.log("─".repeat(65));
console.log();

for (const temp of [0.0, 0.7]) {
  const llm = getLlm({ temperature: temp, maxTokens: 200 });
  const start = performance.now();
  const response = await llm.invoke([
    new HumanMessage(`PR: ${PR_TITLE}\nDiff: ${PR_DIFF}`),
  ]);
  const elapsed = (performance.now() - start) / 1000;

  const usage = response.usage_metadata || {};
  const inp = usage.input_tokens || 0;
  const out = usage.output_tokens || 0;
  const cost = calculateCost(inp, out);
  console.log(
    `  temp=${temp}: ${inp}+${out} tokens, ~$${cost.toFixed(6)}, ${elapsed.toFixed(2)}s`
  );
}

console.log();
console.log("  temp=0.0 vs temp=0.7 — cost is similar.");
console.log("  The choice isn't about saving tokens — it's determinism vs judgment.");
console.log();
console.log("=".repeat(65));
console.log("  Inference parameters are architectural decisions, not knobs.");
console.log("=".repeat(65));
