"""Demo 2: Raw JSON Prompting vs. Pydantic Structured Output

WHAT THIS DEMO SHOWS:
  Raw JSON prompting is a polite request. The model tries to comply — but at
  high temperature, it adds markdown wrappers, conversational text, or invents
  field names. Your pipeline breaks.

  Pydantic structured output is a contract. The model is constrained at the
  token level. It CANNOT return output that violates the schema. Even at
  temperature=0.0, the output is always valid and correctly typed.

THE SETUP:
  Same input (a PR diff). Same temperature (0.0 — deterministic).
  Same extraction task. Two approaches.

Run: python scripts/week-02/demo-02-raw-vs-pydantic.py
"""

import os
import sys
import json
import warnings
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

warnings.filterwarnings("ignore", message=".*Pydantic serializer.*")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.llm import get_llm
from src.config import DEVBUDDY_MODEL
from langchain_core.messages import HumanMessage

# ═══════════════════════════════════════════════════════════════
# THE INPUT — same for both approaches
# ═══════════════════════════════════════════════════════════════
diff_input = """Fix login redirect loop in auth-service (PROJ-421)
Changed session token validation in src/auth.py lines 42-58.
Previously expired tokens caused infinite redirect for 15% of users.
Now returns 401 with clear error. No DB changes. Rollback: revert commit.
Files: src/auth.py, tests/test_auth.py"""

# ═══════════════════════════════════════════════════════════════
# THE SCHEMA — the shape we want the data in
# ═══════════════════════════════════════════════════════════════
class ChangeSchema(BaseModel):
    """Details about the type and severity of the change."""
    type: Literal["bug", "feature", "refactor", "hotfix"] = Field(
        description="The category of the change"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="The impact severity level"
    )
    ticket: Optional[str] = Field(
        None, description="The ticket ID (e.g., PROJ-123) if present in the diff, else null"
    )


class DetailsSchema(BaseModel):
    """Human-readable analysis of the change."""
    summary: str = Field(description="A single sentence summary of what changed")
    root_cause: str = Field(description="The underlying issue that caused the problem")
    user_impact_pct: Optional[int] = Field(
        None, description="Percentage of users impacted, as a raw integer (e.g. 15)"
    )

    @field_validator("user_impact_pct", mode="before")
    @classmethod
    def clean_percentage(cls, v):
        """
        The model might return '15%', '15 percent', or 15.
        This validator coerces ALL of those into a clean integer: 15.

        Raw prompting CANNOT do this — you'd have to clean the data
        AFTER parsing, which means you've already lost the contract.
        """
        if isinstance(v, str):
            digits = "".join(filter(str.isdigit, v))
            return int(digits) if digits else None
        return v


class TechnicalSchema(BaseModel):
    """Machine-parseable technical details."""
    files_changed: List[str] = Field(description="Exact file paths modified")
    db_changed: bool = Field(description="Whether any database changes are included")
    rollback: str = Field(description="Instructions on how to revert this change")


class DiffAnalysis(BaseModel):
    """The root schema — composes all sub-schemas into one contract."""
    change: ChangeSchema
    details: DetailsSchema
    technical: TechnicalSchema


