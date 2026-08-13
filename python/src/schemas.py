"""
DevBuddy — Structured Outputs (Week 2)

The model is a typed function, not a text generator.

Two schema families live here:

* ``BuildCheck`` — flat, 4 fields, produced by ``analyze_pr()``. The in-session
  exercise: a PR diff goes in, a typed object comes out.
* ``ServiceReadinessReport`` — 6 nested models with optional fields and
  cross-field validators. This is the shape DevBuddy emits by Week 7; the
  ``shared/data/service-readiness-*.json`` fixtures are real examples of it.

The important idea is the difference between a *request* and a *contract*.
Asking the model for JSON is a request — it complies most of the time.
``with_structured_output()`` plus a Pydantic validator is a contract: output
that violates it never reaches your code as a valid object. Where JSON Schema
can't express a rule (see ``_sensitive_paths_need_high_severity``), the
validator rejects the answer and ``call_structured()`` sends the model its own
error to fix.

Imports: src.llm (Week 1). Imported by: src.agent (Week 6).
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.config import settings
from src.llm import get_llm, usage_of

T = TypeVar("T", bound=BaseModel)


# ═══════════════════════════════════════════════════════════════
#  Cost accounting
# ═══════════════════════════════════════════════════════════════
@dataclass
class CallStats:
    """Token and cost accounting for one logical LLM call.

    Deliberately accumulates across retries: a call that needed three attempts
    cost three attempts' worth of tokens, and hiding that is how you end up
    with a surprise invoice.
    """

    model: str
    temperature: float
    attempts: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_s: float = 0.0
    errors: list[str] = field(default_factory=list)

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.attempts += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost(self) -> float:
        return settings.cost_of(self.prompt_tokens, self.completion_tokens)

    def line(self) -> str:
        retry_note = "" if self.attempts <= 1 else f"  ⚠ {self.attempts} attempts"
        return (
            f"{self.total_tokens} tokens "
            f"({self.prompt_tokens} in / {self.completion_tokens} out)  "
            f"${self.cost:.6f}  {self.elapsed_s:.2f}s  "
            f"temp={self.temperature}{retry_note}"
        )


class SchemaRetryError(RuntimeError):
    """Raised when the model could not satisfy the schema within max_attempts."""

    def __init__(self, schema: type[BaseModel], stats: CallStats):
        self.schema = schema
        self.stats = stats
        super().__init__(
            f"{schema.__name__} validation failed after {stats.attempts} attempts. "
            f"Last error: {stats.errors[-1] if stats.errors else 'unknown'}"
        )


# ═══════════════════════════════════════════════════════════════
#  BuildCheck — the in-session schema
# ═══════════════════════════════════════════════════════════════
# Paths that make a change risky no matter how small the diff looks.
_SENSITIVE_PATH_HINTS = (
    "auth",
    "payment",
    "session",
    "token",
    "credential",
    "secret",
    "password",
)


class BuildCheck(BaseModel):
    """Analysis of a single pull request."""

    model_config = ConfigDict(extra="forbid")

    project: str = Field(description="The project or service the PR belongs to")
    severity: Literal["critical", "high", "medium", "low"] = Field(
        description=(
            "'critical' for auth/payments/security changes, 'high' for core "
            "logic, 'medium' for feature work, 'low' for docs and typos"
        )
    )
    summary: str = Field(
        min_length=10,
        description="One sentence describing what changed and why",
    )
    affected_files: list[str] = Field(
        min_length=1,
        description="The file paths mentioned in the diff",
    )

    @model_validator(mode="after")
    def _sensitive_paths_need_high_severity(self) -> "BuildCheck":
        """A rule JSON Schema cannot express, so the model cannot be forced into it.

        The model is free to return ``severity='medium'`` for a change to
        ``auth.py`` — strict JSON Schema mode will happily accept it, because
        'medium' is a valid enum member. Only a cross-field validator catches
        it. This is the gap that makes ``call_structured()``'s retry loop worth
        writing: the contract is enforced here, in code, not hoped for in the
        prompt.
        """
        risky = [
            path
            for path in self.affected_files
            if any(hint in path.lower() for hint in _SENSITIVE_PATH_HINTS)
        ]
        if risky and self.severity not in ("critical", "high"):
            raise ValueError(
                f"{risky} touch auth/payment/security code, so severity must be "
                f"'critical' or 'high' — got '{self.severity}'"
            )
        return self


# ═══════════════════════════════════════════════════════════════
#  ServiceReadinessReport — the composed schema (Week 7 output shape)
# ═══════════════════════════════════════════════════════════════
class ServiceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    owner_team: str


class BuildInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "degraded", "down", "unknown"]
    last_deploy: datetime | None = Field(
        default=None, description="ISO-8601 timestamp of the most recent deploy"
    )
    # Optional on purpose: a healthy build has nothing to report here. Making it
    # required would force every caller to invent a value.
    failing_since: datetime | None = None


class DeployRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: str
    author: str
    timestamp: datetime
    status: Literal["success", "failed", "rolling_back", "in_progress"]


class DeploymentInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_deploys: list[DeployRecord] = Field(default_factory=list)
    active_incidents: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """Where a claim came from. Without this the report is just an opinion."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["rag", "tool", "model"]
    content: str
    # Only retrieval produces a similarity score; tool calls have none.
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    confidence: Literal["high", "medium", "low"]
    blockers: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


