/**
 * DevBuddy Integration Test — Week 0 (Node.js)
 *
 * Validates the full setup end-to-end:
 * 1. .env is configured (OPENROUTER_API_KEY, DEVBUDDY_MODEL)
 * 2. OpenRouter connectivity works
 * 3. Structured output returns typed objects
 * 4. Cost tracking works
 * 5. Model swap works (optional)
 *
 * Run: npm test
 */
import { describe, it, expect } from "vitest";
import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { z } from "zod";
import { config, calculateCost } from "../src/config.js";
import { getLlm } from "../src/llm.js";

// ─── Test 1: Environment ──────────────────────────────────────
describe("Environment", () => {
  it("has OPENROUTER_API_KEY configured", () => {
    expect(config.openRouterApiKey).toBeTruthy();
    expect(config.openRouterApiKey).toContain("sk-or-");
  });

  it("has DEVBUDDY_MODEL configured", () => {
    expect(config.model).toBeTruthy();
  });
});

// ─── Test 2: OpenRouter Connectivity ──────────────────────────
describe("OpenRouter Connectivity", () => {
  it("responds to a basic prompt within 30s", async () => {
    const llm = getLlm();
    const start = performance.now();
    const response = await llm.invoke([
      new HumanMessage("Say 'connected' and nothing else."),
    ]);
    const elapsed = (performance.now() - start) / 1000;

    expect(response).toBeTruthy();
    expect(response.content.toLowerCase()).toContain("connected");
    expect(elapsed).toBeLessThan(30);

    // Verify token usage in metadata
    const usage = response.usage_metadata || {};
    const inputTokens = usage.input_tokens || 0;
    const outputTokens = usage.output_tokens || 0;

    console.log(
      `    ✅ OpenRouter connected: ${elapsed.toFixed(1)}s, ` +
        `tokens=${inputTokens}+${outputTokens}`
    );
  });
});

// ─── Test 3: Structured Output ────────────────────────────────
describe("Structured Output", () => {
  it("returns a typed Zod object", async () => {
    const SmokeTestSchema = z.object({
      status: z.string().describe("Must be 'ok'"),
      model_used: z
        .string()
        .describe("The model that processed this request"),
    });

    const llm = getLlm();
    const structured = llm.withStructuredOutput(SmokeTestSchema);

    const response = await structured.invoke([
      new SystemMessage("Return valid JSON only."),
      new HumanMessage(
        "Set status='ok'. Include the model you're running on."
      ),
    ]);

    expect(response).toBeTruthy();
    expect(response.status).toBe("ok");
    expect(response.model_used).toBeTruthy();

    console.log(
      `    ✅ Structured output: ${response.constructor.name}(status='${response.status}')`
    );
  });
});

// ─── Test 4: Cost Tracking ────────────────────────────────────
describe("Cost Tracking", () => {
  it("captures token usage on a plain LLM call", async () => {
    const llm = getLlm();
    const response = await llm.invoke([
      new HumanMessage("One word: hello"),
    ]);

    const usage = response.usage_metadata || {};
    const inputTokens = usage.input_tokens || 0;
    const outputTokens = usage.output_tokens || 0;

    expect(inputTokens).toBeGreaterThan(0);
    expect(outputTokens).toBeGreaterThan(0);

    // Verify our calculateCost helper works with these tokens
    const cost = calculateCost(inputTokens, outputTokens);
    expect(cost).toBeGreaterThan(0);

    console.log(
      `    ✅ Cost tracked: ${inputTokens}+${outputTokens} tokens, ` +
        `~$${cost.toFixed(6)}`
    );
  });
});

// ─── Test 5: Model Swap (Optional) ────────────────────────────
describe("Model Swap", () => {
  const altModel = config.modelAlt;

  if (altModel) {
    it(`swaps to ${altModel} successfully`, async () => {
      const llm = getLlm({ model: altModel });
      const start = performance.now();
      const response = await llm.invoke([
        new HumanMessage("Say 'ok'"),
      ]);
      const elapsed = (performance.now() - start) / 1000;

      expect(response).toBeTruthy();
      expect(elapsed).toBeLessThan(30);

      console.log(
        `    ✅ Model swap: ${altModel} responded in ${elapsed.toFixed(1)}s`
      );
    });
  } else {
    it.skip("model swap (set DEVBUDDY_MODEL_ALT in .env to enable)", () => {
      // Skipped — no alt model configured
    });
  }
});
