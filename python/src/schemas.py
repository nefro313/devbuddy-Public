"""
Week 2 — Structured Outputs (schemas only)

Pydantic models — the *contract*. No LLM imports here, so these are pure and
testable without a network or an API key.

Two schema families:
  BuildCheck            → flat, 4-field PR analysis (in-session)
  ServiceReadinessReport → composed, nested, validated (self-learning + capstone preview)

The functions that call the LLM (analyze_pr, generate_readiness_report) live in
src/llm_functions.py — the "action" that fills this contract.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional


# ═══════════════════════════════════════════════════════════════
# PR Analysis — flat schema for the in-session exercise
# ═══════════════════════════════════════════════════════════════

class BuildCheck(BaseModel):
    """A structured analysis of a PR or code change."""
    project: str = Field(description="Project or service name")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="How urgent is this change?"
    )
    summary: str = Field(description="One-sentence summary of the change")
    affected_files: list[str] = Field(description="Files modified by this change")


# ═══════════════════════════════════════════════════════════════
# Service Readiness Report — composed schema for self-learning
#
# This mirrors the DevBuddy end-state output.
# Engineers build and test this with mock data — no API calls.
#
# Architecture (from Plan.md):
#   User Query → Guardrail → Orchestrator → RAG + Tools → Structured Output
#   Final output: {ready, blockers, next_steps, evidence}
# ═══════════════════════════════════════════════════════════════

class ServiceInfo(BaseModel):
    """Identity of the service being evaluated."""
    name: str = Field(description="Service name, e.g. 'auth-service'")
    version: str = Field(description="Currently deployed version, e.g. '2.1.0'")
    owner_team: str = Field(description="Team responsible for this service")


class BuildStatus(BaseModel):
    """Current build health of the service."""
    status: Literal["healthy", "degraded", "down", "unknown"] = Field(
        description="Current build/health status"
    )
    last_deploy: str = Field(description="ISO timestamp of the most recent deployment")
    failing_since: Optional[str] = Field(
        None,
        description="ISO timestamp of when the build started failing, if degraded or down"
    )

    @field_validator("failing_since")
    @classmethod
    def failing_since_required_for_unhealthy(cls, v, info):
        """If status is degraded or down, failing_since should be present."""
        status = info.data.get("status")
        if status in ("degraded", "down") and v is None:
            raise ValueError(
                f"failing_since is required when status is '{status}'. "
                f"Provide an ISO timestamp."
            )
        return v


class DeployRecord(BaseModel):
    """A single deployment event."""
    sha: str = Field(description="Commit SHA of the deployment")
    author: str = Field(description="Engineer who triggered the deploy")
    timestamp: str = Field(description="ISO timestamp of the deployment")
    status: Literal["success", "failed", "rolling_back"] = Field(
        description="Outcome of this deployment"
    )


class DeploymentInfo(BaseModel):
    """Recent deployment history for the service."""
    recent_deploys: list[DeployRecord] = Field(
        description="Last N deployments, most recent first"
    )
    active_incidents: list[str] = Field(
        default_factory=list,
        description="IDs or summaries of any active incidents"
    )


class EvidenceChunk(BaseModel):
    """A piece of supporting context retrieved or produced during analysis."""
    source: Literal["rag", "tool", "user"] = Field(
        description="Where this evidence came from — RAG retrieval, tool output, or user query"
    )
    content: str = Field(description="The evidence content")
    relevance_score: Optional[float] = Field(
        None,
        description="0.0–1.0 relevance score from the retriever, if sourced from RAG"
    )


class ReadinessVerdict(BaseModel):
    """Final verdict: is this service ready for the target version?"""
    ready: bool = Field(description="True if the service can proceed to the target version")
    confidence: Literal["low", "medium", "high"] = Field(
        description="How confident is this verdict?"
    )
    blockers: list[str] = Field(
        default_factory=list,
        description="Reasons the service is NOT ready. Empty if ready=true."
    )
    recommended_next_steps: list[str] = Field(
        default_factory=list,
        description="What to do next — regardless of ready/blocked"
    )


class ServiceReadinessReport(BaseModel):
    """
    The structured output DevBuddy produces for a service readiness check.

    This is what the capstone delivers. It composes context (RAG),
    live data (tools), and reasoning into one typed, validated contract.

    Engineers test this with mock data during Week 2 self-learning.
    """
    service: ServiceInfo
    build: BuildStatus
    deployment: DeploymentInfo
    verdict: ReadinessVerdict
    evidence: list[EvidenceChunk] = Field(
        default_factory=list,
        description="Supporting evidence from retrieval and tool calls"
    )

    @model_validator(mode="after")
    def readiness_sanity_check(self):
        """
        Cross-field invariant: if ready=True, blockers must be empty.
        If ready=False, blockers should be non-empty (confidence='low' allows
        missing blockers — that's the 'we don't know' case).
        """
        if self.verdict.ready and self.verdict.blockers:
            raise ValueError(
                f"Contradiction: verdict.ready=True but blockers={self.verdict.blockers}. "
                f"If there are blockers, ready must be False."
            )
        if not self.verdict.ready and self.verdict.confidence != "low" and not self.verdict.blockers:
            raise ValueError(
                f"verdict.ready=False with confidence='{self.verdict.confidence}' "
                f"but no blockers listed. Either lower confidence to 'low' or add blockers."
            )
        return self

    @model_validator(mode="after")
    def confidence_low_if_no_evidence(self):
        """If there's no evidence, confidence cannot be higher than 'low'."""
        if not self.evidence and self.verdict.confidence != "low":
            raise ValueError(
                f"No evidence provided but confidence='{self.verdict.confidence}'. "
                f"Without evidence, confidence must be 'low'."
            )
        return self

