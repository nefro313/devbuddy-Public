"""
DevBuddy — Tracing & Observability (Week 7)

One trace_id, three destinations.

    ┌──────────────────────────────────────────────────────────┐
    │  TracerProvider  (service.name = devbuddy)               │
    │                                                          │
    │   ├── BatchSpanProcessor → OTLP/HTTP → Uptrace :14318    │
    │   └── LangfuseSpanProcessor → Langfuse :3001             │
    └──────────────────────────────────────────────────────────┘

Both processors hang off the *same* provider, so a span is created once and
lands in both backends carrying the same trace_id. That shared id is the whole
architecture: it is what turns "an alert fired" into "here is the exact prompt
that caused it" without a single grep.

The division of labour:

* ``traced()``            — spans for the steps you wrote (retrieval, tools,
                            guardrails). Also feeds the Prometheus histogram,
                            so one ``with`` block instruments two layers.
* ``callback_handler()``  — hand to ``graph.invoke(config={"callbacks": [...]})``
                            and every LangChain model call inside becomes a
                            Langfuse *generation*, with prompt, completion,
                            tokens and cost, priced automatically.
* ``score()``             — a judgement about quality, attached to the trace.
                            A guardrail block is a score of 0, not a log line.

Everything degrades to a no-op. A missing Langfuse container, an unreachable
Uptrace, an uninstalled extra — none of them may stop DevBuddy from answering
a question. Observability that can take the system down with it has stopped
being a safety net and become a dependency.

Imports: src.config (Week 1), src.cost_tracker (Week 7).
Imported by: src.guardrails, src.agent.
"""

import re
import time
from contextlib import contextmanager
from typing import Any, Literal

from src import cost_tracker
from src.config import settings

# ─────────────────────────────────────────────────────────────
#  Optional dependencies
# ─────────────────────────────────────────────────────────────
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    OTEL_AVAILABLE = False

try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    LANGFUSE_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
#  Module state
# ─────────────────────────────────────────────────────────────
_provider: Any = None
_tracer: Any = None
_langfuse: Any = None
_status: dict[str, str] = {}


def init(force: bool = False) -> dict[str, str]:
    """Build the tracer provider and connect the backends. Idempotent.

    Returns a dict describing what actually came up, e.g.::

        {"otel": "uptrace @ http://localhost:14318", "langfuse": "http://localhost:3001"}

    Values starting with "off" or "error" mean that leg is not reporting. It
    is called for its side effects, but it returns the status because a
    silently-disabled tracer is the single most annoying thing to debug: you
    look at an empty Uptrace and cannot tell whether the exporter is broken or
    the code never ran.
    """
    global _provider, _tracer, _langfuse, _status

    if _status and not force:
        return _status

    _status = {}

    if not OTEL_AVAILABLE:
        _status["otel"] = "off — opentelemetry not installed"
        _status["langfuse"] = "off — needs opentelemetry"
        return _status

    if not settings.tracing_enabled:
        _status["otel"] = "off — DEVBUDDY tracing_enabled=false"
    # The provider is built even when the Uptrace leg is disabled, because
    # Langfuse needs something to attach its processor to.
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment": settings.otel_environment,
        }
    )
    _provider = TracerProvider(resource=resource)

    # ── Leg 1: Uptrace, over plain OTLP ──────────────────────
    # Nothing here names a vendor beyond the endpoint. Point
    # UPTRACE_DSN at Jaeger, Tempo or Datadog and the code is unchanged —
    # that is the entire argument for OpenTelemetry.
    if settings.tracing_enabled and settings.uptrace_endpoint:
        try:
            exporter = OTLPSpanExporter(
                endpoint=f"{settings.uptrace_endpoint}/v1/traces",
                # The DSN is the project credential. Uptrace reads it from
                # this header on every OTLP request.
                headers={"uptrace-dsn": settings.uptrace_dsn},
                timeout=5,
            )
            _provider.add_span_processor(BatchSpanProcessor(exporter))
            _status["otel"] = f"uptrace @ {settings.uptrace_endpoint}"
        except Exception as exc:  # pragma: no cover
            _status["otel"] = f"error — {exc}"

    otel_trace.set_tracer_provider(_provider)
    _tracer = _provider.get_tracer("devbuddy")

    # ── Leg 2: Langfuse, on the same provider ────────────────
    # Passing our provider is what makes the trace_id shared. Let the SDK
    # build its own and you get two unrelated traces of the same request,
    # which is worse than having one, because you will believe the ids match.
    if LANGFUSE_AVAILABLE and settings.langfuse_enabled and settings.langfuse_secret_key:
        try:
            _langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                environment=settings.otel_environment,
                tracer_provider=_provider,
            )
            _status["langfuse"] = settings.langfuse_host
        except Exception as exc:  # pragma: no cover
            _langfuse = None
            _status["langfuse"] = f"error — {exc}"
    elif not LANGFUSE_AVAILABLE:
        _status["langfuse"] = "off — langfuse not installed"
    else:
        _status["langfuse"] = "off — no LANGFUSE_SECRET_KEY"

    # Without this every Langfuse trace reports $0.00, because Langfuse has
    # never heard of "openai/gpt-4o-mini". Idempotent, and silent when the
    # models already exist.
    if _langfuse is not None:
        registered = ensure_model_prices()
        if registered:
            _status["langfuse"] += f" (registered {registered} model prices)"

    return _status


