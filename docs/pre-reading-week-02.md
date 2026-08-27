# The Model as a Typed Function

> Pre-reading for Week 2. 5 minutes.

---

## The Problem

You call an LLM. It returns text. You try to parse it with `json.loads()`. It works in dev. In production, the model returns slightly different formatting. Your pipeline breaks. On-call wakes up.

This is **code slop** — free-text responses that downstream code can't reliably consume.

---

## The Solution

Treat the LLM as a **typed function**:

```
input:  { title: "Fix login bug", diff: "changed auth.py line 42" }
output: BuildCheck(project="auth-service", severity="high", summary="...", affected_files=["auth.py"])
```

The model is constrained by a schema. It returns a typed object — not prose. Your code imports it directly. No regex. No `try/except json.loads()`. No hoping.

---

## The Three Levers

| Lever | What it controls | The rule |
|-------|-----------------|----------|
| **Prompt engineering** | What the model tries to do | System message = constitution. User message = task. |
| **Schema constraint** | What shape the output must have | Pydantic model + `with_structured_output()`. |
| **Inference parameters** | How deterministic the output is | `temperature=0` for structured output. |

---

## What You'll Build Today

Open `src/schemas.py`. It already contains two schema families:

- **`BuildCheck`** — a flat 4-field model for PR analysis. This is the in-session exercise. You'll reproduce it, break it, vary temperature, and add few-shot examples.
- **`ServiceReadinessReport`** — a composed schema with 5 nested models, `Optional` fields, and cross-field validators. This is what DevBuddy produces at Week 7. You'll explore it during self-learning with mock data (no API calls needed).

The demo scripts in `scripts/week-02/` show why this matters — free-text crashes a parser, structured output saves it. The "request vs contract" distinction is the most important idea in AI-first engineering.

**You'll also:** vary temperature, break the schema on purpose, add a few-shot example, and see what happens. The skill isn't getting it right the first time — it's building systems that survive the breakage.

---

## One Thing to Try

Before the session, run the explore script for your language:

**Python:**
```bash
python scripts/week-02/explore-readiness-report.py
```

**Node.js:**
```bash
node scripts/week-02/explore-readiness-report.js
```

It loads mock JSON scenarios and validates them against `ServiceReadinessReport`. You'll see nested models, optional fields, and cross-field validators in action — before you write a single line of code. Ask yourself: *"How would I build this schema? What would break if I changed field types?"*
