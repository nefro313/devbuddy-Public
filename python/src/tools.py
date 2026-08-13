"""
DevBuddy — Tool Use (Week 4)

    MODEL (decision layer)          YOUR CODE (execution layer)
         │                                 │
         │ "I need build status for        │
         │  payment-api"                   │
         │────────────────────────────────>│  get_build_status("payment-api")
         │                                 │  → {"status": "degraded"}
         │         result injected         │
         │<────────────────────────────────│
         │ "payment-api is degraded."      │

The model never runs your code. It asks. You execute. Everything that can go
wrong — timeouts, retries, fallbacks, audit logging, rate limits, whether a
human has to approve first — lives on your side of that line, because the
model cannot be trusted to enforce any of it and cannot be blamed when it
doesn't.

Concretely: ``execute_tool_safely()`` decides whether to retry. The model is
merely *told* what happened, in a structured error it can reason about. If you
put "retry up to twice on failure" in a prompt instead, you have a suggestion,
not a retry policy.

The data here is mock, matching shared/data/deploy-log.md and incident-log.md.
Week 5 swaps the same tool signatures onto the real RAG index — the interface
is the contract, the data source is an implementation detail.

Imports: src.llm (Week 1). Deliberately does NOT import src.rag — a tool needs
data, not a particular data source.
"""

import json
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from src.config import settings
from src.llm import get_llm, usage_of

# ═══════════════════════════════════════════════════════════════
#  Fault injection — for the failure-handling exercises
# ═══════════════════════════════════════════════════════════════
# Chance that a monitoring call fails, 0.0-1.0. Week 4's self-learning asks for
# a 30% error rate; set FAULT_INJECTION_RATE = 0.3 to get it.
FAULT_INJECTION_RATE: float = 0.0

# Seconds of artificial latency per monitoring call.
LATENCY_SECONDS: float = 0.0

# Deterministic failures, queued per service. Random faults are honest but
# useless in a demo you want to be able to re-run and reason about.
_queued_faults: dict[str, int] = defaultdict(int)


def fail_next(service_name: str, times: int = 1) -> None:
    """Make the next ``times`` monitoring calls for a service fail."""
    _queued_faults[service_name] += times


def reset_faults() -> None:
    """Clear queued faults and turn off random failure."""
    global FAULT_INJECTION_RATE
    _queued_faults.clear()
    FAULT_INJECTION_RATE = 0.0


def _simulate_monitoring_call(service_name: str) -> None:
    """Stand-in for the network. Raises the way a real monitoring API would."""
    if LATENCY_SECONDS:
        time.sleep(LATENCY_SECONDS)
    if _queued_faults[service_name] > 0:
        _queued_faults[service_name] -= 1
        raise ConnectionError(
            f"Could not reach monitoring API for '{service_name}' (connection reset)"
        )
    if FAULT_INJECTION_RATE and random.random() < FAULT_INJECTION_RATE:
        raise ConnectionError(
            f"Could not reach monitoring API for '{service_name}' (timeout after 5s)"
        )


# ═══════════════════════════════════════════════════════════════
#  Mock data sources
# ═══════════════════════════════════════════════════════════════
_BUILD_STATUS = {
    "auth-service": {
        "status": "healthy",
        "version": "2.1.0",
        "owner_team": "platform-identity",
        "last_deploy": "2026-06-28T08:15:00Z",
        "failing_since": None,
    },
    "payment-api": {
        "status": "degraded",
        "version": "1.8.3",
        "owner_team": "payments",
        "last_deploy": "2026-06-28T06:45:00Z",
        "failing_since": "2026-06-28T07:30:00Z",
    },
    "inventory-service": {
        "status": "unknown",
        "version": "0.9.1-beta",
        "owner_team": "catalog",
        "last_deploy": "2026-06-20T11:00:00Z",
        "failing_since": None,
    },
}

