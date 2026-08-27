/**
 * Demo 6: Prompt Engineering + Promptfoo Evaluation
 *
 * Same PR, same Zod schema, three prompt variants:
 * - zero-shot
 * - few-shot
 * - chain-of-thought
 *
 * Run: node scripts/week-02/demo-06-prompt-engineering.js
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { analyzePrWithPrompt } from "../../src/llm_functions.js";
import { config } from "../../src/config.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const promptDir = path.resolve(__dirname, "../../../shared/prompts");

const PR_TITLE = "Fix login redirect loop in auth-service";
const PR_DIFF = [
  "Updated session token validation in auth.py. Expired tokens now return 401 instead of looping.",
  "Files: src/auth.py, tests/test_auth.py",
].join("\n");

function loadPrompt(name) {
  return fs.readFileSync(path.join(promptDir, `${name}.txt`), "utf8").trim();
}

function printResult(label, result) {
  console.log(`\n[${label}]`);
  console.log(`  project: ${result.project}`);
  console.log(`  severity: ${result.severity}`);
  console.log(`  summary: ${result.summary}`);
  console.log(`  affected_files: ${JSON.stringify(result.affected_files)}`);
}

console.log("=".repeat(80));
console.log("  Demo 6: Prompt Engineering + Promptfoo Evaluation");
console.log("=".repeat(80));
console.log(`  Model: ${config.model}`);
console.log("  Task: same PR, same schema, different prompt strategy");
console.log();

for (const [name, template] of Object.entries({
  "zero-shot": loadPrompt("zero-shot"),
  "few-shot": loadPrompt("few-shot"),
  "chain-of-thought": loadPrompt("chain-of-thought"),
})) {
  try {
    const result = await analyzePrWithPrompt({
      title: PR_TITLE,
      diff: PR_DIFF,
      promptTemplate: template,
      temperature: 0.0,
      maxTokens: 512,
    });
    printResult(name, result);
  } catch (error) {
    console.log(`\n[${name}] ERROR: ${error.message}`);
  }
}

console.log("\n" + "-".repeat(80));
console.log("  Why this matters:");
console.log("  - zero-shot is the shortest, but often least robust");
console.log("  - few-shot adds examples and improves format adherence");
console.log("  - chain-of-thought may improve reasoning but can be verbose");
console.log("  Promptfoo helps compare these systematically across models and prompts.");
console.log("-".repeat(80));
