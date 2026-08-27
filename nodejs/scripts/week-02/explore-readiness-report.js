/**
 * Week 2 — Validate a ServiceReadinessReport from mock data.
 *
 * Loads one JSON scenario and validates it against the schema.
 * This is your starting point. Your self-learning assignment is below.
 *
 * Run: node scripts/week-02/explore-readiness-report.js
 */
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { ServiceReadinessReportSchema } from "../../src/schemas.js";
import { config } from "../../src/config.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = resolve(__dirname, "..", "..", "..", "shared", "data");

console.log("=".repeat(70));
console.log("  ServiceReadinessReport — Reference Validation");
console.log("=".repeat(70));
console.log(`  Model: ${config.model}`);
console.log();

// ── Reference: healthy scenario ───────────────────────────────
const path = resolve(DATA_DIR, "service-readiness-healthy.json");
console.log(`  Loading ${path}...`);

const data = JSON.parse(readFileSync(path, "utf-8"));

const report = ServiceReadinessReportSchema.parse(data);
console.log(`  ✅ Validated — ${report.constructor.name}(`);
console.log(`       service.name   = ${report.service.name}`);
console.log(`       service.version= ${report.service.version}`);
console.log(`       build.status   = ${report.build.status}`);
console.log(
  `       deploy.history = ${report.deployment.recent_deploys.length} deploys`
);
console.log(`       verdict.ready  = ${report.verdict.ready}`);
console.log(`       verdict.conf   = ${report.verdict.confidence}`);
console.log(
  `       blockers       = [${report.verdict.blockers.join(", ")}]`
);
console.log(`       evidence       = ${report.evidence.length} chunks`);
console.log("     )");
console.log();

// ═══════════════════════════════════════════════════════════════════
// TAKE-HOME ASSIGNMENT
// ═══════════════════════════════════════════════════════════════════
//
// PART A — Load the other two scenarios:
//   1. Extend this script to also load and validate:
//      shared/data/service-readiness-degraded.json
//      shared/data/service-readiness-unknown.json
//   2. Tests are already in tests/test_schemas.js
//      (the degraded and unknown scenario tests are provided)
//
// PART B — LLM integration:
//   Use generateReadinessReport() from src/llm_functions.js to feed
//   the mock data to the LLM and get back a typed report.
//
//   Example:
//
//     import { generateReadinessReport } from
//       '../../src/llm_functions.js';
//
//     const data = JSON.parse(
//       readFileSync('../../shared/data/
//         service-readiness-healthy.json', 'utf-8'));
//
//     const report = await generateReadinessReport({
//       serviceName: data.service.name,
//       buildData: data.build,
//       deployData: data.deployment,
//       temperature: 0.0,
//     });
//
//     console.log(JSON.stringify(report, null, 2));
//
//   Run this for all 3 scenarios. Compare the LLM's verdict
//   to the hand-written JSON — does the model agree? Where
//   does it differ? What would you change in the system prompt?