# Note: upstream's fixtures disagree with each other — deploy-log.md gives SHA
# pqr901stu234 to a failed auth-service deploy on 2026-06-25, while
# service-readiness-degraded.json gives the same SHA to a failed payment-api
# deploy on 2026-06-27. Both are kept here as they appear in their source file.
_RECENT_DEPLOYS = {
    "auth-service": [
        {"sha": "abc123def456", "author": "tabish", "timestamp": "2026-06-28T08:15:00Z",
         "status": "success", "version": "2.1.0"},
        {"sha": "789ghi012jkl", "author": "alex", "timestamp": "2026-06-27T14:30:00Z",
         "status": "success", "version": "2.0.2"},
        {"sha": "pqr901stu234", "author": "jordan", "timestamp": "2026-06-25T09:10:00Z",
         "status": "failed", "version": "2.0.1"},
    ],
    "payment-api": [
        {"sha": "def789ghi012", "author": "maria", "timestamp": "2026-06-28T06:45:00Z",
         "status": "success", "version": "1.8.3"},
        {"sha": "jkl345mno678", "author": "maria", "timestamp": "2026-06-27T22:00:00Z",
         "status": "rolling_back", "version": "1.8.2"},
        {"sha": "pqr901stu234", "author": "jordan", "timestamp": "2026-06-27T20:15:00Z",
         "status": "failed", "version": "1.8.1"},
    ],
    "inventory-service": [],
}

# Active means unresolved. INC-799 (auth-service) is resolved and so is absent.
_ACTIVE_INCIDENTS = {
    "payment-api": [
        {"id": "INC-842", "severity": "Sev1", "status": "investigating",
         "error_code": "408", "opened": "2026-06-28T07:30:00Z",
         "summary": "payment-api latency > 5s for 15% of requests"},
    ],
    "inventory-service": [
        {"id": "INC-901", "severity": "Sev3", "status": "investigating",
         "error_code": "500", "opened": "2026-06-22T13:05:00Z",
         "summary": "Inventory counts diverging between primary and replica",
         "tracking": ["PROJ-891", "PROJ-892"]},
    ],
    "auth-service": [],
}


# ═══════════════════════════════════════════════════════════════
#  The tools
# ═══════════════════════════════════════════════════════════════
# Docstrings are not documentation here — they are the routing prompt. The
# model picks between these three using nothing but the name, the description
# and the parameter names. Vague docstrings are the usual cause of a model
# calling the wrong tool.
@tool
def get_build_status(service_name: str) -> str:
    """Return the current build and health status for one service.

    Use for questions about whether a service is healthy, broken, degraded, or
    passing its build — and when it last deployed. Does NOT return deployment
    history or incidents.
    """
    _simulate_monitoring_call(service_name)
    record = _BUILD_STATUS.get(service_name)
    if record is None:
        return json.dumps({
            "service": service_name,
            "status": "unknown",
            "note": f"No monitoring data for '{service_name}'. Known services: "
                    f"{', '.join(sorted(_BUILD_STATUS))}",
        })
    return json.dumps({"service": service_name, **record})


@tool
def get_recent_deploys(service_name: str, limit: int = 5) -> str:
    """Return the most recent deployments for one service, newest first.

    Use for questions about what shipped, who deployed it, when, whether a
    deploy failed or was rolled back. Does NOT return current health.
    """
    _simulate_monitoring_call(service_name)
    deploys = _RECENT_DEPLOYS.get(service_name)
    if deploys is None:
        return json.dumps({
            "service": service_name,
            "deploys": [],
            "note": f"No deployment history for '{service_name}'.",
        })
    return json.dumps({
        "service": service_name,
        "count": len(deploys[:limit]),
        "deploys": deploys[:limit],
    })


@tool
def get_active_incidents(service_name: str) -> str:
    """Return unresolved incidents for one service.

    Use for questions about outages, incidents, on-call, or whether anything is
    currently broken in production. Resolved incidents are not returned.
    """
    _simulate_monitoring_call(service_name)
    incidents = _ACTIVE_INCIDENTS.get(service_name, [])
    return json.dumps({
        "service": service_name,
        "active_count": len(incidents),
        "incidents": incidents,
    })


ALL_TOOLS = [get_build_status, get_recent_deploys, get_active_incidents]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}


