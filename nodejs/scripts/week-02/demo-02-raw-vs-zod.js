/**
 * Demo 2: Raw JSON Prompting vs. Zod Structured Output
 *
 * WHAT THIS DEMO SHOWS:
 *   Raw JSON prompting is a polite request. The model tries to comply — but
 *   it may add markdown wrappers, conversational text, or invent field names.
 *   Your pipeline breaks.
 *
 *   Zod structured output is a contract. The model is constrained at the
 *   token level. It CANNOT return output that violates the schema.
 *
 * THE SETUP:
 *   Same input (a PR diff). Same temperature (0.0 — deterministic).
 *   Same extraction task. Two approaches.
 *
 * Run: node scripts/week-02/demo-02-raw-vs-zod.js
 */
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { z } from "zod";
import { getLlm } from "../../src/llm.js";

// ═══════════════════════════════════════════════════════════════
// THE INPUT — same for both approaches
// ═══════════════════════════════════════════════════════════════
const diffInput = `Fix login redirect loop in auth-service (PROJ-421)
Changed session token validation in src/auth.py lines 42-58.
Previously expired tokens caused infinite redirect for 15% of users.
Now returns 401 with clear error. No DB changes. Rollback: revert commit.
Files: src/auth.py, tests/test_auth.py`;

// ═══════════════════════════════════════════════════════════════
// THE SCHEMA — the shape we want the data in
// ═══════════════════════════════════════════════════════════════
const ChangeSchema = z.object({
  type: z
    .enum(["bug", "feature", "refactor", "hotfix"])
    .describe("The category of the change"),
  severity: z
    .enum(["low", "medium", "high", "critical"])
    .describe("The impact severity level"),
  ticket: z
    .string()
    .nullable()
    .optional()
    .describe(
      "The ticket ID (e.g., PROJ-123) if present in the diff, else null"
    ),
});

const DetailsSchema = z.object({
  summary: z
    .string()
    .describe("A single sentence summary of what changed"),
  root_cause: z
    .string()
    .describe("The underlying issue that caused the problem"),
  user_impact_pct: z
    .number()
    .int()
    .nullable()
    .optional()
    .describe(
      "Percentage of users impacted, as a raw integer (e.g. 15)"
    ),
});

const TechnicalSchema = z.object({
  files_changed: z
    .array(z.string())
    .describe("Exact file paths modified"),
  db_changed: z
    .boolean()
    .describe("Whether any database changes are included"),
  rollback: z
    .string()
    .describe("Instructions on how to revert this change"),
});

const DiffAnalysisSchema = z.object({
  change: ChangeSchema,
  details: DetailsSchema,
  technical: TechnicalSchema,
});

