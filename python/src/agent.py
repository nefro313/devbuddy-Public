"""
DevBuddy — Agent Orchestrator (Week 6)

Everything built so far, composed into one flow.

    agent.py
    ├── src.llm         Week 1   the client
    ├── src.schemas     Week 2   ServiceReadinessReport, call_structured
    └── MCP server      Week 5   ALL data access, over the network
        ├── search_docs            → retrieval  (Week 3)
        ├── get_build_status       → tools      (Week 4)
        ├── get_recent_deploys
        └── get_active_incidents

Note what is *not* imported: ``src.rag`` and ``src.tools``. The agent has one
data path — the MCP server — so swapping a data source, adding a tool, or
moving retrieval to another machine changes nothing here. That is the payoff
for the protocol work in Week 5.

Two orchestrators, the same nodes:

* ``run_fixed_chain()``   — extract → retrieve → check build → report. Always
  those four steps, in that order. Predictable, cheap, and unable to answer a
  question it was not designed for.
* ``run_dynamic_agent()`` — a router picks each next step at runtime. Adapts,
  costs more, and needs a guard because a model deciding its own next move can
  decide to keep going.

Prerequisites: Qdrant up, and the MCP server running (`python src/mcp_server.py`).
"""

import asyncio
import json
import time
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from mcp import Client
from pydantic import BaseModel, Field

from src.config import settings
from src.schemas import ServiceReadinessReport, SchemaRetryError, call_structured

# Runaway guards. docs/week-06.md asks you to edit these directly; both
# run_* functions also take overrides so you can demonstrate the guard
# without a source edit.
MAX_STEPS = settings.max_steps
MAX_COST = settings.max_cost

# Every data step, and the MCP tool behind it.
DATA_STEPS = {
    "retrieve_context": "search_docs",
    "check_build": "get_build_status",
    "check_deploys": "get_recent_deploys",
    "check_incidents": "get_active_incidents",
}


class MCPUnavailableError(RuntimeError):
    """The agent's only data path is down."""


# ═══════════════════════════════════════════════════════════════
#  State
# ═══════════════════════════════════════════════════════════════
def _keep_last(_old: Any, new: Any) -> Any:
    """Last write wins — the default, stated explicitly for readability."""
    return new


def _append(old: list, new: list) -> list:
    return (old or []) + (new or [])


def _add(old: int | float, new: int | float) -> int | float:
    return (old or 0) + (new or 0)


class AgentState(TypedDict, total=False):
    """What flows between nodes.

    Token counts and the trace use additive reducers so a node never has to
    read the running total before adding to it — which is what makes the
    step accounting survive a router that revisits nodes.
    """

    query: str
    service_name: Annotated[str, _keep_last]
    context: Annotated[list[str], _keep_last]
    build_status: Annotated[dict | None, _keep_last]
    deploys: Annotated[dict | None, _keep_last]
    incidents: Annotated[dict | None, _keep_last]
    completed: Annotated[list[str], _append]
    # The router's decision. It must be declared here: LangGraph propagates
    # only keys present in the state schema and silently drops the rest, so an
    # undeclared next_step makes every route fall through to generate_report
    # and the agent runs zero data steps while looking perfectly healthy.
    next_step: Annotated[str | None, _keep_last]
    report: Annotated[ServiceReadinessReport | None, _keep_last]
    steps: Annotated[int, _add]
    prompt_tokens: Annotated[int, _add]
    completion_tokens: Annotated[int, _add]
    trace: Annotated[list[dict], _append]
    halted: Annotated[str | None, _keep_last]
    max_steps: Annotated[int, _keep_last]
    max_cost: Annotated[float, _keep_last]


def _cost(state: AgentState) -> float:
    return settings.cost_of(
        state.get("prompt_tokens", 0), state.get("completion_tokens", 0)
    )