# ═══════════════════════════════════════════════════════════════
#  Execution layer
# ═══════════════════════════════════════════════════════════════
def _execute(
    tool_call: dict,
    tools_map: dict | None = None,
    max_attempts: int = 2,
) -> tuple[str, bool]:
    """Run one tool call. Returns (output, succeeded). Never raises.

    Returning the success flag alongside the output matters more than it
    looks. The obvious alternative — having the caller check whether the
    output string contains ``"status": "failed"`` — is wrong here: a perfectly
    successful ``get_recent_deploys`` embeds exactly that substring in any
    deploy record with a failed status, so every healthy history lookup would
    be logged as a tool failure. Success is a property of the execution, not
    something to re-derive by reading the payload.
    """
    tools_map = tools_map if tools_map is not None else TOOLS_BY_NAME
    name = tool_call.get("name", "")
    args = tool_call.get("args", {}) or {}

    target = tools_map.get(name)
    if target is None:
        return json.dumps({
            "status": "failed",
            "tool": name,
            "error": f"No such tool: '{name}'",
            "hint": f"Available tools: {', '.join(sorted(tools_map))}",
        }), False

    last_error = ""
    for _ in range(max_attempts):
        try:
            return target.invoke(args), True
        except Exception as exc:  # a tool may raise anything; none of it should escape
            last_error = f"{type(exc).__name__}: {exc}"

    return json.dumps({
        "status": "failed",
        "tool": name,
        "args": args,
        "error": last_error,
        "attempts": max_attempts,
        "hint": "The tool is temporarily unavailable. Report this gap to the "
                "user rather than guessing the value.",
    }), False


def execute_tool_safely(
    tool_call: dict,
    tools_map: dict | None = None,
    max_attempts: int = 2,
) -> str:
    """Run one tool call and return what the model should see. Never raises.

    A tool that throws takes the whole agent down with it, so failure is
    converted into a structured result the model can read and reason about:
    it can try another tool, ask the user, or report the gap honestly.

    Note where the retry lives — here, in code, with a hard attempt cap. The
    model is informed of the outcome; it does not get a vote on whether to
    hammer a failing service again.
    """
    output, _ = _execute(tool_call, tools_map, max_attempts)
    return output


@dataclass
class ToolLoopResult:
    """What one question cost and which tools it touched."""

    answer: str
    calls: list[dict] = field(default_factory=list)
    iterations: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    stopped_early: bool = False

    @property
    def cost(self) -> float:
        return settings.cost_of(self.prompt_tokens, self.completion_tokens)

    @property
    def tool_names(self) -> list[str]:
        return [call["name"] for call in self.calls]

    def line(self) -> str:
        return (
            f"{self.iterations} round(s), {len(self.calls)} tool call(s), "
            f"{self.prompt_tokens + self.completion_tokens} tokens, "
            f"${self.cost:.6f}"
        )


_SYSTEM_PROMPT = (
    "You are DevBuddy, a release assistant. Use the provided tools to answer "
    "questions about services.\n"
    "Call only the tools the question actually needs — do not check incidents "
    "when asked only about build health.\n"
    "If a tool returns status 'failed', say plainly which data you could not "
    "reach. Never guess a build status, deploy or incident."
)


def run_tool_loop(
    question: str,
    tools: list | None = None,
    max_iterations: int = 5,
    temperature: float = 0.0,
) -> ToolLoopResult:
    """The full decide → execute → return → answer loop.

    The model may ask for several rounds of tools; ``max_iterations`` is the
    stop. Without it a model that keeps requesting tools bills you forever —
    the same class of guard Week 6 applies to agent steps.
    """
    tool_list = tools if tools is not None else ALL_TOOLS
    tools_map = {t.name: t for t in tool_list}
    llm = get_llm(temperature=temperature).bind_tools(tool_list)

    conversation: list[BaseMessage] = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=question),
    ]
    result = ToolLoopResult(answer="")

    for _ in range(max_iterations):
        response: AIMessage = llm.invoke(conversation)
        prompt_tokens, completion_tokens = usage_of(response)
        result.prompt_tokens += prompt_tokens
        result.completion_tokens += completion_tokens
        result.iterations += 1

        if not response.tool_calls:
            result.answer = str(response.content).strip()
            return result

        # The assistant turn carrying tool_calls must be appended before the
        # results, and every tool_call_id must get exactly one ToolMessage back.
        # Skip either and the next request is rejected by the API.
        conversation.append(response)
        for call in response.tool_calls:
            output, ok = _execute(call, tools_map)
            result.calls.append({"name": call["name"], "args": call["args"], "ok": ok})
            conversation.append(ToolMessage(content=output, tool_call_id=call["id"]))

    result.stopped_early = True
    result.answer = (
        f"Stopped after {max_iterations} tool rounds without a final answer."
    )
    return result


# ═══════════════════════════════════════════════════════════════
#  Week 4 checkpoint:  python src/tools.py
# ═══════════════════════════════════════════════════════════════
def _rule(title: str) -> None:
    print(f"\n{'─' * 68}\n  {title}\n{'─' * 68}")


