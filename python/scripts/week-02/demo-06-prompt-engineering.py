"""
Demo 6: Prompt Engineering + Promptfoo Evaluation

What it shows:
  Same task, same schema, three prompt variants:
  - zero-shot
  - few-shot
  - chain-of-thought

The goal is to compare their behavior, especially schema adherence and field quality.

Run: python scripts/week-02/demo-06-prompt-engineering.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.llm_functions import analyze_pr_with_prompt
from src.config import DEVBUDDY_MODEL

PROMPT_DIR = Path(__file__).resolve().parents[3] / "shared" / "prompts"

PR_TITLE = "Fix login redirect loop in auth-service"
PR_DIFF = (
    "Updated session token validation in auth.py. Expired tokens now return 401 instead of looping.\n"
    "Files: src/auth.py, tests/test_auth.py"
)


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8").strip()


def print_result(label: str, result) -> None:
    print(f"\n[{label}]")
    print(f"  project: {result.project}")
    print(f"  severity: {result.severity}")
    print(f"  summary: {result.summary}")
    print(f"  affected_files: {result.affected_files}")


def main() -> None:
    prompts = {
        "zero-shot": load_prompt("zero-shot"),
        "few-shot": load_prompt("few-shot"),
        "chain-of-thought": load_prompt("chain-of-thought"),
    }

    print("=" * 80)
    print("  Demo 6: Prompt Engineering + Promptfoo Evaluation")
    print("=" * 80)
    print(f"  Model: {DEVBUDDY_MODEL}")
    print("  Task: same PR, same schema, different prompt strategy")
    print()

    for name, template in prompts.items():
        try:
            result = analyze_pr_with_prompt(
                title=PR_TITLE,
                diff=PR_DIFF,
                prompt_template=template,
                temperature=0.0,
                max_tokens=512,
            )
            print_result(name, result)
        except Exception as exc:
            print(f"\n[{name}] ERROR: {exc}")

    print("\n" + "-" * 80)
    print("  Why this matters:")
    print("  - zero-shot is the shortest, but often least robust")
    print("  - few-shot adds examples and improves format adherence")
    print("  - chain-of-thought may improve reasoning but can be verbose")
    print("  Promptfoo helps compare these systematically across models and prompts.")
    print("-" * 80)


if __name__ == "__main__":
    main()