def _step(name: str, started: float, detail: str = "", **usage) -> dict:
    """One row of the trace: what ran, how long, what it cost."""
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return {
        "step": name,
        "seconds": round(time.time() - started, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost": settings.cost_of(prompt_tokens, completion_tokens),
        "detail": detail,
    }


# ═══════════════════════════════════════════════════════════════
#  MCP data path
# ═══════════════════════════════════════════════════════════════
async def _call_async(tool_name: str, arguments: dict) -> str:
    async with Client(settings.mcp_url) as client:
        result = await client.call_tool(tool_name, arguments)
        if result.is_error:
            raise MCPUnavailableError(
                f"MCP tool '{tool_name}' failed: "
                f"{''.join(getattr(b, 'text', '') for b in result.content or [])}"
            )
        return "".join(getattr(block, "text", "") for block in result.content or [])


def _call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call one MCP tool and return its parsed payload.

    A fresh connection per call. For a local server the handshake is a couple
    of milliseconds against LLM calls measured in seconds, and it keeps the
    LangGraph nodes plain synchronous functions. A long-lived session would be
    the right trade if the server moved off-box.
    """
    try:
        raw = asyncio.run(_call_async(tool_name, arguments))
    except MCPUnavailableError:
        raise
    except Exception as exc:
        raise MCPUnavailableError(
            f"Cannot reach the MCP server at {settings.mcp_url}: {exc}\n"
            "Start it with:  python src/mcp_server.py"
        ) from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


# ═══════════════════════════════════════════════════════════════
#  Nodes
# ═══════════════════════════════════════════════════════════════
class _ServiceName(BaseModel):
    service_name: str = Field(
        description="The service the question is about, in kebab-case, "
        "e.g. 'payment-api'. Empty string if the question names none."
    )


def extract_service(state: AgentState) -> AgentState:
    """Work out which service the question is about.

    A fixed chain that always checks a hardcoded service answers confidently
    about the wrong system, which is the most expensive kind of wrong.
    """
    started = time.time()
    result, stats = call_structured(
        _ServiceName,
        [
            SystemMessage(
                content="Extract the service name from the question. Known "
                "services: auth-service, payment-api, inventory-service."
            ),
            HumanMessage(content=state["query"]),
        ],
    )
    service = result.service_name.strip() or "auth-service"
    return {
        "service_name": service,
        "steps": 1,
        "prompt_tokens": stats.prompt_tokens,
        "completion_tokens": stats.completion_tokens,
        "completed": ["extract_service"],
        "trace": [
            _step(
                "extract_service",
                started,
                service,
                prompt_tokens=stats.prompt_tokens,
                completion_tokens=stats.completion_tokens,
            )
        ],
    }


def retrieve_context(state: AgentState) -> AgentState:
    started = time.time()
    payload = _call_mcp_tool(
        "search_docs",
        {"query": f"{state['service_name']} {state['query']}", "k": 4},
    )
    chunks = payload.get("chunks", [])
    return {
        "context": chunks,
        "steps": 1,
        "completed": ["retrieve_context"],
        "trace": [_step("retrieve_context", started, f"{len(chunks)} chunks")],
    }


def check_build(state: AgentState) -> AgentState:
    started = time.time()
    payload = _call_mcp_tool("get_build_status", {"service_name": state["service_name"]})
    return {
        "build_status": payload,
        "steps": 1,
        "completed": ["check_build"],
        "trace": [_step("check_build", started, str(payload.get("status")))],
    }


def check_deploys(state: AgentState) -> AgentState:
    started = time.time()
    payload = _call_mcp_tool(
        "get_recent_deploys", {"service_name": state["service_name"], "limit": 5}
    )
    count = len(payload.get("deploys", []))
    return {
        "deploys": payload,
        "steps": 1,
        "completed": ["check_deploys"],
        "trace": [_step("check_deploys", started, f"{count} deploys")],
    }


def check_incidents(state: AgentState) -> AgentState:
    started = time.time()
    payload = _call_mcp_tool("get_active_incidents", {"service_name": state["service_name"]})
    count = len(payload.get("incidents", []))
    return {
        "incidents": payload,
        "steps": 1,
        "completed": ["check_incidents"],
        "trace": [_step("check_incidents", started, f"{count} active")],
    }


_REPORT_PROMPT = """You are DevBuddy, producing a release-readiness report.

Use only the evidence provided. Rules the report must satisfy:
- ready=false requires at least one blocker; ready=true requires none.
- ready=true is impossible while an incident is unresolved.
- A build with status 'degraded' or 'down' must record failing_since.
- Cite each fact in `evidence`: source 'tool' for build/deploy/incident data,
  'rag' for retrieved documentation.
- If a data source was not consulted, do not invent its content. Say so in
  confidence instead: 'low' when key data is missing."""


def generate_report(state: AgentState) -> AgentState:
    """Turn the gathered evidence into a validated ServiceReadinessReport.

    Week 2's cross-field validators do real work here. The model will happily
    write ready=true next to an open Sev1; the schema rejects it and
    call_structured sends the complaint back for a correction.
    """
    started = time.time()
    evidence = {
        "service_name": state["service_name"],
        "question": state["query"],
        "steps_taken": state.get("completed", []),
        "documentation": state.get("context") or "(not retrieved)",
        "build_status": state.get("build_status") or "(not checked)",
        "recent_deploys": state.get("deploys") or "(not checked)",
        "active_incidents": state.get("incidents") or "(not checked)",
        "halted": state.get("halted"),
    }

    try:
        report, stats = call_structured(
            ServiceReadinessReport,
            [
                SystemMessage(content=_REPORT_PROMPT),
                HumanMessage(content=json.dumps(evidence, indent=2, default=str)),
            ],
        )
    except SchemaRetryError as exc:
        return {
            "report": None,
            "steps": 1,
            "prompt_tokens": exc.stats.prompt_tokens,
            "completion_tokens": exc.stats.completion_tokens,
            "halted": f"report failed validation after {exc.stats.attempts} attempts",
            "completed": ["generate_report"],
            "trace": [_step("generate_report", started, "VALIDATION FAILED")],
        }

    # A halted run must never certify a release.
    #
    # The prompt asks the model to lower its confidence when data is missing;
    # asked after a guard cut it off with only a healthy build in hand, it
    # returned ready=true / confidence=high anyway. Reasonable-sounding, and
    # exactly wrong: "I ran out of budget before checking for incidents" is not
    # a green light.
    #
    # This keys off `halted`, not off missing data. A dynamic router that
    # decided incidents were irrelevant to "is X healthy?" made a judgement;
    # a guard that stopped mid-investigation did not.
    if state.get("halted") and report.verdict.ready:
        payload = report.model_dump(mode="json")
        unchecked = [s for s in DATA_STEPS if s not in state.get("completed", [])]
        payload["verdict"]["ready"] = False
        payload["verdict"]["confidence"] = "low"
        payload["verdict"]["blockers"] = [
            f"{step.replace('_', ' ')} was not performed — {state['halted']}"
            for step in unchecked
        ] or [f"assessment incomplete — {state['halted']}"]
        report = ServiceReadinessReport.model_validate(payload)

    return {
        "report": report,
        "steps": 1,
        "prompt_tokens": stats.prompt_tokens,
        "completion_tokens": stats.completion_tokens,
        "completed": ["generate_report"],
        "trace": [
            _step(
                "generate_report",
                started,
                f"ready={report.verdict.ready}",
                prompt_tokens=stats.prompt_tokens,
                completion_tokens=stats.completion_tokens,
            )
        ],
    }


# ═══════════════════════════════════════════════════════════════
#  Router — the dynamic agent's decision point
# ═══════════════════════════════════════════════════════════════
class _NextStep(BaseModel):
    # Field order is generation order under structured output, so asking for
    # the sufficiency judgement first makes the model commit to it before it
    # picks a step — rather than choosing a step and rationalising afterwards.
    answered: bool = Field(
        description="True if the data gathered so far already answers the "
        "question and no further data step is needed"
    )
    next_step: Literal[
        "retrieve_context", "check_build", "check_deploys", "check_incidents", "generate_report"
    ] = Field(description="The single next step to run")
    reason: str = Field(description="One short sentence: why this step, for this question")


_ROUTER_PROMPT = """You plan one step at a time for a release-readiness agent.

Available steps:
- retrieve_context   read the team's documentation (specs, SLAs, runbooks)
- check_build        current build/health status
- check_deploys      recent deployment history
- check_incidents    unresolved incidents
- generate_report    finish and write the report

Choose generate_report as soon as the data already gathered answers the
question. Steps still being available is NOT a reason to run them — each one
costs a model call, and an unasked-for step is waste, not thoroughness.

Match the question, not the menu:

  "Is X healthy?"                        check_build            → generate_report
  "What shipped to X?"                   check_deploys          → generate_report
  "Any incidents on X?"                  check_incidents        → generate_report
  "What was deployed, and any incidents?" check_deploys, check_incidents
                                                                → generate_report
  "What does the spec say about X?"      retrieve_context       → generate_report
  "Full readiness assessment for X"      all four               → generate_report

Never repeat a completed step."""


def _gathered(state: AgentState) -> str:
    """Compact summary of what the agent already holds, for the router."""
    build = state.get("build_status")
    deploys = state.get("deploys")
    incidents = state.get("incidents")
    context = state.get("context")
    return "\n".join(
        [
            f"- build status: {build.get('status') if build else 'NOT CHECKED'}",
            f"- recent deploys: {len(deploys.get('deploys', [])) if deploys else 'NOT CHECKED'}",
            f"- active incidents: "
            f"{len(incidents.get('incidents', [])) if incidents else 'NOT CHECKED'}",
            f"- documentation: {f'{len(context)} passages' if context else 'NOT RETRIEVED'}",
        ]
    )


def _guard(state: AgentState) -> str | None:
    """Return a reason to stop, or None to continue."""
    max_steps = state.get("max_steps") or MAX_STEPS
    max_cost = state.get("max_cost") or MAX_COST
    if state.get("steps", 0) >= max_steps:
        return f"step limit reached ({max_steps})"
    if _cost(state) >= max_cost:
        return f"cost limit reached (${max_cost:.2f})"
    return None


def route(state: AgentState) -> AgentState:
    """Pick the next step. The guard outranks the model."""
    started = time.time()

    stop = _guard(state)
    if stop:
        # The model is not consulted. A budget is not a negotiation.
        return {
            "halted": stop,
            "trace": [_step("guard", started, stop)],
        }

    completed = state.get("completed", [])
    remaining = [s for s in DATA_STEPS if s not in completed]
    if not remaining:
        return {"trace": [_step("route", started, "generate_report (all data gathered)")]}

    result, stats = call_structured(
        _NextStep,
        [
            SystemMessage(content=_ROUTER_PROMPT),
            HumanMessage(
                content=(
                    f"Question: {state['query']}\n"
                    f"Service: {state['service_name']}\n"
                    f"Already done: {completed}\n\n"
                    # The router judges sufficiency, so it needs to see what was
                    # actually gathered — not just which steps ran. Given only
                    # step names it has no way to tell "answered" from
                    # "attempted", and defaults to running everything left.
                    f"Data gathered so far:\n{_gathered(state)}"
                )
            ),
        ],
    )

    # The model's own sufficiency judgement, enforced in code. Listing the
    # steps still available used to be part of this prompt and reliably
    # produced completion bias: having answered "what was deployed, and any
    # incidents?" the router would go on to check build and read the docs,
    # because they were on the menu. The menu is in the system prompt; the
    # remaining list is not passed.
    choice = "generate_report" if result.answered else result.next_step
    if choice in completed:  # belt and braces — the prompt says never repeat
        choice = "generate_report"

    return {
        "next_step": choice,
        "prompt_tokens": stats.prompt_tokens,
        "completion_tokens": stats.completion_tokens,
        "trace": [
            _step(
                "route",
                started,
                f"{choice} — {result.reason}",
                prompt_tokens=stats.prompt_tokens,
                completion_tokens=stats.completion_tokens,
            )
        ],
    }


def _route_edge(state: AgentState) -> str:
    """Translate the router's decision into a graph edge."""
    if state.get("halted"):
        return "generate_report"
    completed = state.get("completed", [])
    if all(step in completed for step in DATA_STEPS):
        return "generate_report"
    return state.get("next_step") or "generate_report"


# ═══════════════════════════════════════════════════════════════
#  Graphs
# ═══════════════════════════════════════════════════════════════
def build_fixed_chain():
    """extract → retrieve → check build → report. Four steps, every time."""
    graph = StateGraph(AgentState)
    graph.add_node("extract_service", extract_service)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("check_build", check_build)
    graph.add_node("generate_report", generate_report)

    graph.set_entry_point("extract_service")
    graph.add_edge("extract_service", "retrieve_context")
    graph.add_edge("retrieve_context", "check_build")
    graph.add_edge("check_build", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()


def build_dynamic_agent():
    """extract → (route → data step)* → report. The model picks the path."""
    graph = StateGraph(AgentState)
    graph.add_node("extract_service", extract_service)
    graph.add_node("route", route)
    for step_name, node in (
        ("retrieve_context", retrieve_context),
        ("check_build", check_build),
        ("check_deploys", check_deploys),
        ("check_incidents", check_incidents),
    ):
        graph.add_node(step_name, node)
    graph.add_node("generate_report", generate_report)

    graph.set_entry_point("extract_service")
    graph.add_edge("extract_service", "route")
    graph.add_conditional_edges(
        "route",
        _route_edge,
        {
            "retrieve_context": "retrieve_context",
            "check_build": "check_build",
            "check_deploys": "check_deploys",
            "check_incidents": "check_incidents",
            "generate_report": "generate_report",
        },
    )
    for step_name in DATA_STEPS:
        graph.add_edge(step_name, "route")
    graph.add_edge("generate_report", END)
    return graph.compile()


def _initial(query: str, max_steps: int | None, max_cost: float | None) -> AgentState:
    return {
        "query": query,
        "steps": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "completed": [],
        "trace": [],
        "max_steps": max_steps or MAX_STEPS,
        "max_cost": max_cost or MAX_COST,
    }


def run_fixed_chain(
    query: str, max_steps: int | None = None, max_cost: float | None = None
) -> dict:
    """Run the fixed chain. Returns the final state."""
    state = build_fixed_chain().invoke(_initial(query, max_steps, max_cost))
    state["cost"] = _cost(state)
    return state


def run_dynamic_agent(
    query: str, max_steps: int | None = None, max_cost: float | None = None
) -> dict:
    """Run the dynamic agent. Returns the final state."""
    # recursion_limit is LangGraph's own backstop against a cyclic graph; our
    # guard should always trip first, and this keeps a bug from becoming a bill.
    state = build_dynamic_agent().invoke(
        _initial(query, max_steps, max_cost), {"recursion_limit": 50}
    )
    state["cost"] = _cost(state)
    return state


# ═══════════════════════════════════════════════════════════════
#  Week 6 checkpoint:  python src/agent.py
# ═══════════════════════════════════════════════════════════════
def _rule(title: str) -> None:
    print(f"\n{'─' * 70}\n  {title}\n{'─' * 70}")


def _show_trace(state: dict) -> None:
    for row in state["trace"]:
        tokens = row["prompt_tokens"] + row["completion_tokens"]
        cost = f"${row['cost']:.6f}" if row["cost"] else "—"
        print(f"    {row['step']:18} {row['seconds']:5.2f}s  "
              f"{tokens:5} tok  {cost:>10}  {row['detail'][:44]}")
    print(f"    {'TOTAL':18} {'':5}   {state['steps']:5} steps "
          f"{'':5} ${state['cost']:.6f}")


def _show_report(state: dict) -> None:
    report = state.get("report")
    if report is None:
        print(f"    no report — {state.get('halted')}")
        return
    verdict = report.verdict
    print(f"    {report.service.name} {report.service.version} "
          f"({report.service.owner_team})")
    print(f"    build={report.build.status}  ready={verdict.ready}  "
          f"confidence={verdict.confidence}")
    for blocker in verdict.blockers:
        print(f"      blocker: {blocker[:80]}")
    print(f"    evidence items: {len(report.evidence)}")


def main() -> None:
    print("=" * 70)
    print("  DevBuddy — Week 6: Agentic Workflows")
    print(f"  model {settings.devbuddy_model}   mcp {settings.mcp_url}")
    print(f"  guards MAX_STEPS={MAX_STEPS} MAX_COST=${MAX_COST:.2f}")
    print("=" * 70)

    try:
        _call_mcp_tool("search_docs", {"query": "ping", "k": 1})
    except MCPUnavailableError as exc:
        print(f"\n❌ {exc}")
        return

    budget = 0.0

    # ── 1. Fixed chain ──────────────────────────────────────────
    _rule("1. Fixed chain — four steps, same path every time")
    question = "Is payment-api ready for release?"
    print(f"  Q: {question}")
    fixed = run_fixed_chain(question)
    budget += fixed["cost"]
    _show_trace(fixed)
    _show_report(fixed)
    print("\n  Note the data steps bill 0 tokens but take seconds. The MCP")
    print("  server runs its own LLM call to synthesise each answer, and that")
    print("  spend is invisible from here — this trace under-reports the true")
    print("  cost of a query. Propagating tool-side cost is Week 7's problem.")

    # ── 2. Dynamic routing ──────────────────────────────────────
    _rule("2. Dynamic agent — steps proportional to the question")
    for question in (
        "Is auth-service healthy?",
        "What was deployed to payment-api, and are there incidents?",
        "Give me a full readiness assessment for payment-api.",
    ):
        run = run_dynamic_agent(question)
        budget += run["cost"]
        data_steps = [s for s in run["completed"] if s in DATA_STEPS]
        print(f"\n  Q: {question}")
        print(f"     data steps ({len(data_steps)}): {', '.join(data_steps)}")
        print(f"     {run['steps']} steps total, ${run['cost']:.6f}")
        report = run.get("report")
        if report:
            print(f"     ready={report.verdict.ready} "
                  f"confidence={report.verdict.confidence} "
                  f"blockers={len(report.verdict.blockers)}")
    print("\n  ↑ the router does not cascade: 'healthy?' does not also pull")
    print("    deploys and incidents. Cost tracks question complexity.")

    # ── 3. The guard ────────────────────────────────────────────
    _rule("3. Guard — MAX_STEPS=2 on a question that needs more")
    guarded = run_dynamic_agent(
        "Give me a full readiness assessment for payment-api.", max_steps=2
    )
    budget += guarded["cost"]
    print(f"  steps taken   {guarded['steps']}  (limit 2)")
    print(f"  halted        {guarded.get('halted')}")
    print(f"  completed     {guarded['completed']}")
    _show_report(guarded)
    print("  ↑ it still reports — but a halted run cannot certify a release,")
    print("    so ready is forced false with the unchecked steps named.")

    # ── 4. Fixed vs dynamic ─────────────────────────────────────
    _rule("4. Fixed vs dynamic on the same question")
    question = "Is auth-service healthy?"
    fixed_run = run_fixed_chain(question)
    dynamic_run = run_dynamic_agent(question)
    budget += fixed_run["cost"] + dynamic_run["cost"]
    print(f"  Q: {question}\n")
    print(f"  fixed    {fixed_run['steps']} steps  ${fixed_run['cost']:.6f}  "
          f"{[s for s in fixed_run['completed'] if s in DATA_STEPS]}")
    print(f"  dynamic  {dynamic_run['steps']} steps  ${dynamic_run['cost']:.6f}  "
          f"{[s for s in dynamic_run['completed'] if s in DATA_STEPS]}")
    print("\n  The fixed chain retrieves documentation whether or not the")
    print("  question needs it, and cannot check incidents even when asked.")
    print("  The dynamic agent pays a router call per step to avoid both.")

    print("\n" + "=" * 70)
    print(f"  Week 6 complete.  Total cost this run: ${budget:.6f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
