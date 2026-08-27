/**
 * DevBuddy — Centralized Configuration
 *
 * Single source of truth for all environment-driven settings.
 * Every module imports from here — never reads process.env directly.
 *
 * Principles:
 *   - Load .env once, at import time
 *   - Validate required keys early (fail fast)
 *   - Provide sensible defaults for all optional values
 *   - Single place to swap providers, models, endpoints
 */
import dotenv from "dotenv";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

// ── Resolve .env path relative to this file ──────────────────
const __dirname = dirname(fileURLToPath(import.meta.url));
const envPath = resolve(__dirname, "..", ".env");
dotenv.config({ path: envPath, override: true });

// ── Read raw value (with fallback) ───────────────────────────
const get = (key, fallback) => process.env[key] || fallback;

// ── Required — fail fast if missing ──────────────────────────
const required = (key) => {
  const value = process.env[key];
  if (!value) {
    throw new Error(
      `${key} is not set.\n` +
        `Ensure ${envPath} exists and contains: ${key}=<your-value>`
    );
  }
  return value;
};

// ── Config object — the single source of truth ───────────────
export const config = {
  // LLM Provider
  openRouterApiKey: required("OPENROUTER_API_KEY"),
  model: get("DEVBUDDY_MODEL", "openai/gpt-4o-mini"),
  modelAlt: get("DEVBUDDY_MODEL_ALT", null),  // optional, for model swap tests
  openRouterBaseUrl: "https://openrouter.ai/api/v1",

  // Inference defaults
  defaultTemperature: 0.0,
  defaultMaxTokens: 1024,

  // App identity (sent to OpenRouter for analytics)
  appReferer: "https://github.com/your-org/devbuddy",
  appTitle: "DevBuddy",

  // Cost tracking (per 1M tokens, OpenRouter pricing)
  pricing: {
    // GPT-4o-mini
    "openai/gpt-4o-mini": { input: 0.15, output: 0.6 },
    // Claude 3.5 Sonnet
    "anthropic/claude-3.5-sonnet": { input: 3.0, output: 15.0 },
    // Gemini 2.5 Flash Lite
    "google/gemini-2.5-flash-lite": { input: 0.075, output: 0.3 },
    // Fallback for unknown models
    default: { input: 0.15, output: 0.6 },
  },

  // Week 3 — RAG (not yet active, just defaults)
  vectorStoreUrl: get("QDRANT_URL", "http://localhost:6333"),
  embeddingModel: "Xenova/all-MiniLM-L6-v2",
  defaultChunkSize: 512,
  defaultChunkOverlap: 50,

  // Week 6 — Agent (not yet active)
  maxAgentSteps: 10,
  maxAgentCost: 2.0,

  // Week 7 — Guardrails (not yet active)
  guardrailConfidenceThreshold: 0.7,
};

// ── Derived helpers ──────────────────────────────────────────

/**
 * Get pricing for the currently configured model.
 * Falls back to default pricing if model isn't explicitly known.
 */
export function getPricing(model = config.model) {
  return config.pricing[model] || config.pricing.default;
}

/**
 * Calculate cost in USD from token counts.
 */
export function calculateCost(promptTokens, completionTokens, model = config.model) {
  const { input, output } = getPricing(model);
  return (promptTokens * input + completionTokens * output) / 1_000_000;
}

/**
 * Pretty-print the current config (hide secret values).
 */
export function inspect() {
  const safe = { ...config };
  safe.openRouterApiKey = safe.openRouterApiKey
    ? safe.openRouterApiKey.slice(0, 12) + "..."
    : "not set";
  return safe;
}

// ── Log on first load (only in development) ──────────────────
console.log(`[devbuddy] config loaded — model: ${config.model}`);
