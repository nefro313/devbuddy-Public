/**
 * Demo 4: The <Sketchpad> Pattern (Chain-of-Thought in Structured Outputs)
 *
 * Modern models are smart enough to catch obvious bugs even without time to think.
 * But if a model outputs a direct verdict as its first token, it is a BLACK BOX.
 * If it gets it wrong, you have no idea why.
 *
 * By adding a `thought_process` string as the VERY FIRST field in your Zod schema,
 * you force the LLM to output its step-by-step reasoning. This provides an AUDIT
 * TRAIL for debugging, evaluations, and human oversight. It's not just about
 * accuracy; it's about observability.
 *
 * Run: node scripts/week-02/demo-04-sketchpad.js
 */
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { z } from "zod";
import { getLlm } from "../../src/llm.js";
import { config } from "../../src/config.js";

// A tricky PR that looks like a simple feature addition (adding a shipping fee),
// but contains a subtle revenue-loss math bug (subtracting instead of adding).
const TRICKY_PR_DIFF = `
PR Title: Add shipping fee for small orders
Description: We are losing margin on small orders. This PR adds a $5 shipping fee to orders under $50.

Files: src/checkout.py

diff --git a/src/checkout.py b/src/checkout.py
@@ -12,6 +12,10 @@
 def calculate_final_total(order):
    total = order.subtotal

+    # Add $5 shipping fee for small orders
+    if total < 50.00:
+        total -= 5.00

    if order.has_vip_pass:
        total *= 0.90

    return total
`;

// ── SCHEMA 1: Direct Verdict (No Sketchpad) ──────────────────
const DirectVerdictSchema = z.object({
  severity: z
    .enum(["low", "medium", "high", "critical"])
    .describe(
      "The impact severity level. 'high' or 'critical' for revenue-loss bugs or security flaws."
    ),
  summary: z.string().describe("Summary of the change"),
});

// ── SCHEMA 2: Reasoned Verdict (With Sketchpad) ──────────────
const ReasonedVerdictSchema = z.object({
  thought_process: z
    .string()
    .describe(
      "Step-by-step reasoning evaluating the diff logic mathematically and practically. Do this FIRST."
    ),
  severity: z
    .enum(["low", "medium", "high", "critical"])
    .describe(
      "The impact severity level. 'high' or 'critical' for revenue-loss bugs or security flaws."
    ),
  summary: z.string().describe("Summary of the change"),
});

const llm = getLlm({ temperature: 0.4 });
const system = new SystemMessage(
  "You are a strict code reviewer. Analyze the PR diff for bugs or logic flaws."
);
const human = new HumanMessage(TRICKY_PR_DIFF);

console.log("=".repeat(75));
console.log("  DEMO 4: The <Sketchpad> Pattern");
console.log("=".repeat(75));
console.log(`  Model: ${config.model}`);

console.log("\n  APPROACH A: Direct Verdict (No Sketchpad)");
console.log("  The model must decide 'severity' on token #1.");
console.log("  " + "-".repeat(55));

const r1 = await llm.withStructuredOutput(DirectVerdictSchema).invoke([system, human]);
console.log(`  Severity: ${r1.severity.toUpperCase()}`);
console.log(`  Summary:  ${r1.summary}`);
console.log(
  "  (The model likely caught the bug. But if it was wrong, we'd have ZERO visibility into why.)"
);

console.log("\n" + "=".repeat(75));

console.log("\n  APPROACH B: Reasoned Verdict (With Sketchpad)");
console.log("  The model generates 'thought_process' first, conditioning its final verdict.");
console.log("  " + "-".repeat(55));

const r2 = await llm.withStructuredOutput(ReasonedVerdictSchema).invoke([system, human]);
console.log("  Thought Process:");
for (const line of r2.thought_process.split(". ")) {
  if (line) console.log(`    - ${line.trim()}`);
}
console.log();
console.log(`  Severity: ${r2.severity.toUpperCase()}`);
console.log(`  Summary:  ${r2.summary}`);
console.log(
  "\n  (Both models got it right, but this one gave us an AUDIT TRAIL. This is how you bridge the 'valid vs. right' gap!)"
);
console.log("=".repeat(75));
