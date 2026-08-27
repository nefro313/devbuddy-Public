"""
DevBuddy Integration Test — Week 0

Validates the full setup end-to-end:
1. .env is configured (OPENROUTER_API_KEY, DEVBUDDY_MODEL)
2. OpenRouter connectivity works
3. Structured output returns typed objects
4. Cost tracking works
5. Model swap works (optional)

Run: python tests/test_integration.py
"""
import os
import sys
import time

# Ensure src/ is importable (Python 3.12+ doesn't auto-add CWD)
# __file__ is python/tests/test_integration.py, so parent is python/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OPENROUTER_API_KEY, DEVBUDDY_MODEL, DEVBUDDY_MODEL_ALT

# ─── Test 1: Environment ──────────────────────────────────────
def test_env_configured():
    """Verify .env has the required variables."""
    assert OPENROUTER_API_KEY is not None, "❌ OPENROUTER_API_KEY not set in .env"
    assert "sk-or-" in OPENROUTER_API_KEY, "❌ OPENROUTER_API_KEY doesn't look like an OpenRouter key"
    assert DEVBUDDY_MODEL is not None, "❌ DEVBUDDY_MODEL not set in .env"

    print(f"  ✅ .env configured: model={DEVBUDDY_MODEL}, key={'*' * 8}{OPENROUTER_API_KEY[-4:]}")


# ─── Test 2: OpenRouter Connectivity ──────────────────────────
def test_openrouter_connectivity():
    """Verify we can call OpenRouter and get a response."""
    from src.llm import get_llm
    from langchain_core.messages import HumanMessage

    llm = get_llm(temperature=0)
    start = time.time()
    response = llm.invoke([HumanMessage(content="Say 'connected' and nothing else.")])
    elapsed = time.time() - start

    assert response is not None, "❌ No response from OpenRouter"
    assert "connected" in response.content.lower(), f"❌ Unexpected response: {response.content[:50]}"
    assert elapsed < 30, f"❌ Response took {elapsed:.0f}s (expected < 30s)"

    # Verify token usage in metadata (available on plain LLM calls)
    usage = response.usage_metadata or {}
    input_tokens = usage.get("input_tokens", 0) if hasattr(usage, "get") else 0
    output_tokens = usage.get("output_tokens", 0) if hasattr(usage, "get") else 0

    print(f"  ✅ OpenRouter connected: {elapsed:.1f}s, "
          f"tokens={input_tokens}+{output_tokens}")


# ─── Test 3: Structured Output ────────────────────────────────
def test_structured_output():
    """Verify with_structured_output returns a typed object."""
    from src.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage
    from pydantic import BaseModel, Field

    class SmokeTest(BaseModel):
        status: str = Field(description="Must be 'ok'")
        model_used: str = Field(description="The model that processed this request")

    llm = get_llm(temperature=0)
    structured = llm.with_structured_output(SmokeTest)

    response = structured.invoke([
        SystemMessage(content="Return valid JSON only."),
        HumanMessage(content="Set status='ok'. Include the model you're running on.")
    ])

    assert isinstance(response, SmokeTest), \
        f"❌ Expected SmokeTest, got {type(response).__name__}"
    assert response.status == "ok", f"❌ Expected status='ok', got '{response.status}'"
    assert response.model_used, "❌ model_used field is empty"

    print(f"  ✅ Structured output: {type(response).__name__}(status='{response.status}')")


# ─── Test 4: Cost Tracking ────────────────────────────────────
def test_cost_tracking():
    """Verify token usage is available from a plain LLM call."""
    from src.llm import get_llm
    from langchain_core.messages import HumanMessage

    llm = get_llm(temperature=0)
    response = llm.invoke([HumanMessage(content="One word: hello")])

    usage = response.usage_metadata or {}
    input_tokens = usage.get("input_tokens", 0) if hasattr(usage, "get") else 0
    output_tokens = usage.get("output_tokens", 0) if hasattr(usage, "get") else 0

    assert input_tokens > 0, "❌ input_tokens is 0"
    assert output_tokens > 0, "❌ output_tokens is 0"

    # Estimated cost (GPT-4o-mini pricing — check OpenRouter dashboard for billing)
    cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000

    print(f"  ✅ Cost tracked: {input_tokens}+{output_tokens} tokens, ~${cost:.6f} (estimated)")


# ─── Test 5: Model Swap (Optional) ────────────────────────────
def test_model_swap():
    """Verify a different model also works (runs if DEVBUDDY_MODEL_ALT is set)."""
    if not DEVBUDDY_MODEL_ALT:
        print("  ⏭️  Model swap skipped (set DEVBUDDY_MODEL_ALT in .env to test)")
        return

    from src.llm import get_llm
    from langchain_core.messages import HumanMessage

    llm = get_llm(model=DEVBUDDY_MODEL_ALT, temperature=0)
    start = time.time()
    response = llm.invoke([HumanMessage(content="Say 'ok'")])
    elapsed = time.time() - start

    assert response is not None, f"❌ No response from {DEVBUDDY_MODEL_ALT}"
    assert elapsed < 30, f"❌ {DEVBUDDY_MODEL_ALT} took {elapsed:.0f}s"

    print(f"  ✅ Model swap: {DEVBUDDY_MODEL_ALT} responded in {elapsed:.1f}s")


# ─── Run All ──────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  DevBuddy Integration Test — Week 0")
    print("=" * 60)
    print()

    tests = [
        ("Environment", test_env_configured),
        ("OpenRouter Connectivity", test_openrouter_connectivity),
        ("Structured Output", test_structured_output),
        ("Cost Tracking", test_cost_tracking),
        ("Model Swap", test_model_swap),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1

    print()
    print("=" * 60)
    if failed == 0:
        print(f"  ✅ ALL {passed} TESTS PASSED")
        print("  Your environment is fully configured and working.")
    else:
        print(f"  {passed} passed, {failed} failed")
        print("  Fix the failures above and re-run.")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
