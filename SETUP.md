# DevBuddy — Setup Guide

Choose your language and follow the steps below.

---

## Prerequisites

- **Python 3.11+** (`python --version`) — for the Python blueprint
- **Node.js 20+** (`node --version`) — for the Node.js blueprint + Promptfoo evals
- **Git**
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

## Step 3: Set Up Python Environment

```bash
cd python
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
cp .env.example .env
# Edit .env → add your OPENROUTER_API_KEY

python src/verification.py       # verify your environment
python tests/test_integration.py  # run the integration test suite
```

</details>

### Node.js

Full guide: [`nodejs/SETUP.md`](nodejs/SETUP.md) — or continue below.

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
python src/verification.py
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

## Step 4: Post to the Channel

Copy your terminal output and post it to `#devbuddy-series` with one sentence:

> _"I want DevBuddy to help me with **\_**."_

---

## Troubleshooting

| Problem                                 | Fix                                                                                                        |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `OPENROUTER_API_KEY not set`            | Did you copy `.env.example` to `.env`? Did you add your key? Are you running from the `python/` directory? |
| `ModuleNotFoundError: langchain_openai` | Run `pip install -r requirements.txt` from the `python/` directory                                         |
| `ModuleNotFoundError: src`              | You must run from the `python/` directory: `cd python && python src/verification.py`                       |
| `python: command not found`             | Use `python3` instead, or install Python 3.11+                                                             |
| Verification script times out           | Check your network. OpenRouter may be rate-limited on shared keys.                                         |
| Anything else                           | Post in `#devbuddy-series`. Don't DM — public debugging builds shared knowledge.                           |

---

## What's Next

- Week 1 is the kick-off session. You'll see the full DevBuddy architecture.
- The verification script you just ran is a microcosm of what DevBuddy becomes.
- Each week: `cd python && git pull upstream main`, read `../docs/week-NN.md`, build in `src/`.
