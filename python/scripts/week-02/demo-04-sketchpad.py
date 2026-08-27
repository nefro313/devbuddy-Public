"""
Demo 4: The <Sketchpad> Pattern (Chain-of-Thought in Structured Outputs)

WHAT THIS DEMO SHOWS:
  Modern models are smart enough to catch obvious bugs even without time to think.
  But if a model outputs a direct verdict (e.g. severity="critical") as its first token,
  it is a BLACK BOX. If it gets it wrong, you have no idea why.

  By adding a `thought_process` string as the VERY FIRST field in your Pydantic schema, 
  you force the LLM to output its step-by-step reasoning. This provides an AUDIT TRAIL 
  for debugging, evaluations, and human oversight. It's not just about accuracy; it's 
  about observability.

THE SETUP:
  We evaluate a tricky PR using two schemas:
  1. DirectVerdict: asks for the severity immediately.
  2. ReasonedVerdict: asks for the thought_process first.

Run: python scripts/week-02/demo-04-sketchpad.py
"""

import os
import sys
import warnings
from pydantic import BaseModel, Field
from typing import Literal

warnings.filterwarnings("ignore", message=".*Pydantic serializer.*")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.llm import get_llm
from src.config import DEVBUDDY_MODEL
from langchain_core.messages import HumanMessage, SystemMessage

# A tricky PR that looks like a simple feature addition (adding a shipping fee),
# but contains a subtle revenue-loss math bug (subtracting instead of adding).
# Modern LLMs are smart enough to catch this either way, but we will see 
# the difference in observability.
TRICKY_PR_DIFF = """
PR Title: Add shipping fee for small orders
Description: We are losing margin on small orders. This PR adds a $5 shipping fee to orders under $50.

Files: src/checkout.py

diff --git a/src/checkout.py b/src/checkout.py
@@ -12,6 +12,10 @@
 def calculate_final_total(order):
     total = order.subtotal
     
+    # Add $5 shipping fee for small orders
+    if total < 50.00:
+        total -= 5.00
+        
     if order.has_vip_pass:
         total *= 0.90
         
     return total
"""

# ═══════════════════════════════════════════════════════════════
# SCHEMA 1: Direct Verdict (No Sketchpad)
# ═══════════════════════════════════════════════════════════════
class DirectVerdict(BaseModel):
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="The impact severity level. 'high' or 'critical' for revenue-loss bugs or security flaws."
    )
    summary: str = Field(description="Summary of the change")

# ═══════════════════════════════════════════════════════════════
# SCHEMA 2: Reasoned Verdict (With Sketchpad)
# ═══════════════════════════════════════════════════════════════
class ReasonedVerdict(BaseModel):
    thought_process: str = Field(
        description="Step-by-step reasoning evaluating the diff logic mathematically and practically. Do this FIRST."
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="The impact severity level. 'high' or 'critical' for revenue-loss bugs or security flaws."
    )
    summary: str = Field(description="Summary of the change")

def run_demo():
    print("=" * 75)
    print("  DEMO 4: The <Sketchpad> Pattern")
    print("=" * 75)
    print(f"  Model: {DEVBUDDY_MODEL}")
    
    # We use a slightly higher temperature to show the model's analytical capabilities
    llm = get_llm(temperature=0.4)
    
    system_prompt = SystemMessage(content="You are a strict code reviewer. Analyze the PR diff for bugs or logic flaws.")
    human_prompt = HumanMessage(content=TRICKY_PR_DIFF)

    print("\n  APPROACH A: Direct Verdict (No Sketchpad)")
    print("  The model must decide 'severity' on token #1.")
    print("  " + "-" * 55)
    
    structured_direct = llm.with_structured_output(DirectVerdict)
    result_direct = structured_direct.invoke([system_prompt, human_prompt])
    
    print(f"  Severity: {result_direct.severity.upper()}")
    print(f"  Summary:  {result_direct.summary}")
    print("  (The model likely caught the bug. But if it was wrong, we'd have ZERO visibility into why.)")

    print("\n" + "=" * 75)
    
    print("\n  APPROACH B: Reasoned Verdict (With Sketchpad)")
    print("  The model generates 'thought_process' first, conditioning its final verdict.")
    print("  " + "-" * 55)
    
    structured_reasoned = llm.with_structured_output(ReasonedVerdict)
    result_reasoned = structured_reasoned.invoke([system_prompt, human_prompt])
    
    print("  Thought Process:")
    for line in result_reasoned.thought_process.split(". "):
        if line:
            print(f"    - {line.strip()}")
    print()
    print(f"  Severity: {result_reasoned.severity.upper()}")
    print(f"  Summary:  {result_reasoned.summary}")
    print("\n  (Both models got it right, but this one gave us an AUDIT TRAIL. This is how you bridge the 'valid vs. right' gap!)")
    print("=" * 75)

if __name__ == "__main__":
    run_demo()