class ServiceReadinessReport(BaseModel):
    """"Is auth-service ready for v2.1?" — answered as a typed object.

    ``extra="forbid"`` throughout is deliberate. If a future model or a renamed
    upstream field introduces ``buildStatus`` alongside ``build``, this fails
    loudly at the boundary instead of silently reading a stale default.
    """

    model_config = ConfigDict(extra="forbid")

    service: ServiceInfo
    build: BuildInfo
    deployment: DeploymentInfo
    verdict: Verdict
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _verdict_is_internally_consistent(self) -> "ServiceReadinessReport":
        """Catch reports that contradict themselves.

        An LLM will cheerfully produce ``ready=true`` next to an unresolved
        Sev1 incident. Field-level types cannot see that; only a whole-object
        validator can.
        """
        if not self.verdict.ready and not self.verdict.blockers:
            raise ValueError(
                "verdict.ready is false but no blockers were listed — "
                "an unready service must say what is blocking it"
            )
        if self.verdict.ready and self.verdict.blockers:
            raise ValueError(
                f"verdict.ready is true but blockers are listed: {self.verdict.blockers}"
            )
        if self.verdict.ready and self.deployment.active_incidents:
            raise ValueError(
                "verdict.ready is true while incidents are unresolved: "
                f"{self.deployment.active_incidents}"
            )
        if self.build.status == "healthy" and self.build.failing_since is not None:
            raise ValueError(
                "build.status is 'healthy' but failing_since is set — pick one"
            )
        if self.build.status in ("degraded", "down") and self.build.failing_since is None:
            raise ValueError(
                f"build.status is '{self.build.status}' but failing_since is missing — "
                "a broken build must record when it broke"
            )
        return self


# ═══════════════════════════════════════════════════════════════
#  The structured-call engine
# ═══════════════════════════════════════════════════════════════
def _raw_text(raw) -> str:
    """Best-effort text of whatever the model actually returned."""
    if raw is None:
        return "(no response)"
    content = getattr(raw, "content", "") or ""
    if content:
        return str(content)[:800]
    tool_calls = getattr(raw, "tool_calls", None) or []
    if tool_calls:
        return json.dumps(tool_calls[0].get("args", {}))[:800]
    return "(empty response)"


def _validation_summary(exc: ValidationError) -> str:
    """Flatten a ValidationError into one line the model can act on."""
    parts = []
    for err in exc.errors():
        location = ".".join(str(p) for p in err["loc"]) or "<model>"
        parts.append(f"{location}: {err['msg']}")
    return "; ".join(parts)


def _validation_input(exc: ValidationError) -> str:
    """The payload the model sent, recovered from the error itself."""
    errors = exc.errors()
    if errors and "input" in errors[0]:
        try:
            return json.dumps(errors[0]["input"], default=str)[:800]
        except (TypeError, ValueError):
            return str(errors[0]["input"])[:800]
    return "(unavailable)"


