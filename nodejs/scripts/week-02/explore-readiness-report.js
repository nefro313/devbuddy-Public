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

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = resolve(__dirname, "..", "..", "..", "shared", "data");

console.log("=".repeat(70));
console.log("  ServiceReadinessReport — Reference Validation");
console.log("=".repeat(70));
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
console.log("─".repeat(70));
console.log("  TAKE-HOME ASSIGNMENT");
console.log("─".repeat(70));
console.log();
console.log("  PART A — Load the other two scenarios:");
console.log("    1. Extend this script to also load and validate:");
console.log("       shared/data/service-readiness-degraded.json");
console.log("       shared/data/service-readiness-unknown.json");
console.log("    2. Tests are already in tests/test_schemas.js");
console.log("       (the degraded and unknown scenario tests are provided)");
console.log();
console.log("  PART B — LLM integration:");
console.log("    Use generateReadinessReport() from src/schemas.js to feed");
console.log("    the mock data to the LLM and get back a typed report.");
console.log();
console.log("    Example:");
console.log();
console.log("    import { generateReadinessReport } from");
console.log("      '../../src/schemas.js';");
console.log();
console.log("    const data = JSON.parse(");
console.log("      readFileSync('../../shared/data/");
console.log("        service-readiness-healthy.json', 'utf-8'));");
console.log();
console.log("    const report = await generateReadinessReport({");
console.log("      serviceName: data.service.name,");
console.log("      buildData: data.build,");
console.log("      deployData: data.deployment,");
console.log("      temperature: 0.0,");
console.log("    });");
console.log();
console.log("    console.log(JSON.stringify(report, null, 2));");
console.log();
console.log("    Run this for all 3 scenarios. Compare the LLM's verdict");
console.log("    to the hand-written JSON — does the model agree? Where");
console.log("    does it differ? What would you change in the system prompt?");
console.log("─".repeat(70));
