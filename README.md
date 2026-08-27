# DevBuddy — AI Practitioner Series

> **You're building an AI agent.** Not a chatbot. A component. By Week 7, DevBuddy will retrieve docs, check build status, query deployments, and generate structured release reports — all from a single question.

---

## Architecture — The End State

```
                         ┌──────────────────────┐
                         │     User Query         │
                         │ "Is auth-service      │
                         │  ready for v2.1?"     │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Input Guardrail     │  Week 7
                         │   (blocks injection)  │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Agent Orchestrator  │  Week 6
                         │   (plans steps)       │
                         └──┬───────┬───────┬───┘
                            │       │       │
              ┌─────────────▼┐  ┌───▼────┐  ┌▼─────────────┐
              │  RAG Engine  │  │ Tools  │  │  Structured   │
              │  (Week 3)    │  │(Week 4)│  │   Output      │
              │              │  │        │  │   (Week 2)    │
              └──────┬───────┘  └───┬────┘  └──────┬────────┘
                     │              │               │
              ┌──────▼──────┐ ┌────▼────────┐ ┌───▼───────────┐
              │  ChromaDB   │ │ Mock APIs   │ │ Pydantic/Zod   │
              │  Vector     │ │ + Real data │ │ Validation     │
              │  Store      │ │ sources     │ │ + Auto-retry   │
              └─────────────┘ └─────────────┘ └───────────────┘
                            │       │       │
                            └───────┼───────┘
                                    │
                         ┌──────────▼───────────┐
                         │   MCP Server          │  Week 5
                         │   (shared tools)      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Output Guardrail    │  Week 7
                         │   Cost + Tracing      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Structured Report   │
                         └──────────────────────┘
```

---

## How Code Grows — The Import Graph

Once a module is built, it is NEVER copied. It is IMPORTED.

```
Week 1:  src/llm.py                          Foundation
Week 2:  src/llm.py ← src/schemas.py          Contract
Week 3:  src/llm.py ← src/rag.py              Memory
Week 4:  src/llm.py ← src/tools.py            Hands
Week 5:  src/tools.py ← src/mcp_server.py      Platform
Week 6:  src/llm.py + schemas + rag + tools ← src/agent.py   Brain
Week 7:  src/agent.py ← guardrails + cost + tracing          Production
```

---

## Schedule

| Week | Topic | What You Build |
|------|-------|---------------|
| 0 | Setup | Fork the repo. Run `verification.py`. Post to channel. |
| 1 | Kick-off | Architecture, rubric, AI vs Traditional Engineering |
| 2 | Structured Outputs | `src/schemas.py` — typed objects, not prose |
| 3 | RAG | `src/rag.py` — embed, chunk, retrieve, ground |
| 4 | Tools | `src/tools.py` — function calling, error recovery |
| 5 | MCP | `src/mcp_server.py` — shared tool ecosystem |
| 6 | Agent | `src/agent.py` — orchestrator, imports everything |
| 7 | Production | Guardrails + cost + tracing + capstone |

---

## Levels

| Level | Title | What it means |
|-------|-------|--------------|
| 0 | Consumer | Reproduced the exercise. Can call an LLM and parse output. |
| 1 | Builder | Extended and broke things independently. |
| 2 | Evaluator | Documented failures + tradeoffs. Contributed ADRs to runbook. |
| 3 | Architect | Built the capstone. Defended architecture decisions. |

**Gate:** Level 2 minimum. Level 3 is the target.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| LLM Provider | OpenRouter (one key, any model) |
| Framework (Python, Node.js) | LangChain + LangGraph |
| Framework (Java) | Spring AI |
| Validation | Pydantic (Python), Zod (Node.js), Jakarta Bean Validation (Java) |
| Vector Store | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Evals | Promptfoo (`npx promptfoo`, configs in `shared/evals/`) |

---

## Getting Started

See [`SETUP.md`](SETUP.md) for step-by-step instructions. Quick version:

```bash
gh repo fork org/devbuddy --clone
cd devbuddy/python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OPENROUTER_API_KEY
python src/verification.py
```