def call_structured(
    schema: type[T],
    messages: Sequence[BaseMessage],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_attempts: int = 3,
) -> tuple[T, CallStats]:
    """Call the LLM and return a validated ``schema`` instance.

    On validation failure the model is shown its own output and the validator's
    complaint, then asked again — up to ``max_attempts`` times.

    Note what is *not* appended to the conversation: the raw assistant message.
    Under function-calling transport that message carries ``tool_calls``, and an
    assistant tool_call not followed by a matching tool result is a protocol
    error at the API. Quoting the text back inside a new human turn sidesteps
    that entirely and works under every transport.

    Raises:
        SchemaRetryError: if no attempt produced a valid object.
    """
    resolved_model = model or settings.devbuddy_model
    stats = CallStats(model=resolved_model, temperature=temperature)
    structured_llm = get_llm(
        model=resolved_model, temperature=temperature
    ).with_structured_output(schema, include_raw=True)

    conversation = list(messages)
    started = time.time()

    for _ in range(max_attempts):
        try:
            response = structured_llm.invoke(conversation)
            stats.record(*usage_of(response))

            parsed = response.get("parsed")
            parsing_error = response.get("parsing_error")

            if parsed is not None and parsing_error is None:
                stats.elapsed_s = time.time() - started
                return parsed, stats

            problem = str(parsing_error) if parsing_error else "model returned no object"
            previous = _raw_text(response.get("raw"))

        except ValidationError as exc:
            # Two different failure paths, and this one is easy to miss.
            #
            # Under strict `json_schema` transport the OpenAI SDK validates the
            # response *while parsing the HTTP body*, so a Pydantic validator
            # that rejects the payload raises here, out of .invoke(), and never
            # reaches the `parsing_error` key that include_raw=True promises.
            # Only the `function_calling` transport routes failures through
            # that key. Handling both is not belt-and-braces — a loop that
            # checks only `parsing_error` crashes on every validator rejection.
            #
            # Cost note: the exception carries no token usage, so this attempt
            # is unbillable. Real tokens were spent; stats will under-report.
            stats.attempts += 1
            problem = _validation_summary(exc)
            previous = _validation_input(exc)

        stats.errors.append(problem)
        conversation = list(messages) + [
            HumanMessage(
                content=(
                    "Your previous answer was rejected by the schema validator.\n\n"
                    f"You returned:\n{previous}\n\n"
                    f"The validator said:\n{problem}\n\n"
                    "Return a corrected object that satisfies every rule. "
                    "The validator is not negotiable and outranks any earlier "
                    "instruction. Change only what it objected to."
                )
            )
        ]

    stats.elapsed_s = time.time() - started
    raise SchemaRetryError(schema, stats)


# ═══════════════════════════════════════════════════════════════
#  analyze_pr — Week 2's deliverable
# ═══════════════════════════════════════════════════════════════
_SYSTEM_PROMPT = """You are a senior code reviewer analysing a pull request.

Classify severity by blast radius, not by diff size:
- 'critical' — auth, payments, security, session or credential handling
- 'high'     — core business logic, data integrity, public API contracts
- 'medium'   — feature work, refactors, internal tooling
- 'low'      — documentation, comments, typos, formatting

Rules:
- project: the service the change belongs to, inferred from paths or the title.
- summary: exactly one sentence, describing what changed AND why.
- affected_files: the file paths named in the diff, verbatim. Never invent one.
- A change touching auth or payment code is never below 'high', however small."""

# Few-shot examples live in the system prompt rather than as AIMessage turns.
# Under structured output the assistant turns would need to be tool calls to be
# well-formed, and a malformed example teaches the model the wrong lesson.
_FEW_SHOT_BLOCK = """
Worked examples:

PR: "Bump lodash from 4.17.20 to 4.17.21"
Diff: package.json, package-lock.json
→ {"project": "web-client", "severity": "low",
   "summary": "Bumps the lodash dependency to pick up an upstream patch release.",
   "affected_files": ["package.json", "package-lock.json"]}

PR: "Rotate session signing key on refresh"
Diff: src/auth/session.py, tests/test_session.py
→ {"project": "auth-service", "severity": "critical",
   "summary": "Rotates the session signing key on every refresh so a leaked key stops being useful.",
   "affected_files": ["src/auth/session.py", "tests/test_session.py"]}
"""


