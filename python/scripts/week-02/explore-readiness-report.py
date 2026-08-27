"""
Week 2 — Validate a ServiceReadinessReport from mock data.

Loads one JSON scenario and validates it against the schema.
This is your starting point. Your self-learning assignment is below.

Run: python scripts/week-02/explore-readiness-report.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.schemas import ServiceReadinessReport
from src.config import DEVBUDDY_MODEL

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..", "shared", "data",
)

print("=" * 70)
print("  ServiceReadinessReport — Reference Validation")
print("=" * 70)
print(f"  Model: {DEVBUDDY_MODEL}")
print()

# ── Reference: healthy scenario ───────────────────────────────
path = os.path.join(DATA_DIR, "service-readiness-healthy.json")
print(f"  Loading {path}...")

with open(path) as f:
    data = json.load(f)

report = ServiceReadinessReport.model_validate(data)
print(f"  ✅ Validated — {type(report).__name__}(")
print(f"       service.name   = {report.service.name}")
print(f"       service.version= {report.service.version}")
print(f"       build.status   = {report.build.status}")
print(f"       deploy.history = {len(report.deployment.recent_deploys)} deploys")
print(f"       verdict.ready  = {report.verdict.ready}")
print(f"       verdict.conf   = {report.verdict.confidence}")
print(f"       blockers       = {report.verdict.blockers}")
print(f"       evidence       = {len(report.evidence)} chunks")
print(f"     )")

print()


# ═══════════════════════════════════════════════════════════════════
# TAKE-HOME ASSIGNMENT
# ═══════════════════════════════════════════════════════════════════
#
# PART A — Load the other two scenarios:
#   1. Extend this script to also load and validate:
#      shared/data/service-readiness-degraded.json
#      shared/data/service-readiness-unknown.json
#   2. Add the same tests to tests/test_schemas.py
#      (follow the healthy example that's already there)
#
# PART B — LLM integration & Agentic Self-Correction:
#   Use src.llm_functions.generate_readiness_report() to feed
#   the mock data to the LLM and get back a typed report.
#   Example:
#
#     import json
#     from src.llm_functions import generate_readiness_report
#
#     with open('../shared/data/service-readiness-healthy.json') as f:
#         data = json.load(f)
#
#     report = generate_readiness_report(
#         service_name=data['service']['name'],
#         build_data=data['build'],
#         deploy_data=data['deployment'],
#         temperature=0.0,
#     )
#
#     # report is a typed ServiceReadinessReport — no parsing needed!
#     print(report.model_dump_json(indent=2))
#
#   1. Run this for all 3 scenarios. Compare the LLM's verdict
#      to the hand-written JSON — does the model agree?
#   2. Your schema has custom @model_validators (e.g., if ready=True, 
#      blockers must be empty). What happens if the LLM violates this? 
#      Pydantic throws a ValidationError.
#   3. CHALLENGE: Catch the pydantic.ValidationError, extract the error 
#      string, and send it back to the LLM as a new HumanMessage: 
#      "Your output failed validation: {error}. Please correct it."
#      (This is the foundation of Agentic Self-Correction!)
# ═══════════════════════════════════════════════════════════════════
