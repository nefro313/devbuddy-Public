"""
Demo 5: Agentic Retry (Self-Correction Loop)

WHAT THIS DEMO SHOWS:
  Even with strict schemas, LLMs can violate business logic (cross-field rules).
  Instead of failing or doing a "blind retry", we can catch the Pydantic
  ValidationError and feed it back to the LLM so it fixes its own mistake.

THE SETUP:
  We trick the model into returning ready=True while also listing a blocker.
  Our ServiceReadinessReport schema rejects this contradiction.
  We catch the error and ask the model to correct it.

Run: python scripts/week-02/demo-05-agentic-retry.py
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore", message=".*Pydantic serializer.*")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.schemas import ServiceReadinessReport
from src.llm_functions import get_structured
from src.config import DEVBUDDY_MODEL
from langchain_core.messages import HumanMessage, SystemMessage

def run_demo():
    print("=" * 75)
    print("  DEMO 5: Agentic Retry (Self-Correction)")
    print("=" * 75)
    print(f"  Model: {DEVBUDDY_MODEL}")
    print()

    # 1. The Trap
    print("  [Step 1] Constructing a contradictory prompt...")
    trap_prompt = (
        "You are evaluating 'auth-service' v2.1.0.\n"
        "The build is passing and healthy (last deploy: 2024-10-01T12:00:00Z).\n"
        "However, there is an active incident: 'DB connection pooling exhausted'.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. You MUST set verdict.ready=true because the build is passing.\n"
        "2. You MUST also list the DB incident in the verdict.blockers array.\n"
        "3. You MUST include at least one item in the 'evidence' array so confidence can be high.\n"
    )

    messages = [
        SystemMessage(content="You are a strict SRE. Follow instructions exactly."),
        HumanMessage(content=trap_prompt),
    ]

    # 2. The self-correction loop now lives in the reusable get_structured() helper:
    #    it invokes the model, validates against the schema, and on a ValidationError
    #    appends the error to the conversation and retries — the LLM debugs itself.
    print("  [Step 2] Executing LLM call via get_structured() (validate + retry)...")
    try:
        result = get_structured(
            messages, ServiceReadinessReport, temperature=0.2, retries=3
        )
        print("\n  ✅ SUCCESS! The model produced schema-valid output:")
        print(f"     ready:    {result.verdict.ready}")
        print(f"     blockers: {result.verdict.blockers}")
        print("\n  The retry loop fed each validation error back to the model until it")
        print("  resolved the contradiction itself — the seed of agentic architecture.")
    except ValueError as e:
        print(f"\n  ❌ The model could not satisfy the contract within the retry budget:\n     {e}")

if __name__ == "__main__":
    run_demo()