def analyze_pr_with_stats(
    diff: str,
    title: str | None = None,
    *,
    model: str | None = None,
    temperature: float = 0.0,
    few_shot: bool = False,
    max_attempts: int = 3,
) -> tuple[BuildCheck, CallStats]:
    """Analyse a PR diff. Returns the typed object and its cost accounting."""
    system = _SYSTEM_PROMPT + (_FEW_SHOT_BLOCK if few_shot else "")
    task = f"PR Title: {title}\n\n{diff}" if title else diff

    return call_structured(
        BuildCheck,
        [SystemMessage(content=system), HumanMessage(content=task)],
        model=model,
        temperature=temperature,
        max_attempts=max_attempts,
    )


def analyze_pr(
    diff: str,
    title: str | None = None,
    *,
    model: str | None = None,
    temperature: float = 0.0,
    few_shot: bool = False,
    max_attempts: int = 3,
) -> BuildCheck:
    """Analyse a PR diff and return a ``BuildCheck`` — a typed object, not a string."""
    result, _ = analyze_pr_with_stats(
        diff,
        title,
        model=model,
        temperature=temperature,
        few_shot=few_shot,
        max_attempts=max_attempts,
    )
    return result


# ═══════════════════════════════════════════════════════════════
#  Fixture loading
# ═══════════════════════════════════════════════════════════════
def load_diff(name: str) -> str:
    """Read a diff from shared/data/ (e.g. 'sample-diff.txt')."""
    return (settings.data_dir / name).read_text(encoding="utf-8")


