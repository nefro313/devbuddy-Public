# DevBuddy — Node.js Blueprint

> **Language Shepherd:** [TBD]
> **Blueprint Ready:** Week 0 | **Engineers can use from:** Week 0

## Quick Start

```bash
# Navigate to the Node.js directory
cd nodejs

# Install dependencies
npm install

# Set your API key
cp .env.example .env
# Edit .env → add your OPENROUTER_API_KEY

# Verify your environment
npm run verify
```

## Stack

| Layer | Choice |
|-------|--------|
| LLM Provider | OpenRouter (via `@langchain/openai`) |
| Framework | LangChain.js + LangGraph.js |
| Validation | Zod |
| Vector Store | Qdrant |
| Embeddings | @xenova/transformers |
| MCP | @modelcontextprotocol/sdk |
| Evals | Promptfoo |
| Tracing | LangChain callbacks + OpenTelemetry |

## Project Structure

```
nodejs/
├── src/
│   ├── llm.js           # Week 1: OpenRouter client factory
│   ├── verification.js   # Week 0: verification script (run once, keep)
│   ├── schemas.js        # Week 2: Zod schemas + structured output
│   ├── rag.js            # Week 3: loader, chunker, vector store, retriever
│   ├── tools.js          # Week 4: tool definitions
│   ├── mcp_server.js     # Week 5: MCP server
│   ├── agent.js          # Week 6: agent graph, planner, orchestrator
│   ├── guardrails.js     # Week 7: input/output guardrails
│   ├── cost_tracker.js   # Week 7: token/cost tracking
│   └── tracing.js        # Week 7: callbacks and tracing
├── package.json
└── .env.example
```

## How Code Grows — The Import Graph

Once a module is built, it is NEVER copied. It is IMPORTED.

```
Week 1:  src/llm.js                              Foundation
Week 2:  src/llm.js ← src/schemas.js               Contract
Week 3:  src/llm.js ← src/rag.js                   Memory
Week 4:  src/llm.js ← src/tools.js                 Hands
Week 5:  src/tools.js ← src/mcp_server.js           Platform
Week 6:  src/llm.js + schemas + rag + tools ← src/agent.js   Brain
Week 7:  src/agent.js ← guardrails + cost + tracing            Production
```

## Differences from Python

| Concept | Python | Node.js |
|---------|--------|---------|
| Typed validation | Pydantic BaseModel | Zod schemas |
| Structured output | `llm.with_structured_output(Model, include_raw=True)` | `llm.withStructuredOutput(zodSchema, { includeRaw: true })` |
| Response parsing | `response["parsed"]` + `response["raw"]` | `response.parsed` + `response.raw` |
| Environment variables | `os.environ.get("KEY")` | `process.env.KEY` |
| Module imports | `from src.llm import get_llm` | `import { getLlm } from "./llm.js"` |

## Each Week

```bash
cd nodejs                            # Work from the nodejs directory
git pull upstream main               # Get latest docs + data
cat ../docs/week-NN.md               # Read this week's task
# Build in src/
# Post result to #devbuddy-series
```