def main() -> None:
    print("=" * 68)
    print("  DevBuddy — Week 4: Tool Use")
    print(f"  model: {settings.devbuddy_model}   tools: {', '.join(TOOLS_BY_NAME)}")
    print("=" * 68)
    reset_faults()
    budget = 0.0

    # ── 1. The model decides. It does not execute. ──────────────
    _rule("1. The model returns a tool CALL, not a result")
    llm = get_llm(temperature=0.0).bind_tools(ALL_TOOLS)
    response = llm.invoke([HumanMessage(content="Is the payment-api healthy?")])
    prompt_tokens, completion_tokens = usage_of(response)
    budget += settings.cost_of(prompt_tokens, completion_tokens)
    print(f"  question        Is the payment-api healthy?")
    print(f"  content         {response.content!r}  ← empty: it has no data yet")
    for call in response.tool_calls:
        print(f"  tool_calls      {call['name']}({call['args']})")
    print("  Nothing ran. The model asked; our code has not answered yet.")

    # ── 2. Close the loop ───────────────────────────────────────
    _rule("2. decide → execute → return → answer")
    call = response.tool_calls[0]
    observation = execute_tool_safely(call)
    print(f"  we execute      {call['name']}({call['args']})")
    print(f"  tool returns    {observation}")
    final = llm.invoke([
        HumanMessage(content="Is the payment-api healthy?"),
        response,
        ToolMessage(content=observation, tool_call_id=call["id"]),
    ])
    prompt_tokens, completion_tokens = usage_of(final)
    budget += settings.cost_of(prompt_tokens, completion_tokens)
    print(f"  model answers   {str(final.content).strip()}")

    # ── 3. Routing ──────────────────────────────────────────────
    _rule("3. Routing — the docstring is the router")
    questions = [
        "Is auth-service healthy?",
        "What was deployed to payment-api recently?",
        "Is anything broken in production for inventory-service?",
        "Give me a full readiness picture for payment-api.",
        "What is the capital of France?",
    ]
    for question in questions:
        outcome = run_tool_loop(question)
        budget += outcome.cost
        chosen = ", ".join(outcome.tool_names) or "(none — answered directly)"
        print(f"\n  Q: {question}")
        print(f"     tools: {chosen}")
        print(f"     A: {outcome.answer[:150]}")

    # ── 4. Failure in the application layer ─────────────────────
    _rule("4. Tool failure is caught in your code, not the prompt")

    print("  a) transient — fails once, retry succeeds:")
    fail_next("payment-api", times=1)
    recovered = execute_tool_safely(
        {"name": "get_build_status", "args": {"service_name": "payment-api"}},
        max_attempts=2,
    )
    print(f"     {recovered}")

    print("\n  b) persistent — both attempts fail, structured error returned:")
    fail_next("payment-api", times=5)
    exhausted = execute_tool_safely(
        {"name": "get_build_status", "args": {"service_name": "payment-api"}},
        max_attempts=2,
    )
    print(f"     {exhausted}")

    print("\n  c) unknown tool name — clear error, not a KeyError crash:")
    print(f"     {execute_tool_safely({'name': 'get_buildstatus', 'args': {}})}")

    print("\n  d) end to end: what does the model do with a failed tool?")
    reset_faults()
    fail_next("payment-api", times=9)
    degraded_run = run_tool_loop("Is payment-api healthy?")
    budget += degraded_run.cost
    print(f"     tool calls: {[(c['name'], 'ok' if c['ok'] else 'FAILED') for c in degraded_run.calls]}")
    print(f"     A: {degraded_run.answer[:220]}")
    reset_faults()

    # ── 5. Cost ─────────────────────────────────────────────────
    _rule("5. What the tool loop costs")
    priced = run_tool_loop("Is payment-api ready to release? Check everything.")
    budget += priced.cost
    print(f"  question   Is payment-api ready to release? Check everything.")
    for call in priced.calls:
        # get_recent_deploys returns a record with "status": "failed" inside it.
        # This must still read ok=True — see the note in _execute().
        print(f"  tool       {call['name']:22} ok={call['ok']}")
    print(f"  {priced.line()}")
    print(f"  A: {priced.answer[:300]}")

    print("\n" + "=" * 68)
    print(f"  Week 4 complete.  Total cost this run: ${budget:.6f}")
    print("=" * 68)


if __name__ == "__main__":
    main()