// ═══════════════════════════════════════════════════════════════
// THE DEMO
// ═══════════════════════════════════════════════════════════════
async function runDemo() {
  console.log("=".repeat(75));
  console.log(
    "  DEMO: Raw JSON Prompting (Request) vs. Zod (Contract)"
  );
  console.log("=".repeat(75));
  console.log();
  console.log("  THE INPUT (same for both approaches):");
  console.log("  " + "-".repeat(55));
  for (const line of diffInput.trim().split("\n")) {
    console.log(`  | ${line}`);
  }
  console.log("  " + "-".repeat(55));
  console.log();

  const testTemperature = 0;
  console.log(`  TEMPERATURE: ${testTemperature} — fully deterministic`);
  console.log(
    "     Even at temp=0, raw prompting can fail. The model may still wrap"
  );
  console.log(
    "     valid JSON in markdown backticks. Temperature is not the issue."
  );
  console.log(
    "     The APPROACH is the issue — request vs contract."
  );
  console.log();

  // ═══════════════════════════════════════════════════════════
  // APPROACH A: RAW PROMPTING — "The Request"
  // ═══════════════════════════════════════════════════════════
  console.log("=".repeat(75));
  console.log("  APPROACH A: Raw JSON Prompting");
  console.log("  Strategy: Ask the model nicely to return JSON.");
  console.log("  Problem:  It's a request, not a contract.");
  console.log("=".repeat(75));
  console.log();

  const rawPrompt =
    "Analyze this code change and extract details. " +
    "Return a JSON object matching this schema:\n" +
    "{\n" +
    '  "change": { "type": "bug"|"feature", "severity": "low"|"high", "ticket": "string" },\n' +
    '  "details": { "summary": "string", "root_cause": "string", "user_impact_pct": integer },\n' +
    '  "technical": { "files_changed": ["string"], "db_changed": boolean, "rollback": "string" }\n' +
    "}\n\n" +
    "DIFF:\n";

  const llmRaw = getLlm({ temperature: testTemperature, maxTokens: 300 });

  console.log("  Sending prompt to model...");
  const responseRaw = await llmRaw.invoke([
    new HumanMessage(`${rawPrompt}\n${diffInput}`),
  ]);
  const rawText = responseRaw.content.trim();

  console.log(`  Raw response (${rawText.length} chars):`);
  console.log("  " + "-".repeat(55));
  for (const line of rawText.split("\n")) {
    console.log(`  | ${line}`);
  }
  console.log("  " + "-".repeat(55));
  console.log();

  console.log("  Attempting to parse as JSON...");
  try {
    // Strip markdown code fences if present
    let jsonStr = rawText;
    if (jsonStr.startsWith("```")) {
      jsonStr = jsonStr.replace(/^```(?:json)?\s*\n?/, "").replace(/\n?```\s*$/, "");
    }
    const data = JSON.parse(jsonStr);
    console.log(
      `  ✅ JSON PARSE SUCCEEDED. Keys returned: ${Object.keys(data).join(", ")}`
    );
    const change = data.change || {};
    const details = data.details || {};
    console.log(`     change.type:     ${change.type || "MISSING"}`);
    console.log(`     change.severity: ${change.severity || "MISSING"}`);
    console.log(`     change.ticket:   ${change.ticket || "MISSING"}`);
    const impact = details.user_impact_pct ?? "MISSING";
    console.log(
      `     details.user_impact_pct: ${impact} (type: ${typeof impact})`
    );
    if (typeof impact === "string" && impact.includes("%")) {
      console.log(
        `     ⚠️  VALUE IS A STRING: '${impact}' — you must clean this manually`
      );
      console.log(
        "        Zod structured output would have handled this automatically."
      );
    }

    console.log();
    console.log("  Full raw JSON result:");
    console.log("  " + "-".repeat(55));
    console.log(`  ${JSON.stringify(data, null, 2)}`);
    console.log("  " + "-".repeat(55));
  } catch (e) {
    console.log("  ❌ JSON PARSE FAILED");
    console.log(`     Error: ${e.message}`);
    console.log();
    console.log("  Raw output that failed to parse:");
    console.log("  " + "-".repeat(55));
    for (const line of rawText.split("\n")) {
      if (line.trim().startsWith("```")) {
        console.log(`  | ⚠️  ${line}`);
      } else {
        console.log(`  | ${line}`);
      }
    }
    console.log("  " + "-".repeat(55));
    console.log();
    console.log("     THIS IS THE PROBLEM: a single malformed response");
    console.log("     breaks your entire pipeline.");
  }

  // ═══════════════════════════════════════════════════════════
  // APPROACH B: ZOD — "The Contract"
  // ═══════════════════════════════════════════════════════════
  console.log();
  console.log("=".repeat(75));
  console.log("  APPROACH B: Zod + withStructuredOutput()");
  console.log(
    "  Strategy: Bind the schema to the model at the API level."
  );
  console.log(
    "  Result:   The model CANNOT return output that violates the schema."
  );
  console.log("=".repeat(75));
  console.log();

  const llmStructured = getLlm({ temperature: testTemperature, maxTokens: 300 });
  const structuredLlm = llmStructured.withStructuredOutput(
    DiffAnalysisSchema
  );

  console.log(
    "  Sending SAME input to model (same temperature, same diff)..."
  );
  const zodResult = await structuredLlm.invoke([
    new SystemMessage("Analyze the diff and return a valid DiffAnalysis object."),
    new HumanMessage(`Analyze this diff:\n${diffInput}`),
  ]);

  console.log(`  Returned type: ${zodResult.constructor.name}`);
  console.log(
    `  Is it a string? ${
      typeof zodResult === "string"
        ? "❌ YES — would need parsing"
        : "✅ NO — it is a typed object"
    }`
  );
  console.log();

  console.log(
    "  Extracted data (all fields guaranteed present and correctly typed):"
  );
  console.log(`    change.type:              ${zodResult.change.type}`);
  console.log(`    change.severity:          ${zodResult.change.severity}`);
  console.log(`    change.ticket:            ${zodResult.change.ticket}`);
  console.log(`    details.summary:          ${zodResult.details.summary}`);
  console.log(`    details.root_cause:       ${zodResult.details.root_cause}`);
  console.log(
    `    details.user_impact_pct:  ${zodResult.details.user_impact_pct} ` +
      `(type: ${typeof zodResult.details.user_impact_pct})`
  );
  console.log(
    `    technical.files_changed:  [${zodResult.technical.files_changed.join(", ")}]`
  );
  console.log(
    `    technical.db_changed:     ${zodResult.technical.db_changed}`
  );
  console.log(
    `    technical.rollback:       ${zodResult.technical.rollback}`
  );
  console.log();

  console.log("  Full Zod result:");
  console.log("  " + "-".repeat(55));
  console.log(`  ${JSON.stringify(zodResult, null, 2)}`);
  console.log("  " + "-".repeat(55));
  console.log();

  // ═══════════════════════════════════════════════════════════
  // THE VERDICT
  // ═══════════════════════════════════════════════════════════
  console.log("=".repeat(75));
  console.log("  THE VERDICT");
  console.log("=".repeat(75));
  console.log();
  console.log(
    "  Same input. Same temperature (0.0). Same extraction task."
  );
  console.log();
  console.log("  Approach A (Raw Prompting):");
  console.log("    • A polite request to 'return JSON'");
  console.log("    • Model may add markdown backticks — even at temperature=0");
  console.log(
    "    • JSON.parse() may crash. Pipeline breaks. Temperature didn't matter."
  );
  console.log();
  console.log("  Approach B (Zod):");
  console.log("    • A binding contract — schema enforced at the token level");
  console.log("    • Model CANNOT return output that violates the schema");
  console.log("    • Output is ALWAYS a typed object — no parsing needed");
  console.log();
  console.log("  Raw JSON prompting = hope-based architecture.");
  console.log("  Zod schema          = engineering.");
  console.log("=".repeat(75));
}

runDemo().catch((err) => {
  console.error("Demo failed:", err.message);
  process.exit(1);
});