def load_readiness_report(path: str | Path) -> ServiceReadinessReport:
    """Validate a service-readiness JSON file against the composed schema.

    Accepts a bare filename in shared/data/ or a full path.
    """
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = settings.data_dir / path
    return ServiceReadinessReport.model_validate_json(path.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════
#  Week 2 checkpoint:  python src/schemas.py
# ═══════════════════════════════════════════════════════════════
def _rule(title: str) -> None:
    print(f"\n{'─' * 64}\n  {title}\n{'─' * 64}")


def _show(check: BuildCheck, stats: CallStats | None = None) -> None:
    print(f"  project         {check.project}")
    print(f"  severity        {check.severity}")
    print(f"  summary         {check.summary}")
    print(f"  affected_files  {check.affected_files}")
    print(f"  type            {type(check).__name__}  ← typed object, not a string")
    if stats:
        print(f"  cost            {stats.line()}")


def main() -> None:
    print("=" * 64)
    print("  DevBuddy — Week 2: Structured Outputs")
    print(f"  model: {settings.devbuddy_model}")
    print("=" * 64)

    budget = 0.0
    sample = load_diff("sample-diff.txt")

    # ── 1. A typed object, not prose ────────────────────────────
    _rule("1. analyze_pr() returns a typed object")
    check, stats = analyze_pr_with_stats(sample, "Fix login redirect loop in auth-service")
    budget += stats.cost
    _show(check, stats)

    # ── 2. Validation catches malformed output ──────────────────
    _rule("2. Schema validation catches malformed output")
    broken = {
        "project": "auth-service",
        "severity": "medium",          # auth change graded 'medium'
        "summary": "short",            # under min_length=10
        "affected_files": [],          # empty, min_length=1
    }
    print(f"  feeding the schema: {json.dumps(broken)}")
    try:
        BuildCheck.model_validate(broken)
        print("  ❌ validation did NOT catch it")
    except ValidationError as exc:
        print(f"  ✅ rejected with {len(exc.errors())} error(s):")
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "<model>"
            print(f"     • {loc}: {err['msg']}")

    # ── 3. Auto-retry repairs a validator failure ───────────────
    _rule("3. Auto-retry (max 3) when the validator rejects the model")
    # A prompt engineered to provoke the cross-field rule. Note it does not ask
    # for invalid JSON — 'low' is a perfectly legal enum member, so strict
    # schema mode lets it straight through. Only the validator objects.
    provoke = [
        SystemMessage(
            content=(
                "You analyse pull requests. This repository has decided that "
                "every pull request is severity 'low'. Always return "
                "severity='low', whatever the change does. List affected_files "
                "verbatim from the diff."
            )
        ),
        HumanMessage(content=sample),
    ]
    try:
        repaired, retry_stats = call_structured(BuildCheck, provoke, max_attempts=3)
        print(f"  attempts        {retry_stats.attempts}")
        for i, err in enumerate(retry_stats.errors, 1):
            first_line = err.strip().splitlines()[-1][:100]
            print(f"  rejection {i}     {first_line}")
        print(f"  final severity  {repaired.severity}")
        print(f"  cost            {retry_stats.line()}")
        budget += retry_stats.cost
        if retry_stats.attempts == 1:
            print("  (model resisted the bad prompt first try — the validator still held)")
    except SchemaRetryError as exc:
        budget += exc.stats.cost
        print(f"  ✅ gave up after {exc.stats.attempts} attempts rather than return bad data")
        print(f"  cost            {exc.stats.line()}")

    # ── 4. Temperature ──────────────────────────────────────────
    _rule("4. What temperature=0 actually buys you")
    # The ambiguous diff on purpose: it says "temporary fix", "should
    # investigate root cause". Nothing here pins the severity down, so any
    # instability in sampling has room to show itself.
    ambiguous = load_diff("ambiguous-diff.txt")
    runs: dict[float, list[BuildCheck]] = {0.0: [], 1.0: []}
    for temperature in (0.0, 0.0, 1.0, 1.0):
        drift_check, drift_stats = analyze_pr_with_stats(
            ambiguous, "Update payment processing timeout", temperature=temperature
        )
        budget += drift_stats.cost
        runs[temperature].append(drift_check)
        print(f"  temp={temperature}  [{drift_check.severity:8}] {drift_check.summary}")

    for temperature, pair in runs.items():
        same_severity = pair[0].severity == pair[1].severity
        same_summary = pair[0].summary == pair[1].summary
        print(
            f"  temp={temperature}: severity stable={same_severity}  "
            f"summary identical={same_summary}"
        )
    print(
        "  ↑ temperature=0 is greedy decoding, not a determinism guarantee: the\n"
        "    graded field is reproducible, the prose usually is not. Depend on\n"
        "    the enum, never on the sentence."
    )

    # ── 5. Few-shot ─────────────────────────────────────────────
    _rule("5. Few-shot examples tighten adherence")
    for use_few_shot in (False, True):
        fs_check, fs_stats = analyze_pr_with_stats(
            "Add Python 3.11+ requirement and setup steps.\nFiles changed:\n- README.md",
            "Update README with setup instructions",
            few_shot=use_few_shot,
        )
        budget += fs_stats.cost
        label = "few-shot " if use_few_shot else "zero-shot"
        print(f"  {label}  [{fs_check.severity:8}] {fs_check.project:16} "
              f"{fs_stats.prompt_tokens} prompt tokens")
    print("  ↑ few-shot costs more prompt tokens — that is the trade you are making")

    # ── 6. The composed schema ──────────────────────────────────
    _rule("6. ServiceReadinessReport — nested, optional, cross-validated")
    for name in (
        "service-readiness-healthy.json",
        "service-readiness-degraded.json",
        "service-readiness-unknown.json",
    ):
        report = load_readiness_report(name)
        print(
            f"  ✅ {name:34} {report.service.name:18} "
            f"build={report.build.status:9} ready={str(report.verdict.ready):5} "
            f"blockers={len(report.verdict.blockers)} evidence={len(report.evidence)}"
        )

    print("\n  Now a self-contradicting report — ready=true with an open Sev1:")
    contradiction = json.loads(
        (settings.data_dir / "service-readiness-degraded.json").read_text()
    )
    contradiction["verdict"]["ready"] = True
    contradiction["verdict"]["blockers"] = []
    try:
        ServiceReadinessReport.model_validate(contradiction)
        print("  ❌ validation did NOT catch it")
    except ValidationError as exc:
        print(f"  ✅ {exc.errors()[0]['msg']}")

    print("\n" + "=" * 64)
    print(f"  Week 2 complete.  Total cost this run: ${budget:.6f}")
    print("=" * 64)


if __name__ == "__main__":
    main()
