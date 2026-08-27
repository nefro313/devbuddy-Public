/**
 * Demo 5: Agentic Retry (Self-Correction Loop)
 *
 * Even with strict schemas, LLMs can violate business logic (cross-field rules).
 * Instead of failing or doing a "blind retry", we catch the validation error and
 * feed it back to the LLM so it fixes its own mistake.
 *
 * Run: node scripts/week-02/demo-05-agentic-retry.js
 */
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { getLlm } from "../../src/llm.js";
import { ServiceReadinessReportSchema } from "../../src/schemas.js";
import { config } from "../../src/config.js";

const llm = getLlm({ temperature: 0.2 });
const structured = llm.withStructuredOutput(ServiceReadinessReportSchema);

const messages = [
  new SystemMessage("You are a strict SRE. Follow instructions exactly."),
  new HumanMessage(
    "You are evaluating 'auth-service' v2.1.0.\n" +
      "The build is passing and healthy (last deploy: 2024-10-01T12:00:00Z).\n" +
      "However, there is an active incident: 'DB connection pooling exhausted'.\n\n" +
      "CRITICAL INSTRUCTIONS:\n" +
      "1. You MUST set verdict.ready=true because the build is passing.\n" +
      "2. You MUST also list the DB incident in the verdict.blockers array.\n" +
      "3. You MUST include at least one item in the 'evidence' array so confidence can be high.\n"
  ),
];

function extractError(e) {
  // Zod's .refine() errors live in e.errors; LangChain may wrap them in the message.
  if (e && Array.isArray(e.errors) && e.errors.length) {
    return e.errors[0].message || JSON.stringify(e.errors[0]);
  }
  const msg = e?.message || String(e);
  // LangChain's OutputParserException embeds the Zod error as {"message":"..."}.
  const m = msg.match(/"message":"([^"]+)"/);
  return m ? m[1] : msg;
}

console.log("=".repeat(75));
console.log("  DEMO 5: Agentic Retry (Self-Correction)");
console.log("=".repeat(75));
console.log(`  Model: ${config.model}`);
console.log();

const maxRetries = 3;
for (let attempt = 1; attempt <= maxRetries; attempt++) {
  try {
    console.log(`  Attempt ${attempt} / ${maxRetries}...`);
    const result = await structured.invoke(messages);

    console.log("\n  ✅ SUCCESS! The LLM produced valid output:");
    console.log(`     ready:    ${result.verdict.ready}`);
    console.log(`     blockers: ${result.verdict.blockers}`);

    if (attempt > 1) {
      console.log("\n  By giving the LLM the error, it acted as its own debugger.");
    } else {
      console.log("\n  ❌ WAIT. The LLM passed on the first try? The trap failed.");
    }
    break;
  } catch (e) {
    const errorMsg = extractError(e);
    console.log(`  ❌ Caught validation error:\n     ${errorMsg}`);

    if (attempt < maxRetries) {
      console.log("  -> Feeding error back to the LLM for self-correction...\n");
      messages.push(
        new HumanMessage(
          `Your previous output failed schema validation with this error:\n${errorMsg}\n\nPlease analyze the error and output a corrected JSON.`
        )
      );
    } else {
      console.log("\n  ❌ Max retries reached. The LLM could not fix the error.");
    }
  }
}
