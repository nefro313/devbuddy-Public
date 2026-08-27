# DevBuddy — Setup Guide (Node.js)

Follow these steps to get DevBuddy running on your machine.

---

## Prerequisites

- **Node.js 20 or later** (`node --version`)
- **npm** (comes with Node.js) or **pnpm**
- **Git**
- An OpenRouter API key (check `#devbuddy-series` or contact the ops team)

---

## Step 1: Fork the Repository

```bash
# Via GitHub CLI
gh repo fork org/devbuddy --clone

# Or via GitHub UI: click Fork → Clone your fork
git clone https://github.com/YOUR_USERNAME/devbuddy.git
cd devbuddy
```

---

## Step 2: Add Upstream Remote

```bash
git remote add upstream https://github.com/org/devbuddy.git
```

Each week you'll run `git pull upstream main` to get the latest docs and data.

---

## Step 3: Install Dependencies

```bash
cd nodejs
npm install
```

This installs all packages listed in `package.json`:
- `@langchain/openai` — OpenRouter LLM calls
- `@langchain/core` — messages, callbacks, runnable interface
- `@langchain/langgraph` — agent orchestration (Week 6)
- `zod` — typed schema validation
- `@langchain/qdrant` — vector store (Week 3)
- `@xenova/transformers` — local embeddings (Week 3)
- `@modelcontextprotocol/sdk` — MCP server/client (Week 5)
- `dotenv` — environment variable loading

---

## Step 4: Configure Your API Key

```bash
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key:

```
OPENROUTER_API_KEY=sk-or-your-actual-key
```

**Never commit `.env` to git.** It's in `.gitignore`.

---

## Step 5: Run the Verification Script

```bash
npm run verify
```

Or directly:

```bash
node src/verification.js
```

You should see output like:

```
============================================================
  DevBuddy Verification — Week 0 (Node.js)
============================================================

[1/3] Checking: auth-service...
  Status:      passing
  Confidence:  30%
  Reason:      I don't have real CI access...
  Tokens:      147 (102 in / 45 out)
  Cost:        $0.000042
  Time:        1.23s
  Type:        Object ← typed object, not a string!

[2/3] Checking: api-gateway...
  ...

============================================================
  ✅ VERIFICATION PASSED
  Runtime:    Node.js v22.5.0
  Model:      openai/gpt-4o-mini
  Total tokens: 441
  Total cost:   $0.000126
  Date:       2026-07-02T10:30:00.000Z
============================================================
```

---

## Step 6: Post to the Channel

Copy your terminal output and post it to `#devbuddy-series` with one sentence:

> *"I want DevBuddy to help me with _____."*

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `OPENROUTER_API_KEY not set` | Did you copy `.env.example` to `.env`? Did you add your key? Are you running from the `nodejs/` directory? |
| `Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@langchain/openai'` | Run `npm install` from the `nodejs/` directory |
| `Error: Cannot find module './llm.js'` | You must run from the `nodejs/` directory: `cd nodejs && node src/verification.js` |
| `node: command not found` | Install Node.js 20+ from [nodejs.org](https://nodejs.org) or via `nvm` |
| `unsupported Node.js version` | Check `node --version`. Must be 20+. Use `nvm install 22` if needed. |
| `Cannot find module 'dotenv/config'` | Run `npm install` — the `dotenv` package may not be installed |
| Verification script times out | Check your network. OpenRouter may be rate-limited on shared keys. |
| `SyntaxError: Cannot use import statement outside a module` | Make sure `package.json` has `"type": "module"`. It should be there by default. |
| `fetch failed` / `ECONNREFUSED` | Check your network / proxy settings. OpenRouter base URL may be blocked by corporate firewall. |
| Anything else | Post in `#devbuddy-series`. Don't DM — public debugging builds shared knowledge. |

---

## Project Structure

```
nodejs/
├── src/
│   ├── llm.js           # OpenRouter client factory (Week 1)
│   ├── verification.js   # Verification script — run this first!
│   ├── schemas.js        # Zod schemas + structured output (Week 2)
│   ├── rag.js            # RAG pipeline (Week 3)
│   ├── tools.js          # Tool definitions (Week 4)
│   ├── mcp_server.js     # MCP server (Week 5)
│   ├── agent.js          # Agent orchestrator (Week 6)
│   ├── guardrails.js     # Input/output guardrails (Week 7)
│   ├── cost_tracker.js   # Cost tracking (Week 7)
│   └── tracing.js        # Tracing + observability (Week 7)
├── node_modules/         # Dependencies (git-ignored)
├── package.json          # Project config + scripts + dependencies
├── package-lock.json     # Locked dependency versions
└── .env                  # Your API key (git-ignored)
```

---

## Scripts

| Command | What it does |
|---------|-------------|
| `npm run verify` | Run the Week 0 verification script |
| `npm test` | Run the test suite (available from Week 2) |
| `npm run test:watch` | Run tests in watch mode |

---

## Keyboard Shortcuts

None yet — but as packages are added, shortcuts will be documented here.

---

## What's Next

- Week 1 is the kick-off session. You'll see the full DevBuddy architecture.
- The verification script you just ran is a microcosm of what DevBuddy becomes.
- Each week: `cd nodejs && git pull upstream main`, read `../docs/week-NN.md`, build in `src/`.

---

## Switching Between Languages

If you're using both Python and Node.js:

```bash
# Python
cd python
source .venv/bin/activate

# Node.js
cd nodejs
# (no venv needed — node_modules is local)
```

The architectures and patterns are identical. The language is just syntax.