def status() -> dict[str, str]:
    """What init() brought up, without forcing it to run."""
    return dict(_status)


def get_tracer():
    if _tracer is None:
        init()
    return _tracer


def get_langfuse():
    if not _status:
        init()
    return _langfuse


# ─────────────────────────────────────────────────────────────
#  Spans
# ─────────────────────────────────────────────────────────────
def _attr(value: Any) -> Any:
    """Coerce a value into something OTel will accept as an attribute.

    OTel accepts str, bool, int, float and homogeneous sequences of those.
    Handing it a dict or a Pydantic model drops the attribute silently, which
    is how you end up with a span that has none of the fields you set.
    """
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return str(value)


@contextmanager
def traced(name: str, step: str | None = None, **attributes: Any):
    """Trace a step, and time it into the Prometheus histogram.

    One ``with`` block, two observability layers — the span goes to Uptrace and
    Langfuse, the duration goes to Prometheus. Keeping them together is what
    stops the two from drifting apart as steps are added.

    The three habits, enforced here so you cannot forget them:
      * the span is named after the step, not the function
      * interesting values go on as attributes
      * exceptions are recorded on the span before they propagate

    Yields the span, so the body can add attributes it only learns later::

        with traced("rag.retrieve", query=q) as span:
            chunks = retrieve(q)
            span.set_attribute("rag.chunk_count", len(chunks))
    """
    tracer = get_tracer()
    started = time.perf_counter()

    if tracer is None:
        # No OTel: still record latency, still yield something with the same
        # shape so callers never need to branch.
        try:
            yield _NoOpSpan()
        finally:
            cost_tracker.record_latency(step or name, time.perf_counter() - started)
        return

    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, _attr(value))
        try:
            yield span
        except Exception as exc:
            # Without this the span shows a duration and no reason. Uptrace
            # groups errors by exception type; it can only do that if the
            # exception was recorded on the span.
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        finally:
            cost_tracker.record_latency(step or name, time.perf_counter() - started)


class _NoOpSpan:
    """Stands in for a span when OTel is not installed."""

    def set_attribute(self, *_args, **_kwargs) -> None:
        return None

    def record_exception(self, *_args, **_kwargs) -> None:
        return None

    def set_status(self, *_args, **_kwargs) -> None:
        return None


