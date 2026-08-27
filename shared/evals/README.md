# Promptfoo — Eval Configs

Promptfoo runs evals against your LLM outputs. You write assertions in YAML,
Promptfoo calls the model, validates the output, and shows a pass/fail table.

---

## Prerequisites

Promptfoo runs via `npx` (Node.js package runner). You need Node.js 20+:

```bash
node --version   # must be v20.x or later
```

If Node.js isn't installed: [https://nodejs.org](https://nodejs.org) — download the LTS version.
No global install needed — `npx` downloads Promptfoo on first run.

---

## Quick Test (Week 0)

```bash
cd shared/evals
export OPENROUTER_API_KEY=sk-or-your-key
npx promptfoo@latest eval --config week-00-smoke.yaml
```

This calls the model, validates it returns valid JSON, and prints a summary table:

```
┌─────────────┬───────────────────────────┬──────────┬────────┐
│ Test Case   │ Assertions                │ Status   │ Cost   │
├─────────────┼───────────────────────────┼──────────┼────────┤
│ Basic JSON  │ 1 passed, 0 failed        │ PASS     │ $0.001 │
└─────────────┴───────────────────────────┴──────────┴────────┘
```

## How to Read the Output

- **PASS** — all assertions matched
- **FAIL** — one or more assertions didn't match. The output shows what the model returned vs what was expected
- **Cost** — token cost from OpenRouter headers

Run a failing test to see it:
```bash
# This test expects "4" — the model usually gets it right, but if not, you'll see the failure
npx promptfoo@latest eval --config week-00-smoke.yaml
```

---

## Eval Configs

| File | Week | What it tests | Run after |
|------|------|---------------|-----------|
| `week-00-smoke.yaml` | Week 0 | Model returns valid structured output | Week 0 |
| `week-02-structured-output.yaml` | Week 2 | Schema adherence, field types, retry behavior | Week 2 |
| `week-03-rag-grounding.yaml` | Week 3 | Retrieved context relevance, hallucination suppression | Week 3 |
| `week-04-tool-selection.yaml` | Week 4 | Correct tool routing, argument validation | Week 4 |
| `week-05-mcp-tool-ecosystem.yaml` | Week 5 | Tool synthesis: valid JSON for all 4 tools | Week 5 |
| `week-06-agent-planning.yaml` | Week 6 | Step sequence correctness, state coherence | Week 6 |
| `week-07-production-suite.yaml` | Week 7 | Guardrails, cost, latency, provider swap | Week 7 |
