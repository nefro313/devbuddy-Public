/**
 * Week 2 — Structured output functions (the "action" that fills the contract).
 *
 * These functions call the LLM and return typed objects. They live here — not
 * in schemas.js — so schemas.js stays pure (schemas only, no LLM imports).
 * The schema is the contract; these functions produce a model response that fits it.
 */
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { getLlm } from "./llm.js";
import { BuildCheckSchema, ServiceReadinessReportSchema } from "./schemas.js";

/**
 * Analyze a PR and return a structured BuildCheck.
 *
 * @param {Object} opts
 * @param {string} opts.title - PR title
 * @param {string} opts.diff - PR diff content
 * @param {number} [opts.temperature=0.0] - 0.0 for deterministic output
 * @param {number|null} [opts.maxTokens=null] - Max tokens in response. null = model default.
 * @returns {Promise<BuildCheck>}
 */
export async function analyzePr({
  title,
  diff,
  temperature = 0.0,
  maxTokens = null,
}) {
  const prompt =
    "You are a code reviewer. Analyze the given PR and return a BuildCheck.\n" +
    "- severity: 'critical' if it touches auth, payments, or security. " +
    "'high' if it changes core logic. 'medium' for feature work. 'low' for docs/typos.\n" +
    "- summary: one sentence describing what changed and why.\n" +
    "- affected_files: list the files mentioned in the diff.\n" +
    "- project: extract the project or service name from the PR context.";

  return analyzePrWithPrompt({
    title,
    diff,
    promptTemplate: prompt,
    temperature,
    maxTokens,
  });
}

export async function analyzePrWithPrompt({
  title,
  diff,
  promptTemplate,
  temperature = 0.0,
  maxTokens = null,
}) {
  const llm = getLlm({ temperature, maxTokens });
  const structured = llm.withStructuredOutput(BuildCheckSchema);

  const prompt = promptTemplate
    .replaceAll("{{title}}", title)
    .replaceAll("{{diff}}", diff);

  const result = await structured.invoke([
    new SystemMessage(
      "You are a careful code reviewer. Follow the instructions exactly and " +
        "return only a valid JSON object that matches the schema."
    ),
    new HumanMessage(prompt),
  ]);

  return result;
}

/**
 * Generate a ServiceReadinessReport from mock build/deploy data.
 *
 * @param {Object} opts
 * @param {string} opts.serviceName - e.g. 'auth-service'
 * @param {Object} opts.buildData - build status fields (status, last_deploy, failing_since)
 * @param {Object} opts.deployData - deployment history (recent_deploys, active_incidents)
 * @param {number} [opts.temperature=0.0] - 0.0 for deterministic output
 * @returns {Promise<ServiceReadinessReport>}
 */
export async function generateReadinessReport({
  serviceName,
  buildData,
  deployData,
  temperature = 0.0,
}) {
  const llm = getLlm({ temperature });
  const structured = llm.withStructuredOutput(
    ServiceReadinessReportSchema
  );

  const result = await structured.invoke([
    new SystemMessage(
      "You are a site reliability engineer assessing whether a service is ready " +
        "for its next release. You are given build health data and recent deployment " +
        "history. Produce a ServiceReadinessReport.\n\n" +
        "RULES:\n" +
        "- If the build status is 'healthy' with no active incidents and recent " +
        "deploys are all 'success', the service is ready with high confidence.\n" +
        "- If the build is 'degraded' or there are active incidents, the service is " +
        "NOT ready. List specific blockers.\n" +
        "- If there is no data at all, set confidence to 'low'.\n" +
        "- Every verdict must be supported by evidence. Reference the data you were given.\n" +
        "- Blockers should be specific and actionable, not vague."
    ),
    new HumanMessage(
      `Service: ${serviceName}\n\n` +
        `Build data:\n${JSON.stringify(buildData, null, 2)}\n\n` +
        `Deployment data:\n${JSON.stringify(deployData, null, 2)}`
    ),
  ]);

  return result;
}
