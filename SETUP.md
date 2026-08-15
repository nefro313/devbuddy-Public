# DevBuddy — Setup Guide (Python)

Follow these steps to get DevBuddy running on your machine.

---

## Prerequisites

- Python 3.11 or later (`python --version`)
- Git
- [uv](https://docs.astral.sh/uv/) (fast Python package manager, recommended)
- `make` (optional; macOS/Linux only. On Windows use `python install.py`)
- An OpenRouter API key (check `#devbuddy-series` or contact the ops team)

Install uv once:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell):
# powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## Quick Path (recommended)

From the `python/` directory, one command does the whole setup: creates the virtual environment, installs the Week 0 dependencies, and scaffolds your `.env`. It works on Windows, macOS, and Linux and needs nothing but Python.

```bash
cd python
python install.py
# then edit python/.env, add your OPENROUTER_API_KEY, and:
python run.py
```

On macOS/Linux with `make` installed, `make install` and `make run` do the same thing. That's it. The steps below explain it in detail.

---

## Step 1: Fork the Repository

```bash
# Via GitHub CLI
gh repo fork org/devbuddy --clone

# Or via GitHub UI: click Fork -> Clone your fork
git clone https://github.com/YOUR_USERNAME/devbuddy.git
cd devbuddy
```

---

## Step 2: Add Upstream Remote

```bash
git remote add upstream https://github.com/org/devbuddy.git
```

Each week you'll run `git fetch upstream` and check out that week's branch (see "Branch Layout" below).

---

## Step 3: Set Up the Python Environment

We use uv for fast, reproducible installs. The Week 0 dependency set is intentionally small, so this installs in seconds.

```bash
cd python
python install.py   # creates .venv, installs Week 0 deps, scaffolds .env (Windows/macOS/Linux)
```

If you prefer to run the steps yourself:

```bash
cd python
uv venv                          # creates .venv, picks Python 3.11+
uv pip install -r requirements.txt
```

Later weeks pull heavier libraries. Install them only when you reach that week:

```bash
uv pip install -e ".[rag]"       # Week 3 (RAG: chromadb, embeddings, ...)
uv pip install -e ".[mcp]"       # Week 5 (MCP)
uv pip install -e ".[agent]"     # Week 6 (Agent: langgraph)
uv pip install -e ".[obs]"       # Week 7 (LLMOps: langfuse, otel, prometheus)
```

<details>
<summary>No uv either? Plain venv + pip still works</summary>

```bash
cd python
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
```
</details>

---

## Step 4: Configure Your API Key

`make install` already copied `.env.example` to `.env` for you. Open `python/.env` and set your key:

```
OPENROUTER_API_KEY=sk-or-your-actual-key
```

(If you set up manually, run `cp .env.example .env` first.)

**Never commit `.env` to git.** It's in `.gitignore`. Your key is loaded automatically from `python/.env` at runtime, so no manual `export` is needed.

---

## Step 5: Run the Verification Script

```bash
python run.py
# same as: uv run python src/verification.py  (or `make run` on macOS/Linux)
```

You should see output like:

```
============================================================
  DevBuddy Verification — Week 0
============================================================

[1/3] Checking: auth-service...
  Status:      passing
  Confidence:  30%
  Reason:      I don't have real CI access...
  Tokens:      147 (102 in / 45 out)
  Cost:        $0.000042
  Time:        1.23s
  Type:        BuildCheck ← typed object, not a string!

============================================================
  ✅ VERIFICATION PASSED
============================================================
```

---

## Step 6: Post to the Channel

Copy your terminal output and post it to `#devbuddy-series` with one sentence:

> *"I want DevBuddy to help me with _____."*

---

## Branch Layout — One Branch Per Week

This repo uses **one branch per week**. `main` is the Week 0 baseline: stub files you build from. Each `week-NN` branch is that week's worked checkpoint. It adds `docs/week-NN.md`, the pre-reading, the completed solution under `src/`, and test fixtures under `shared/`.

```bash
git fetch upstream
git checkout week-02        # switch to a specific week's materials
```

Available now: `week-01` through `week-06` (Week 6 = Agentic Workflows is the latest). If you miss a session, check out the next week's branch to get a clean starting point.

---

## Week 7 — The Observability Stack

Everything runs locally from the repo root. No accounts, no keys beyond the OpenRouter one you already have.

```bash
docker compose up -d
```

That brings up fifteen containers. Five of them you actually look at:

