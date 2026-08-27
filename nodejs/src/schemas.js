/**
 * Week 2 — Structured Outputs (Node.js)
 *
 * Zod schemas + structured LLM calls.
 * The LLM returns typed objects, not prose.
 *
 * Two schema families:
 *   BuildCheck            → flat, 4-field PR analysis (in-session)
 *   ServiceReadinessReport → composed, nested, validated (self-learning + capstone preview)
 */
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { z } from "zod";
import { getLlm } from "./llm.js";

// ═══════════════════════════════════════════════════════════════
// PR Analysis — flat schema for the in-session exercise
// ═══════════════════════════════════════════════════════════════

export const BuildCheckSchema = z.object({
  project: z.string().describe("Project or service name"),
  severity: z
    .enum(["low", "medium", "high", "critical"])
    .describe("How urgent is this change?"),
  summary: z.string().describe("One-sentence summary of the change"),
  affected_files: z
    .array(z.string())
    .describe("Files modified by this change"),
});

/**
 * @typedef {z.infer<typeof BuildCheckSchema>} BuildCheck
 */

// ═══════════════════════════════════════════════════════════════
// Service Readiness Report — composed schema for self-learning
//
// This mirrors the DevBuddy end-state output.
// Engineers build and test this with mock data — no API calls.
// ═══════════════════════════════════════════════════════════════

export const ServiceInfoSchema = z.object({
  name: z.string().describe("Service name, e.g. 'auth-service'"),
  version: z
    .string()
    .describe("Currently deployed version, e.g. '2.1.0'"),
  owner_team: z.string().describe("Team responsible for this service"),
});

export const BuildStatusSchema = z
  .object({
    status: z
      .enum(["healthy", "degraded", "down", "unknown"])
      .describe("Current build/health status"),
    last_deploy: z
      .string()
      .describe("ISO timestamp of the most recent deployment"),
    failing_since: z
      .string()
      .nullable()
      .optional()
      .describe(
        "ISO timestamp of when the build started failing, if degraded or down"
      ),
  })
  .refine(
    (data) => {
      // If status is degraded or down, failing_since should be present
      if (
        (data.status === "degraded" || data.status === "down") &&
        !data.failing_since
      ) {
        return false;
      }
      return true;
    },
    {
      message:
        "failing_since is required when status is 'degraded' or 'down'. Provide an ISO timestamp.",
      path: ["failing_since"],
    }
  );

export const DeployRecordSchema = z.object({
  sha: z.string().describe("Commit SHA of the deployment"),
  author: z.string().describe("Engineer who triggered the deploy"),
  timestamp: z.string().describe("ISO timestamp of the deployment"),
  status: z
    .enum(["success", "failed", "rolling_back"])
    .describe("Outcome of this deployment"),
});

export const DeploymentInfoSchema = z.object({
  recent_deploys: z
    .array(DeployRecordSchema)
    .describe("Last N deployments, most recent first"),
  active_incidents: z
    .array(z.string())
    .default([])
    .describe("IDs or summaries of any active incidents"),
});

export const EvidenceChunkSchema = z.object({
  source: z
    .enum(["rag", "tool", "user"])
    .describe(
      "Where this evidence came from — RAG retrieval, tool output, or user query"
    ),
  content: z.string().describe("The evidence content"),
  relevance_score: z
    .number()
    .min(0)
    .max(1)
    .nullable()
    .optional()
    .describe(
      "0.0–1.0 relevance score from the retriever, if sourced from RAG"
    ),
});

export const ReadinessVerdictSchema = z.object({
  ready: z
    .boolean()
    .describe("True if the service can proceed to the target version"),
  confidence: z
    .enum(["low", "medium", "high"])
    .describe("How confident is this verdict?"),
  blockers: z
    .array(z.string())
    .default([])
    .describe("Reasons the service is NOT ready. Empty if ready=true."),
  recommended_next_steps: z
    .array(z.string())
    .default([])
    .describe("What to do next — regardless of ready/blocked"),
});

export const ServiceReadinessReportSchema = z
  .object({
    service: ServiceInfoSchema,
    build: BuildStatusSchema,
    deployment: DeploymentInfoSchema,
    verdict: ReadinessVerdictSchema,
    evidence: z
      .array(EvidenceChunkSchema)
      .default([])
      .describe("Supporting evidence from retrieval and tool calls"),
  })
  .refine(
    (data) => {
      // If ready=true, blockers must be empty
      if (data.verdict.ready && data.verdict.blockers.length > 0) {
        return false;
      }
      return true;
    },
    {
      message:
        "Contradiction: verdict.ready=true but blockers are present. " +
        "If there are blockers, ready must be false.",
      path: ["verdict", "ready"],
    }
  )
  .refine(
    (data) => {
      // If ready=false with confidence != 'low', blockers should be non-empty
      if (
        !data.verdict.ready &&
        data.verdict.confidence !== "low" &&
        data.verdict.blockers.length === 0
      ) {
        return false;
      }
      return true;
    },
    {
      message:
        "verdict.ready=false with confidence above 'low' but no blockers listed. " +
        "Either lower confidence to 'low' or add blockers.",
      path: ["verdict", "confidence"],
    }
  )
  .refine(
    (data) => {
      // If no evidence, confidence cannot be higher than 'low'
      if (data.evidence.length === 0 && data.verdict.confidence !== "low") {
        return false;
      }
      return true;
    },
    {
      message:
        "No evidence provided but confidence is above 'low'. " +
        "Without evidence, confidence must be 'low'.",
      path: ["verdict", "confidence"],
    }
  );

/**
 * @typedef {z.infer<typeof ServiceReadinessReportSchema>} ServiceReadinessReport
 */

// ═══════════════════════════════════════════════════════════════
// LLM Functions
// ═══════════════════════════════════════════════════════════════

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
  const llm = getLlm({ temperature, maxTokens });
  const structured = llm.withStructuredOutput(BuildCheckSchema);

  const result = await structured.invoke([
    new SystemMessage(
      "You are a code reviewer. Analyze the given PR and return a BuildCheck.\n" +
        "- severity: 'critical' if it touches auth, payments, or security. " +
        "'high' if it changes core logic. 'medium' for feature work. 'low' for docs/typos.\n" +
        "- summary: one sentence describing what changed and why.\n" +
        "- affected_files: list the files mentioned in the diff.\n" +
        "- project: extract the project or service name from the PR context."
    ),
    new HumanMessage(`PR Title: ${title}\n\nDiff:\n${diff}`),
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
