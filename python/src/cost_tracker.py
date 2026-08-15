"""
DevBuddy — Cost Tracking & Metrics (Week 7)

Six numbers, exposed on a page Prometheus reads every 15 seconds.

    devbuddy_requests_total              Counter    status, entrypoint
    devbuddy_request_latency_seconds     Histogram  step
    devbuddy_llm_tokens_total            Counter    model, direction
    devbuddy_llm_cost_usd_total          Counter    model
    devbuddy_tool_errors_total           Counter    tool, kind
    devbuddy_guardrail_blocks_total      Counter    rule

Nothing here pushes anywhere. The process exposes ``:8001/metrics`` as plain
text and Prometheus pulls it. That inversion is the point: a DevBuddy that has
crashed stops answering the scrape, so ``up == 0`` fires an alert. A push model
would simply go quiet, and quiet is indistinguishable from idle.

**Label discipline.** Every function below takes a fixed, bounded set of label
values, and that is deliberate — it is not possible to reach through this API
and label a metric with a user id, a query string or a trace id. Prometheus
allocates one time series per distinct label combination, so a `user_id` label
on a counter is how you turn a 6-series database into a 60,000-series one and
lose the whole instance. High-cardinality facts belong on a *span*
(src/tracing.py), which is stored per-request and indexed for exactly that.

Cost lives here rather than in config.py because by Week 7 there are two
prices per model and more than one model in play. ``settings.cost_of()`` still
works and is still correct for the configured model; ``cost_of()`` here knows
the difference between gpt-4o-mini and claude-sonnet-4.

Imports: src.config (Week 1). Imported by: src.tracing, src.guardrails, src.agent.
"""

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from src.config import settings

# ─────────────────────────────────────────────────────────────
#  Optional dependency
# ─────────────────────────────────────────────────────────────
# Weeks 1-6 must keep running for anyone who installed only the core deps, so
# a missing prometheus_client degrades to no-op metrics instead of an
# ImportError. Install with:  uv pip install -e ".[obs]"
try:
    from prometheus_client import REGISTRY, Counter, Histogram, start_http_server

    METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    METRICS_AVAILABLE = False

    class _NoOpMetric:
        """Accepts every call a Counter or Histogram would, and does nothing."""

        def labels(self, *_args, **_kwargs):
            return self

        def inc(self, *_args, **_kwargs):
            return None

        def observe(self, *_args, **_kwargs):
            return None

    def Counter(*_args, **_kwargs):  # type: ignore[misc]
        return _NoOpMetric()

    def Histogram(*_args, **_kwargs):  # type: ignore[misc]
        return _NoOpMetric()


# ─────────────────────────────────────────────────────────────
#  Pricing
# ─────────────────────────────────────────────────────────────
# USD per 1M tokens, as (input, output). These are OpenRouter list prices and
# they move — treat this table as a default, not as a source of truth, and
# check https://openrouter.ai/models before you quote a number to anyone.
#
# The output price is the one that surprises people: it is typically 4x the
# input price, which is why "make the prompt shorter" is usually the wrong
# optimisation and "stop the agent re-sending its history" is the right one.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "anthropic/claude-sonnet-4": (3.00, 15.00),
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "meta-llama/llama-3.3-70b-instruct": (0.12, 0.30),
}

# Models we have already warned about, so the warning appears once per process
# rather than once per call.
_warned_models: set[str] = set()


