"""
Demo 3: Inference Parameters — Temperature, Max Tokens, Cost

Same PR. Same Pydantic schema. Vary temperature, max_tokens.
Shows what changes and what stays the same.

Run: python scripts/week-02/demo-03-inference-parameters.py
"""
import os, sys, time, warnings
warnings.filterwarnings("ignore", message=".*Pydantic serializer.*")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.llm_functions import analyze_pr
from src.llm import get_llm
from src.config import DEVBUDDY_MODEL

PR_TITLE = "Consolidate error handling across user profile module"
PR_DIFF  = (
    "Moved duplicate try/except blocks from 6 profile endpoints into a shared\n"
    "error_handler.py decorator. No behavior changes — same errors, same messages.\n"
    "Added unit tests for the new decorator. This is prep work for the v2 profiles API.\n"
    "Files: src/profiles/error_handler.py (+80, new), src/profiles/views.py (-120),\n"
    "       tests/test_error_handler.py (+45, new)"
)

print("=" * 65)
print("  Demo 3: Inference Parameters — Temp, Max Tokens, Cost")
print("=" * 65)
print(f"  Model: {DEVBUDDY_MODEL}")
print()
print(f"  INPUT: {PR_TITLE}")
print(f"         {PR_DIFF}")
print()

# ═══════════════════════════════════════════════════════════════
# Part 1: Temperature — determinism vs. judgment
# ═══════════════════════════════════════════════════════════════
print("─" * 65)
print("  PART 1: Temperature — determinism vs. judgment")
print("─" * 65)
print()

print("  temp=0.0 (deterministic) — same input, run twice:")
for i in range(2):
    r = analyze_pr(PR_TITLE, PR_DIFF, temperature=0.0)
    print(f"    run {i+1}: severity={r.severity}  summary=\"{r.summary}\"")
print("    → same verdict, consistent phrasing.")
print()

print("  temp=1.0 (creative) — same input, run twice:")
for i in range(2):
    r = analyze_pr(PR_TITLE, PR_DIFF, temperature=1.0)
    print(f"    run {i+1}: severity={r.severity}  summary=\"{r.summary}\"")
print("    → same verdict, but the phrasing drifts more.")
print()

print("  Key: every run returned a VALID BuildCheck — the schema guarantees")
print("  validity at ANY temperature. Temperature barely moves the verdict; it")
print("  only nudges the phrasing. temp=0 is a reproducibility choice (tests, CI),")
print("  not a correctness rule. (Where temperature matters more is free-text")
print("  reasoning — see demo-04, the sketchpad.)")
print()

# ═══════════════════════════════════════════════════════════════
# Part 2: Max Tokens — truncation kills structured output
# ═══════════════════════════════════════════════════════════════
print("─" * 65)
print("  PART 2: Max Tokens — cost guard or truncation risk?")
print("─" * 65)
print()

for limit in [512, 200, 50, 15, 8]:
    try:
        result = analyze_pr(PR_TITLE, PR_DIFF, temperature=0.0, max_tokens=limit)
        print(f"  max_tokens={limit:>3}: ✅ {result.severity}")
    except Exception as e:
        msg = str(e).replace("\n", " ")
        print(f"  max_tokens={limit:>3}: ❌ {msg}")

print()
print(f"  Set max_tokens=512 → safe. Cost ceiling: moderate.")
print(f"  Set max_tokens=200 → still may fail depending on model/provider.")
print(f"  Set max_tokens=8   → truncated. Validation fails.")
print(f"  Rule: max_tokens must fit your schema. Measure, don't guess.")
print()

# ═══════════════════════════════════════════════════════════════
# Part 3: Cost at different temperatures
# ═══════════════════════════════════════════════════════════════
print("─" * 65)
print("  PART 3: Cost — same task, different temperatures")
print("─" * 65)
print()

for temp in [0.0, 0.7]:
    llm = get_llm(temperature=temp)
    start = time.time()
    response = llm.invoke(f"PR: {PR_TITLE}\nDiff: {PR_DIFF}")
    elapsed = time.time() - start

    usage = response.usage_metadata or {}
    inp = usage.get("input_tokens", 0) if hasattr(usage, "get") else 0
    out = usage.get("output_tokens", 0) if hasattr(usage, "get") else 0
    cost = (inp * 0.15 + out * 0.60) / 1_000_000
    print(f"  temp={temp}: {inp}+{out} tokens, ~${cost:.6f}, {elapsed:.2f}s")

print()
print("  temp=0.0 vs temp=0.7 — cost is similar.")
print("  The choice isn't about saving tokens — it's determinism vs. judgment.")
print()
print("=" * 65)
print("  Inference parameters are architectural decisions, not knobs.")
print("=" * 65)
