# Week 1 — AI-First Engineering: Why, What, How

**Session type:** Kick-off. 1 hour. No code to write — but your environment must be verified.

---

## This Week

- Understand what "AI-first engineering" means vs "bolting AI on"
- See the full DevBuddy architecture — where we're going
- Watch the live demo (it will break — that's the point)
- Get your environment verified and posted to the channel

---

## Before the Session

1. **Read the pre-reading:** [`docs/pre-reading-week-01.md`](pre-reading-week-01.md) (5 min)
   — "AI Engineering vs Traditional Engineering"

2. **Fork the repo, install, and verify your environment:**

### Python

```bash
cd python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env → add your OPENROUTER_API_KEY
python src/verification.py
```

### Node.js

```bash
cd nodejs
npm install
cp .env.example .env
# Edit .env → add your OPENROUTER_API_KEY
node src/verification.js
```

**Expected output:** You should see `✅ VERIFICATION PASSED` with token counts and cost printed for 3 projects.

---

## After the Session

Post your verification output to `#devbuddy-series` with one sentence:

> *"I want DevBuddy to help me with _____."*

**Deadline:** Within 48 hours.

---

## What We Covered

[Ops team fills this in after the session]

## Key Takeaways

-

## Engineer Commitments

- I want DevBuddy to help me with: _______________

## Pre-Reading for Week 2

- Read: "The Model as a Typed Function"
- Distributed 48 hours before the session
