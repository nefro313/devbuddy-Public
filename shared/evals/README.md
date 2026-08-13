# Promptfoo — Eval Configs

Promptfoo runs evals against your LLM outputs. Configs are YAML. Run with `npx`.

## Prerequisites

- Node.js 20+ (`node --version`)
- OpenRouter API key set in environment

## Quick Test (Week 0)

```bash
cd shared/evals
export OPENROUTER_API_KEY=sk-or-your-key
npx promptfoo@latest eval --config week-00-smoke.yaml
```

This runs a basic eval: does the model return valid JSON with the expected fields?

## Eval Configs (built during the series)

| File | Week | What it tests |
|------|------|---------------|
| `week-00-smoke.yaml` | Week 0 | Model returns valid structured output |
| `week-02-structured-output.yaml` | Week 2 | Schema adherence, field types, retry behavior |
| `week-03-rag-grounding.yaml` | Week 3 | Retrieved context relevance, hallucination suppression |
| `week-04-tool-selection.yaml` | Week 4 | Correct tool routing, error handling |
| `week-05-mcp-tool-ecosystem.yaml` | Week 5 | Tool synthesis: valid JSON, correct structure for each tool |
| `week-06-agent-planning.yaml` | Week 6 | Step sequence correctness, state coherence |
| `week-07-production-suite.yaml` | Week 7 | Guardrails, cost, latency, provider swap |