# The two functions below differ in exactly one thing: whether this span is
# itself the generation, or whether a real generation already exists beneath
# it. Langfuse promotes any span carrying `gen_ai.*` to a priced generation,
# so setting them in the wrong place double-counts the cost of every call.
#
# The LangChain callback handler only runs where it is attached — inside
# `graph.invoke`. So the agent's own nodes get a child generation for free,
# and everything else (the guardrails, the MCP server across the network) does
# not and must declare itself.
def record_generation(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Bill a model call and mark this span as the generation. Returns USD.

    Use where no LangChain callback handler was attached. The attribute names
    are the OpenTelemetry GenAI semantic conventions, so any OTel backend —
    not just Langfuse — knows what they mean.
    """
    usd = cost_tracker.record_llm_call(model, prompt_tokens, completion_tokens)

    if OTEL_AVAILABLE:
        span = otel_trace.get_current_span()
        if span is not None:
            span.set_attribute("gen_ai.system", "openrouter")
            span.set_attribute("gen_ai.request.model", model)
            span.set_attribute("gen_ai.usage.input_tokens", prompt_tokens)
            span.set_attribute("gen_ai.usage.output_tokens", completion_tokens)
            span.set_attribute("devbuddy.cost_usd", usd)
    return usd


def record_nested_generation(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Bill a model call that already has its own generation underneath. Returns USD.

    Use inside the agent's graph nodes, where the LangChain callback handler
    has already produced a full Langfuse generation — prompt, completion,
    tokens and price — one level down. This only annotates the parent step and
    keeps the Prometheus counters whole; it must not claim to be a generation
    itself, or the same call is priced twice.
    """
    usd = cost_tracker.record_llm_call(model, prompt_tokens, completion_tokens)

    if OTEL_AVAILABLE:
        span = otel_trace.get_current_span()
        if span is not None:
            span.set_attribute("devbuddy.model", model)
            span.set_attribute("devbuddy.input_tokens", prompt_tokens)
            span.set_attribute("devbuddy.output_tokens", completion_tokens)
            span.set_attribute("devbuddy.cost_usd", usd)
    return usd


def ensure_model_prices() -> int:
    """Teach Langfuse what our models cost. Returns how many were registered.

    Langfuse prices a generation by matching the model name against its own
    table, which knows ``gpt-4o-mini`` but not OpenRouter's ``openai/gpt-4o-mini``.
    Unmatched means unpriced, and unpriced means every trace shows $0.00 —
    a cost dashboard that is confidently, quietly wrong.

    Registering them from ``cost_tracker.PRICES`` also means the two systems
    cannot disagree: Prometheus and Langfuse read the same table.
    """
    client = get_langfuse()
    if client is None:
        return 0

    try:
        import httpx

        auth = (settings.langfuse_public_key, settings.langfuse_secret_key)
        base = settings.langfuse_host.rstrip("/")
        with httpx.Client(timeout=10) as http:
            existing = http.get(f"{base}/api/public/models?limit=100", auth=auth)
            known = {m["modelName"] for m in existing.json().get("data", [])}

            created = 0
            for model, (price_in, price_out) in cost_tracker.PRICES.items():
                if model in known:
                    continue
                short = model.split("/")[-1]
                response = http.post(
                    f"{base}/api/public/models",
                    auth=auth,
                    json={
                        "modelName": model,
                        # Match the OpenRouter form and the bare form, so a
                        # generation logged either way is still priced.
                        "matchPattern": rf"(?i)^(.*/)?{re.escape(short)}$",
                        "unit": "TOKENS",
                        "inputPrice": price_in / 1_000_000,
                        "outputPrice": price_out / 1_000_000,
                    },
                )
                if response.status_code < 300:
                    created += 1
        return created
    except Exception:  # pragma: no cover - never fatal
        return 0


def current_trace_id() -> str | None:
    """The 32-char hex trace id, or None outside a trace.

    Log this in the response. It is the join key between an alert in Grafana,
    a waterfall in Uptrace and a prompt in Langfuse.
    """
    if not OTEL_AVAILABLE:
        return None
    span = otel_trace.get_current_span()
    context = span.get_span_context() if span else None
    if context is None or not context.trace_id:
        return None
    return format(context.trace_id, "032x")


# ─────────────────────────────────────────────────────────────
#  Langfuse: generations, scores, sessions
# ─────────────────────────────────────────────────────────────
def callback_handler():
    """The LangChain/LangGraph callback handler, or None.

    Pass it into the graph and every model call underneath becomes a Langfuse
    generation with its prompt, completion, token counts and cost:

        run_dynamic_agent(q)  ->  graph.invoke(state, config={"callbacks": [handler]})
    """
    if get_langfuse() is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception:  # pragma: no cover
        return None


def score(
    name: str,
    value: float | str,
    comment: str | None = None,
    data_type: Literal["NUMERIC", "CATEGORICAL", "BOOLEAN"] = "NUMERIC",
) -> None:
    """Attach a quality judgement to the current trace.

    This is the signal neither Prometheus nor Uptrace can produce. A span knows
    a call took 1.6 seconds and returned 200; only a score knows the answer it
    returned was wrong.

    Never raises. A scoring backend that is down must not fail the request it
    was trying to judge.
    """
    client = get_langfuse()
    if client is None:
        return
    try:
        client.score_current_trace(
            name=name, value=value, data_type=data_type, comment=comment
        )
    except Exception:  # pragma: no cover
        pass


def describe_trace(**attributes: Any):
    """Context manager adding trace-level metadata (user, session, tags).

    Langfuse v4 replaced v3's ``update_current_trace()`` with a context
    manager, because trace-level attributes have to be set before the child
    spans are created, not patched on afterwards.

    Accepts user_id, session_id, tags, metadata, version, trace_name.
    """
    client = get_langfuse()
    if client is None:
        return _null_context()
    try:
        from langfuse import propagate_attributes

        return propagate_attributes(**attributes)
    except Exception:  # pragma: no cover
        return _null_context()


@contextmanager
def _null_context():
    yield None


def flush() -> None:
    """Push buffered spans and scores. Call before a short-lived process exits.

    Both exporters batch. A script that ends without flushing loses whatever
    was still in the buffer, which looks exactly like an exporter that does
    not work.
    """
    if _langfuse is not None:
        try:
            _langfuse.flush()
        except Exception:  # pragma: no cover
            pass
    if _provider is not None:
        try:
            _provider.force_flush(timeout_millis=5000)
        except Exception:  # pragma: no cover
            pass


# ═══════════════════════════════════════════════════════════════
#  Week 7 checkpoint:  python src/tracing.py
# ═══════════════════════════════════════════════════════════════
def main() -> None:
    print("=" * 70)
    print("  DevBuddy — Week 7: Tracing & Observability")
    print("=" * 70)

    state = init()
    print("\n  Backends")
    for leg, detail in state.items():
        mark = "✗" if detail.startswith(("off", "error")) else "✓"
        print(f"    {mark} {leg:10} {detail}")

    if not OTEL_AVAILABLE:
        print("\n  Install the Week 7 extras:  uv pip install -e \".[obs]\"")
        return

    print("\n  Emitting a synthetic request — 7 spans, one trace")
    with traced("devbuddy.request", step="total", **{"devbuddy.entrypoint": "checkpoint"}):
        trace_id = current_trace_id()

        with traced("guardrail.input", **{"guardrail.rule": "prompt_injection"}):
            time.sleep(0.02)
        with traced("agent.extract_service") as span:
            time.sleep(0.15)
            span.set_attribute("devbuddy.service_name", "auth-service")
            record_generation(settings.devbuddy_model, 180, 24)
        with traced("rag.retrieve") as span:
            time.sleep(0.10)
            span.set_attribute("rag.chunk_count", 4)
        with traced("tool.get_build_status") as span:
            time.sleep(0.30)
            span.set_attribute("devbuddy.build_status", "healthy")
        with traced("agent.generate_report") as span:
            time.sleep(0.25)
            record_generation(settings.devbuddy_model, 1400, 320)
            span.set_attribute("devbuddy.ready", False)
        with traced("guardrail.output", **{"guardrail.rule": "grounding"}):
            time.sleep(0.02)

        score("grounded", 1.0, comment="checkpoint run, evidence present")

    print(f"    trace_id  {trace_id}")
    print(f"    cost      ${cost_tracker.ledger.usd:.6f} "
          f"({cost_tracker.ledger.calls} generations)")

    # A span that fails, so error grouping has something to group.
    print("\n  Emitting a failing span")
    try:
        with traced("tool.get_build_status", **{"devbuddy.tool": "get_build_status"}):
            raise TimeoutError("build API did not respond in 6s")
    except TimeoutError as exc:
        cost_tracker.record_tool_error("get_build_status", "timeout")
        print(f"    recorded: {exc}")

    print("\n  Flushing…")
    flush()

    print("\n" + "=" * 70)
    if trace_id:
        print(f"  Uptrace   http://localhost:14318  → search {trace_id}")
        print(f"  Langfuse  {settings.langfuse_host}  → same id, with prompts")
    print("  Spans are batched; give them a few seconds to appear.")
    print("=" * 70)


if __name__ == "__main__":
    main()
