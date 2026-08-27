"""
Demo 1: Unstructured request → crash, then Schema → guaranteed.

The moderator's "Demo 1": ask the LLM for the fields you want — but with NO
schema. The model gives you those fields back as prose, so json.loads() crashes.
Then add a schema constraint (analyze_pr) and get a typed object that ALWAYS
parses. A request is not a contract.

Run: python scripts/week-02/demo-01-prose-vs-structured.py
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore", message=".*Pydantic serializer.*")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.messages import HumanMessage
from src.llm import get_llm
from src.llm_functions import analyze_pr
from src.config import DEVBUDDY_MODEL

PR_TITLE = "Fix login redirect loop in auth-service"
PR_DIFF = (
    "Changed session token validation in src/auth.py lines 42-58.\n"
    "Previously expired tokens caused infinite redirect for 15% of users.\n"
    "Now returns 401 with clear error. No DB changes. Rollback: revert commit.\n"
    "Files: src/auth.py, tests/test_auth.py"
)

print("=" * 70)
print("  Demo 1: Prose → crash, then Schema → success")
print("=" * 70)
print(f"  Model: {DEVBUDDY_MODEL}")
print()
print(f"  INPUT: {PR_TITLE}")
for line in PR_DIFF.split("\n"):
    print(f"         {line}")
print()

# ═══════════════════════════════════════════════════════════════
# Step 1: plain prompt → prose
# ═══════════════════════════════════════════════════════════════
print("-" * 70)
print("  STEP 1: ask for the fields (no schema) → prose")
print("-" * 70)
print()

llm = get_llm(temperature=0.0)
raw = llm.invoke([HumanMessage(content=(
    f"Analyze this PR and return its severity, a one-sentence summary, "
    f"and the affected files.\n\n"
    f"PR Title: {PR_TITLE}\n\nDiff:\n{PR_DIFF}"
))]).content

print("  Raw response:")
for line in raw.strip().split("\n"):
    print(f"  | {line}")
print()

# ═══════════════════════════════════════════════════════════════
# Step 2: json.loads → crash
# ═══════════════════════════════════════════════════════════════
print("-" * 70)
print("  STEP 2: json.loads(raw) → crash")
print("-" * 70)
print()

try:
    data = json.loads(raw)
    print(f"  ✅ parsed unexpectedly: {list(data.keys())}")
except json.JSONDecodeError as e:
    print(f"  ❌ CRASHED: {e}")
    print()
    print("  You asked for the severity, summary, and affected files.")
    print("  The model gave them to you — as prose. With no schema,")
    print("  the model picks the format, and it picked prose.")
    print("  Free text breaks pipelines. Let's fix it.")
print()

# ═══════════════════════════════════════════════════════════════
# Step 3: schema constraint → typed object
# ═══════════════════════════════════════════════════════════════
print("-" * 70)
print("  STEP 3: analyze_pr (schema-constrained) → typed object")
print("-" * 70)
print()

result = analyze_pr(PR_TITLE, PR_DIFF, temperature=0.0)
print(f"  type: {type(result).__name__}  ← typed object, not prose!")
print()
print(result.model_dump_json(indent=2))
print()

print("=" * 70)
print("  The LLM is now a typed function.")
print("  Input → BuildCheck. Your code consumes it directly.")
print("=" * 70)