| | URL | Login | Answers |
|---|---|---|---|
| **Prometheus** | http://localhost:9090 | — | Is the system healthy? |
| **Grafana** | http://localhost:3000 | `admin` / `devbuddy` | ...shown to a human, with alerts |
| **Uptrace** | http://localhost:14318 | `admin@uptrace.local` / `devbuddy` | Which step was slow? |
| **Langfuse** | http://localhost:3001 | `devbuddy@local.dev` / `devbuddy123` | Was the answer good, what did it cost? |
| **Qdrant** | http://localhost:6333/dashboard | — | The Week 3 vector store |

Two more feed Prometheus the infrastructure half of the picture, which DevBuddy's own `/metrics` cannot see: **cAdvisor** (`:8082`) for per-container CPU, memory and restarts, and **node-exporter** (`:9100`) for host CPU, load and memory. On macOS and Windows, node-exporter reports the Docker Desktop VM rather than your actual machine.

The remaining eight are storage that Langfuse and Uptrace need (Postgres, ClickHouse, Redis, MinIO — one set each). You will never open them.

Weeks 1–6 only need Qdrant, so if the full stack is too heavy:

```bash
docker compose up -d qdrant
```

### Then run it

```bash
cd python && uv run python src/mcp_server.py
```

```bash
cd python && uv run python src/agent.py
```

The agent starts its own metrics server on `:8001`, which is what Prometheus scrapes. Confirm the target is `UP` at http://localhost:9090/targets — if DevBuddy is not running, that target is legitimately down.

### The one thing to actually look at

Run a query, take the `trace_id` the agent prints, and find it in **both** Uptrace and Langfuse. Same id, two different views of one request: the waterfall that shows which step burned the seconds, and the prompts that show whether the answer was any good. That link is the whole point of the week.

### Self-hosted vs Langfuse Cloud

Self-hosting Langfuse costs six containers (Postgres, ClickHouse, Redis, MinIO, web, worker). That is the real price of "no data leaves the laptop". To swap it for the managed service, create a project at [cloud.langfuse.com](https://cloud.langfuse.com) and put three lines in `python/.env`:

```
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

Then `docker compose up -d` everything except the `langfuse-*` services. No code changes — `src/tracing.py` only reads settings.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `make: command not found` | You're likely on Windows (`make` is a Unix tool). Use `python install.py` then `python run.py` instead. No make needed. |
| `uv: command not found` | Fine. `python install.py` falls back to venv + pip automatically. Install uv only if you want faster setups. |
| `OPENROUTER_API_KEY not set` | The key is auto-loaded from `python/.env`. Make sure `python/.env` exists and contains your real key (not the placeholder from `.env.example`). |
| `ModuleNotFoundError: langchain_openai` | Run `python install.py` from the `python/` directory. |
| `ModuleNotFoundError: src` | Run from the `python/` directory: `cd python && python run.py`. |
| `python: command not found` | Use `python3` (e.g. `python3 install.py`). |
| Verification script times out | Check your network. OpenRouter may be rate-limited on shared keys. |
| Prometheus target `devbuddy` is DOWN | Nothing is running. The metrics server lives in the DevBuddy process — start `src/agent.py` and it appears. |
| Grafana panels empty right after a run | Prometheus *pulls* every 15s, and `src/agent.py` only lives ~90s — the last counter values are never scraped, and instant queries go stale 5 minutes after the process exits. Use `max_over_time(devbuddy_requests_total[30m])`, or keep a process running. Traces in Uptrace and Langfuse are pushed, so they are always complete. |
| `langfuse-worker` restarting, everything else healthy | `ENCRYPTION_KEY` must be exactly 64 hex characters, and **quoted** in the compose file. An all-digit value is parsed by YAML as the integer `0`. Regenerate with `openssl rand -hex 32`. |
| Traces in Uptrace but not Langfuse | Check `langfuse-worker` logs. Ingestion is asynchronous: web accepts the event, the worker writes it. |
| No spans anywhere, script exits fine | The exporters batch. Call `tracing.flush()` before a short-lived process exits — `src/agent.py` already does. |
| Port already in use on 3000/9090/5432/6379 | Something else is running. Ports are set in `docker-compose.yml`; the databases deliberately publish nothing. |
| Guardrail blocks a legitimate question | Lower the aggressiveness or set `GUARDRAILS_ENABLED=false` in `.env` to compare. A false positive is a real cost — see the `off_topic` classifier prompt. |
| Anything else | Post in `#devbuddy-series`. Don't DM — public debugging builds shared knowledge. |

---

## What's Next

- Week 1 is the kick-off session. You'll see the full DevBuddy architecture.
- The verification script you just ran is a microcosm of what DevBuddy becomes.
- Each week: `git fetch upstream && git checkout week-NN`, read `docs/week-NN.md`, build in `python/src/`.
