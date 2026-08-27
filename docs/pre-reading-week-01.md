# AI Engineering vs Traditional Engineering

> Pre-reading for Week 1. 5 minutes.

You've built software for years. You have instincts about what works. Some transfer directly to AI-first systems. Some don't. This table is your framework for the series.

---

## What Transfers Directly

| Your existing instinct | How it applies to AI systems |
|---|---|
| Error handling, retry logic, circuit breakers | LLM calls fail. Timeouts happen. Rate limits hit. Handle them like any external API. |
| Observability: logging, tracing, metrics | You can't debug what you can't see. Trace every LLM call, tool call, retrieval. |
| API design: contracts, versioning | Structured output (JSON schema) is your API contract with the model. Version it. |
| Code review, PRs, CI/CD | Prompt changes are code changes. They go through the same review pipeline. |
| Feature flags, incremental rollout | Ship AI features behind flags. Roll back to deterministic if the model degrades. |
| Capacity planning, cost modelling | LLM calls cost money per token. Model at scale before you build. |

---

## What's Different — Requires New Muscles

| Traditional engineering | AI-first engineering |
|---|---|
| Assert on exact output: `assert result == "expected"` | Evaluate with ranges and patterns. Evals replace unit tests. |
| Determinism is the default | Non-determinism is the default. Manage variance, don't eliminate it. |
| The code is the logic | The model is the decision layer. Your code is the execution and enforcement layer. |
| Bugs are in your code | Bugs can be in your prompt, context assembly, retrieval, model choice, or parameters. |
| You test with expected inputs | You also test with adversarial inputs. Prompt injection is a real attack surface. |
| Cost is infrastructure (servers, databases) | Cost is per-call and per-token. $0.02 × 10,000/day = $6,000/month. |

---

## One Question to Hold

As you go through this series, ask after each week:

> *"Does this change how I'd approach a feature request in my team?"*