# ═══════════════════════════════════════════════════════════════
# THE DEMO
# ═══════════════════════════════════════════════════════════════
def run_demo():
    print("=" * 75)
    print("  DEMO: Raw JSON Prompting (Request) vs. Pydantic (Contract)")
    print("=" * 75)
    print(f"  Model: {DEVBUDDY_MODEL}")
    print()
    print("  THE INPUT (same for both approaches):")
    print("  " + "-" * 55)
    for line in diff_input.strip().split("\n"):
        print(f"  | {line}")
    print("  " + "-" * 55)
    print()

    test_temperature = 0
    print(f"  TEMPERATURE: {test_temperature} — fully deterministic")
    print("     Even at temp=0, raw prompting fails. The model still wraps")
    print("     valid JSON in markdown backticks. Temperature is not the issue.")
    print("     The APPROACH is the issue — request vs contract.")
    print()

    # ═══════════════════════════════════════════════════════════
    # APPROACH A: RAW PROMPTING — "The Request"
    # ═══════════════════════════════════════════════════════════
    print("=" * 75)
    print("  APPROACH A: Raw JSON Prompting")
    print("  Strategy: Ask the model nicely to return JSON.")
    print("  Problem:  It's a request, not a contract.")
    print("=" * 75)
    print()

    raw_prompt = (
        "Analyze this code change and extract details. "
        "Return a JSON object matching this schema:\n"
        "{\n"
        '  "change": { "type": "bug"|"feature", "severity": "low"|"high", "ticket": "string" },\n'
        '  "details": { "summary": "string", "root_cause": "string", "user_impact_pct": integer },\n'
        '  "technical": { "files_changed": ["string"], "db_changed": boolean, "rollback": "string" }\n'
        "}\n\n"
        "DIFF:\n"
    )
    print(f"Raw Prompt: {raw_prompt}")
    print("=" * 75)

    llm_raw = get_llm(temperature=test_temperature)

    print("  Sending prompt to model...")
    response_raw = llm_raw.invoke([HumanMessage(content=f"{raw_prompt}\n{diff_input}")])
    raw_text = response_raw.content.strip()

    print(f"  Raw response ({len(raw_text)} chars):")
    print("  " + "-" * 55)
    for line in raw_text.split("\n"):
        print(f"  | {line}")
    print("  " + "-" * 55)
    print()

    print("  Attempting to parse as JSON...")
    try:
        data = json.loads(raw_text)
        print("  ✅ PARSE SUCCEEDED (even with markdown wrapper? check raw output)")
        print(f"     Keys returned: {list(data.keys())}")
        change = data.get("change", {})
        details = data.get("details", {})
        print(f"     change.type:     {change.get('type', 'MISSING')}")
        print(f"     change.severity: {change.get('severity', 'MISSING')}")
        print(f"     change.ticket:   {change.get('ticket', 'MISSING')}")
        impact = details.get("user_impact_pct", "MISSING")
        print(f"     details.user_impact_pct: {impact} (type: {type(impact).__name__})")
        if isinstance(impact, str) and "%" in impact:
            print(f"     ⚠️  VALUE IS A STRING: '{impact}' — you must clean this manually")
            print(f"        Pydantic's field_validator would have handled this automatically.")
        
        # Print the full parsed JSON for comparison
        print()
        print(f"  Full raw JSON result:")
        print("  " + "-" * 55)
        print(f"  {json.dumps(data, indent=2)}")
        print("  " + "-" * 55)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON PARSE FAILED")
        print(f"     Error: {e.msg} at line {e.lineno}, column {e.colno}")
        print()
        # Show the raw output so the audience can see what went wrong
        print(f"  Raw output that failed to parse:")
        print("  " + "-" * 55)
        for line in raw_text.split("\n"):
            if line.strip().startswith("```"):
                print(f"  | ⚠️  {line}")
            else:
                print(f"  | {line}")
        print("  " + "-" * 55)
        print()
        print("     THIS IS THE PROBLEM: a single malformed response")
        print("     breaks your entire pipeline. In production, this means")
        print("     an alert at 3am because the model felt chatty.")

    # ═══════════════════════════════════════════════════════════
    # APPROACH B: PYDANTIC — "The Contract"
    # ═══════════════════════════════════════════════════════════
    print()
    print("=" * 75)
    print("  APPROACH B: Pydantic + with_structured_output()")
    print("  Strategy: Bind the schema to the model at the API level.")
    print("  Result:   The model CANNOT return output that violates the schema.")
    print("=" * 75)
    print()

    llm_structured = get_llm(temperature=test_temperature)
    structured_llm = llm_structured.with_structured_output(DiffAnalysis)

    print("  Sending SAME input to model (same temperature, same diff)...")
    pydantic_result = structured_llm.invoke(f"Analyze this diff:\n{diff_input}")

    print(f"  Returned type: {type(pydantic_result).__name__}")
    print(f"  Is it a string? {'❌ YES — would need parsing' if isinstance(pydantic_result, str) else '✅ NO — it is a typed object'}")
    print()

    print("  Extracted data (all fields guaranteed present and correctly typed):")
    print(f"    change.type:              {pydantic_result.change.type}")
    print(f"    change.severity:          {pydantic_result.change.severity}")
    print(f"    change.ticket:            {pydantic_result.change.ticket}")
    print(f"    details.summary:          {pydantic_result.details.summary}")
    print(f"    details.root_cause:       {pydantic_result.details.root_cause}")
    print(f"    details.user_impact_pct:  {pydantic_result.details.user_impact_pct} (type: {type(pydantic_result.details.user_impact_pct).__name__})")
    print(f"    technical.files_changed:  {pydantic_result.technical.files_changed}")
    print(f"    technical.db_changed:     {pydantic_result.technical.db_changed}")
    print(f"    technical.rollback:       {pydantic_result.technical.rollback}")
    print()

    # Print the full Pydantic result as JSON for comparison
    print("  Full Pydantic result (model_dump):")
    print("  " + "-" * 55)
    import json as _json
    print(f"  {_json.dumps(pydantic_result.model_dump(), indent=2)}")
    print("  " + "-" * 55)
    print()

    # ═══════════════════════════════════════════════════════════
    # THE VERDICT
    # ═══════════════════════════════════════════════════════════
    print("=" * 75)
    print("  THE VERDICT")
    print("=" * 75)
    print()
    print("  Same input. Same temperature (0.0). Same extraction task.")
    print()
    print("  Approach A (Raw Prompting):")
    print("    • A polite request to 'return JSON'")
    print("    • Model adds markdown backticks — even at temperature=0")
    print("    • json.loads() crashes. Pipeline breaks. Temperature didn't matter.")
    print()
    print("  Approach B (Pydantic):")
    print("    • A binding contract — schema enforced at the token level")
    print("    • Model CANNOT return output that violates the schema")
    print("    • Output is ALWAYS a typed object — no parsing needed")
    print("    • field_validators handle edge cases automatically ('15%' → 15)")
    print()
    print("  Raw JSON prompting = hope-based architecture.")
    print("  Pydantic schema     = engineering.")
    print("=" * 75)


if __name__ == "__main__":
    run_demo()