def price_of(model: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens for a model.

    Falls back to the configured price and says so, loudly and once. A silent
    fallback is how a cost dashboard ends up confidently reporting gpt-4o
    traffic at gpt-4o-mini prices — off by 16x, and green the whole time.
    """
    if model in PRICES:
        return PRICES[model]

    if model not in _warned_models:
        _warned_models.add(model)
        print(
            f"  [cost_tracker] no price for '{model}' — falling back to "
            f"${settings.price_input_per_m}/${settings.price_output_per_m} per 1M. "
            f"Add it to PRICES in src/cost_tracker.py."
        )
    return settings.price_input_per_m, settings.price_output_per_m


def cost_of(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """USD for one call against a specific model."""
    price_in, price_out = price_of(model)
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000


# ─────────────────────────────────────────────────────────────
#  The six metrics
# ─────────────────────────────────────────────────────────────
# Registered once. Re-importing this module in a live interpreter would
# otherwise raise "Duplicated timeseries in CollectorRegistry".
def _already_registered(name: str) -> bool:
    if not METRICS_AVAILABLE:
        return False
    return name in getattr(REGISTRY, "_names_to_collectors", {})


if not _already_registered("devbuddy_requests_total"):
    REQUESTS = Counter(
        "devbuddy_requests_total",
        "DevBuddy requests, by outcome and entry point",
        ["status", "entrypoint"],
    )

    LATENCY = Histogram(
        "devbuddy_request_latency_seconds",
        "Wall-clock seconds per step; step='total' is the whole request",
        ["step"],
        # The default buckets stop at 10s, which puts every interesting agent
        # request in +Inf and makes p95 meaningless. An LLM call is seconds and
        # a full agent run is tens of seconds, so the buckets go out to 60.
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 12.0, 20.0, 30.0, 60.0),
    )

    TOKENS = Counter(
        "devbuddy_llm_tokens_total",
        "Tokens consumed, by model and direction",
        ["model", "direction"],
    )

    COST = Counter(
        "devbuddy_llm_cost_usd_total",
        "Cumulative USD spent on model calls",
        ["model"],
    )

    TOOL_ERRORS = Counter(
        "devbuddy_tool_errors_total",
        "Tool call failures, by tool and failure kind",
        ["tool", "kind"],
    )

    GUARDRAIL_BLOCKS = Counter(
        "devbuddy_guardrail_blocks_total",
        "Requests or responses stopped by a guardrail, by rule",
        ["rule"],
    )
else:  # pragma: no cover - only on module reload
    _c = REGISTRY._names_to_collectors
    REQUESTS = _c["devbuddy_requests_total"]
    LATENCY = _c["devbuddy_request_latency_seconds"]
    TOKENS = _c["devbuddy_llm_tokens_total"]
    COST = _c["devbuddy_llm_cost_usd_total"]
    TOOL_ERRORS = _c["devbuddy_tool_errors_total"]
    GUARDRAIL_BLOCKS = _c["devbuddy_guardrail_blocks_total"]


# ─────────────────────────────────────────────────────────────
#  In-process ledger
# ─────────────────────────────────────────────────────────────
@dataclass
class Ledger:
    """Running totals for this process.

    Prometheus counters are write-only from the application's point of view —
    you cannot read one back to decide whether to stop. The agent's cost guard
    needs a number it can compare *right now*, so the same call updates both.
    """

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    usd: float = 0.0
    by_model: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, model: str, prompt_tokens: int, completion_tokens: int, usd: float) -> None:
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.usd += usd
            self.by_model[model] = self.by_model.get(model, 0.0) + usd

    def reset(self) -> None:
        with self._lock:
            self.calls = 0
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.usd = 0.0
            self.by_model = {}


ledger = Ledger()


# ─────────────────────────────────────────────────────────────
#  Recording
# ─────────────────────────────────────────────────────────────
def record_llm_call(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Record one model call. Returns what it cost, in USD.

    This is the single place tokens become money. Everything else — the
    Grafana burn-rate panel, the agent's cost guard, the number printed at the
    end of a run — reads the result of this function.
    """
    usd = cost_of(model, prompt_tokens, completion_tokens)
    TOKENS.labels(model, "in").inc(prompt_tokens)
    TOKENS.labels(model, "out").inc(completion_tokens)
    COST.labels(model).inc(usd)
    ledger.add(model, prompt_tokens, completion_tokens, usd)
    return usd


def record_request(status: str, entrypoint: str) -> None:
    """One completed request. status is 'ok', 'error' or 'blocked'."""
    REQUESTS.labels(status, entrypoint).inc()


def record_latency(step: str, seconds: float) -> None:
    LATENCY.labels(step).observe(seconds)


def record_tool_error(tool: str, kind: str) -> None:
    """A tool call failed. `kind` is the shape of the failure, not its message.

    'timeout', 'unavailable', 'bad_argument' — a bounded vocabulary. Passing
    the exception text here would put an unbounded string into a label and
    take Prometheus down with it.
    """
    TOOL_ERRORS.labels(tool, kind).inc()


def record_guardrail_block(rule: str) -> None:
    GUARDRAIL_BLOCKS.labels(rule).inc()


@contextmanager
def time_step(step: str):
    """Time a block of work into the latency histogram.

    Records on the way out whether or not the body raised — a step that fails
    after 30 seconds still took 30 seconds, and leaving it out of the
    histogram makes a broken system look faster than a working one.
    """
    started = time.perf_counter()
    try:
        yield
    finally:
        record_latency(step, time.perf_counter() - started)


# ─────────────────────────────────────────────────────────────
#  The scrape endpoint
# ─────────────────────────────────────────────────────────────
_server_port: int | None = None


def start_metrics_server(port: int | None = None) -> int | None:
    """Expose /metrics. Returns the bound port, or None if it did not start.

    Idempotent, and never fatal. If the port is taken — the usual cause is a
    second DevBuddy process, such as the MCP server started in another
    terminal — this logs and carries on unmonitored rather than refusing to
    answer questions. Losing telemetry is bad; losing the service to protect
    the telemetry is worse.

    A caveat worth understanding before you trust a panel: Prometheus *pulls*,
    every 15 seconds. ``python src/agent.py`` lives for about ninety seconds,
    so Prometheus catches perhaps six snapshots and never sees the final
    counter values — a block that happens two seconds before exit is real, is
    in the trace, and is missing from Grafana. That is not a bug in the
    counter; it is what pull-based metrics do to short-lived processes. A real
    service runs continuously and the problem disappears. For genuinely
    batch-shaped work the answer is a Pushgateway, not a shorter scrape
    interval.
    """
    global _server_port

    if not settings.metrics_enabled or not METRICS_AVAILABLE:
        return None
    if _server_port is not None:
        return _server_port

    port = port or settings.metrics_port
    try:
        start_http_server(port)
    except OSError as exc:
        print(f"  [cost_tracker] metrics server not started on :{port} — {exc}")
        return None

    _server_port = port
    return port


# ═══════════════════════════════════════════════════════════════
#  Week 7 checkpoint:  python src/cost_tracker.py
# ═══════════════════════════════════════════════════════════════
def main() -> None:
    import urllib.request

    print("=" * 70)
    print("  DevBuddy — Week 7: Cost Tracking & Metrics")
    print("=" * 70)

    if not METRICS_AVAILABLE:
        print("\n  prometheus_client is not installed.")
        print("  Install the Week 7 extras:  uv pip install -e \".[obs]\"")
        return

    print("\n  Pricing")
    print(f"    {'model':38} {'in $/1M':>9} {'out $/1M':>9}")
    for model, (price_in, price_out) in PRICES.items():
        marker = " ←" if model == settings.devbuddy_model else ""
        print(f"    {model:38} {price_in:9.2f} {price_out:9.2f}{marker}")

    print("\n  One 4o-mini call, 1,200 in / 400 out")
    usd = record_llm_call("openai/gpt-4o-mini", 1200, 400)
    print(f"    ${usd:.6f}")
    print("\n  The same call on gpt-4o")
    print(f"    ${cost_of('openai/gpt-4o', 1200, 400):.6f}   "
          f"({cost_of('openai/gpt-4o', 1200, 400) / usd:.0f}x)")

    # Exercise every metric so the scrape below has something in it.
    record_request("ok", "fixed_chain")
    record_request("error", "dynamic_agent")
    record_request("blocked", "dynamic_agent")
    record_tool_error("get_build_status", "timeout")
    record_guardrail_block("prompt_injection")
    with time_step("retrieve_context"):
        time.sleep(0.05)
    with time_step("total"):
        time.sleep(0.1)

    port = start_metrics_server()
    if port is None:
        print("\n  Metrics server did not start; nothing to scrape.")
        return

    print(f"\n  Serving  http://localhost:{port}/metrics")
    body = urllib.request.urlopen(f"http://localhost:{port}/metrics", timeout=5).read().decode()

    names = [
        "devbuddy_requests_total",
        "devbuddy_request_latency_seconds",
        "devbuddy_llm_tokens_total",
        "devbuddy_llm_cost_usd_total",
        "devbuddy_tool_errors_total",
        "devbuddy_guardrail_blocks_total",
    ]
    print("\n  Exposed metrics")
    for name in names:
        present = any(line.startswith(f"# HELP {name}") for line in body.splitlines())
        print(f"    {'✓' if present else '✗'} {name}")

    print("\n  Sample lines")
    for line in body.splitlines():
        if line.startswith(("devbuddy_llm_cost", "devbuddy_requests_total")):
            print(f"    {line}")

    print(f"\n  Ledger: {ledger.calls} calls, "
          f"{ledger.prompt_tokens} in / {ledger.completion_tokens} out, "
          f"${ledger.usd:.6f}")
    print("\n" + "=" * 70)
    print("  Prometheus scrapes this page every 15s. Start the stack with")
    print("  'docker compose up -d' and check http://localhost:9090/targets.")
    print("=" * 70)


if __name__ == "__main__":
    main()
