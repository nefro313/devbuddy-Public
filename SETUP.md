# DevBuddy — Setup Guide

---

## Prerequisites

- Python 3.11 or later (`python --version`)
- Node.js 20 or later (`node --version`) — for Promptfoo evals (Week 7)
- Docker Desktop (or equivalent) — for Qdrant vector database (Week 3+)
- Git
- An OpenRouter API key (check `#devbuddy-series` or contact the ops team)

---

## Step 1: Fork the Repository

```bash
# Via GitHub CLI
gh repo fork org/devbuddy --clone

# Or via GitHub UI: click Fork → then clone your fork
git clone https://github.com/YOUR_USERNAME/devbuddy.git
cd devbuddy
```

---

## Step 2: Add Upstream Remote

```bash
git remote add upstream https://github.com/org/devbuddy.git
```

Each week: `git pull upstream main` to get the latest.

---

## Step 3: Set Up Python Environment

```bash
cd python
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

---

## Step 4: Start Qdrant (Week 3+)

Qdrant is the vector database for RAG. Start it with Docker:

```bash
cd devbuddy   # repo root (where docker-compose.yml lives)
docker-compose up -d   # or 'docker compose up -d' if you have the compose plugin
```

Verify it's running:

```bash
curl http://localhost:6333/healthz
# → {"title":"healthz","version":"..."}
```

Dashboard at http://localhost:6333/dashboard

---

## Step 5: Configure Your API Key

```bash
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key:

```
OPENROUTER_API_KEY=sk-or-your-actual-key
DEVBUDDY_MODEL=openai/gpt-4o-mini
```

Change `DEVBUDDY_MODEL` to any OpenRouter model string (`anthropic/claude-sonnet`, `google/gemini-flash`, etc.).

**Never commit `.env`.** It's in `.gitignore`.

---

## Step 6: Run the Verification Script

```bash
python src/verification.py
```

Expected output:

```
============================================================
  DevBuddy Verification — Week 0
============================================================

[1/3] Asking: Say 'connected' in exactly one word.
  Response:    connected
  Tokens:      19 (16 in / 3 out)
  Cost:        ~$0.000004 (estimated — check OpenRouter dashboard for billing)
  Time:        2.12s

[2/3] Asking: What is 2 + 2? Answer with just the number.
  Response:    4
  Tokens:      23 (21 in / 2 out)
  Cost:        ~$0.000004 (estimated — check OpenRouter dashboard for billing)
  Time:        0.76s

[3/3] Asking: Name one programming language in one word.
  Response:    Python
  Tokens:      17 (15 in / 2 out)
  Cost:        ~$0.000003 (estimated — check OpenRouter dashboard for billing)
  Time:        0.58s

============================================================
  ✅ VERIFICATION PASSED
  Python:        3.13.5
  Model:         openai/gpt-4o-mini
  Total tokens:  59
  Total cost:    ~$0.000012 (estimated)
  Date:          2026-06-27T21:04:17

  Post this output to #devbuddy-series to confirm.

  What do you want DevBuddy to help you with?
  _______________________________________________
============================================================
```

---

## Step 7: Run the Integration Test

```bash
python tests/test_integration.py
```

This validates everything end-to-end:

```
============================================================
  DevBuddy Integration Test — Week 0
============================================================

  ✅ .env configured: model=openai/gpt-4o-mini, key=********i7U9
  ✅ OpenRouter connected: 1.2s, tokens=15+3
  ✅ Structured output: SmokeTest(status='ok')
  ✅ Cost tracked: 18+5 tokens, ~$0.000006 (estimated)
  ⏭️  Model swap skipped (set DEVBUDDY_MODEL_ALT in .env to test)

============================================================
  ✅ ALL 5 TESTS PASSED
============================================================
```

---

## Step 8: Post to the Channel

Copy your terminal output and post it to `#devbuddy-series` with one sentence:

> *"I want DevBuddy to help me with _____."*

---

## Step 9: Verify Promptfoo (Optional)

Promptfoo runs evals against your LLM outputs. This smoke test demonstrates:
- **Multi-model comparison** — same prompt, GPT-4o-mini vs Gemini Flash
- **Assertions** — does the output contain "4"? Is it valid JSON?
- **Latency tracking** — response time measured per call
- **Cost tracking** — token cost shown per call (automatic, no assertion needed)

```bash
cd ../shared/evals
export OPENROUTER_API_KEY=sk-or-your-key
npx promptfoo@latest eval --config week-00-smoke.yaml
```

You'll see a table comparing both models across all 4 test cases — pass/fail, latency, and cost per call.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `OPENROUTER_API_KEY not set` | Did you copy `.env.example` to `.env`? Add your key? Running from `python/`? |
| `ModuleNotFoundError: langchain_openai` | `pip install -r requirements.txt` from `python/` |
| `ModuleNotFoundError: src` | You must run from `python/`: `cd python && python src/verification.py` |
| `python: command not found` | Try `python3`, or install Python 3.11+ |
| Script times out | Check network. Shared sandbox keys may be rate-limited. |
| Anything else | Post in `#devbuddy-series`. Public debugging builds shared knowledge. |
