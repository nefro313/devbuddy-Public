/**
 * Demo 1: Unstructured request → crash, then Schema → guaranteed.
 *
 * The moderator's "Demo 1": ask the LLM for the fields you want — but with NO
 * schema. The model gives you those fields back as prose, so JSON.parse()
 * crashes. Then add a schema constraint (analyzePr) and get a typed object
 * that ALWAYS parses. A request is not a contract.
 *
 * Run: node scripts/week-02/demo-01-prose-vs-structured.js
 */
import { HumanMessage } from "@langchain/core/messages";
import { getLlm } from "../../src/llm.js";
import { analyzePr } from "../../src/llm_functions.js";
import { config } from "../../src/config.js";

const PR_TITLE = "Fix login redirect loop in auth-service";
const PR_DIFF = [
  "Changed session token validation in src/auth.py lines 42-58.",
  "Previously expired tokens caused infinite redirect for 15% of users.",
  "Now returns 401 with clear error. No DB changes. Rollback: revert commit.",
  "Files: src/auth.py, tests/test_auth.py",
].join("\n");

console.log("=".repeat(70));
console.log("  Demo 1: Prose → crash, then Schema → success");
console.log("=".repeat(70));
console.log(`  Model: ${config.model}`);
console.log();
console.log(`  INPUT: ${PR_TITLE}`);
for (const line of PR_DIFF.split("\n")) {
  console.log(`         ${line}`);
}
console.log();

// ═══════════════════════════════════════════════════════════════
// Step 1: plain prompt → prose
// ═══════════════════════════════════════════════════════════════
console.log("-".repeat(70));
console.log("  STEP 1: ask for the fields (no schema) → prose");
console.log("-".repeat(70));
console.log();

const llm = getLlm({ temperature: 0.0 });
const raw = (
  await llm.invoke([
    new HumanMessage(
      `Analyze this PR and return its severity, a one-sentence summary, and the affected files.\n\nPR Title: ${PR_TITLE}\n\nDiff:\n${PR_DIFF}`
    ),
  ])
).content;

console.log("  Raw response:");
for (const line of raw.trim().split("\n")) {
  console.log(`  | ${line}`);
}
console.log();

// ═══════════════════════════════════════════════════════════════
// Step 2: JSON.parse → crash
// ═══════════════════════════════════════════════════════════════
console.log("-".repeat(70));
console.log("  STEP 2: JSON.parse(raw) → crash");
console.log("-".repeat(70));
console.log();

try {
  const data = JSON.parse(raw);
  console.log(`  ✅ parsed unexpectedly: ${Object.keys(data).join(", ")}`);
} catch (e) {
  console.log(`  ❌ CRASHED: ${e.message}`);
  console.log();
  console.log("  You asked for the severity, summary, and affected files.");
  console.log("  The model gave them to you — as prose. With no schema,");
  console.log("  the model picks the format, and it picked prose.");
  console.log("  Free text breaks pipelines. Let's fix it.");
}
console.log();

// ═══════════════════════════════════════════════════════════════
// Step 3: schema constraint → typed object
// ═══════════════════════════════════════════════════════════════
console.log("-".repeat(70));
console.log("  STEP 3: analyzePr (schema-constrained) → typed object");
console.log("-".repeat(70));
console.log();

const result = await analyzePr({
  title: PR_TITLE,
  diff: PR_DIFF,
  temperature: 0.0,
});

console.log(`  type: ${result.constructor.name}  ← typed object, not prose!`);
console.log();
console.log(JSON.stringify(result, null, 2));
console.log();

console.log("=".repeat(70));
console.log("  The LLM is now a typed function.");
console.log("  Input → BuildCheck. Your code consumes it directly.");
console.log("=".repeat(70));
