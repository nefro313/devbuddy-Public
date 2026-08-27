"""
Week 2 — Structured output functions (the "action" that fills the contract).

These functions call the LLM and return typed objects. They live here — not in
schemas.py — so schemas.py stays pure (models only, no LLM imports). The schema
is the contract; these functions produce a model response that fits it.
"""
import json

from pydantic import ValidationError
from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_llm
from src.schemas import BuildCheck, ServiceReadinessReport


# ═══════════════════════════════════════════════════════════════
# Reusable structured-output helper (validate + self-correct)
#
# One place for the "call the model, validate, retry with the error" loop, so
# later weeks (RAG, tools, agent) import it instead of re-implementing it.
# demo-05 is a thin wrapper over this.
#
# `method` picks how the schema is enforced:
#   "function_calling" — tool calling. Widest support → our portable default.
#   "json_schema"      — provider-native strict mode (newer OpenAI/GPT-class).
#                        Many free OpenRouter models do NOT support this.
#   "json_mode"        — valid JSON only, not your shape.
# ═══════════════════════════════════════════════════════════════

def get_structured(
    messages,
    schema,
    *,
    method: str = "function_calling",
    temperature: float = 0.0,
    max_tokens: int | None = None,
    retries: int = 2,
):
    """Return a validated `schema` instance; on drift, feed the error back and retry.

    Args:
        messages: a prompt string or a list of LangChain messages.
        schema: the Pydantic model to enforce.
        method: 'function_calling' (portable) | 'json_schema' (strict) | 'json_mode'.
        retries: extra attempts after the first (total tries = retries + 1).

    Raises:
        ValueError: if no valid instance is produced within the retry budget.
    """
    llm = get_llm(temperature=temperature, max_tokens=max_tokens).with_structured_output(
        schema, method=method, include_raw=True
    )
    convo = list(messages) if isinstance(messages, list) else [HumanMessage(content=messages)]
    last_err = None
    for _ in range(retries + 1):
        out = llm.invoke(convo)
        parsed, err = out.get("parsed"), out.get("parsing_error")
        if parsed is not None and err is None:
            return parsed
        last_err = err
        convo.append(HumanMessage(content=(
            "Your previous reply failed schema validation with this error:\n"
            f"{last_err}\n\nReturn a corrected response that satisfies the schema."
        )))
    raise ValueError(f"Could not get a valid {schema.__name__} after {retries + 1} tries: {last_err}")


def analyze_pr(
    title: str,
    diff: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    method: str = "function_calling",
) -> BuildCheck:
    """
    Analyze a PR and return a structured BuildCheck.

    Args:
        title: PR title
        diff: PR diff content
        temperature: 0.0 for deterministic output (default)
        max_tokens: Max tokens in the response. None = model default.
        method: how the schema is enforced (see get_structured). Default
            'function_calling' for portability across OpenRouter models. Free
            models often reject 'json_schema' — switch to gpt-4o-mini to use it.

    Returns:
        BuildCheck with project, severity, summary, affected_files
    """
    prompt = (
        "You are a code reviewer. Analyze the given PR and return a BuildCheck.\n"
        "- severity: 'critical' if it touches auth, payments, or security. "
        "'high' if it changes core logic. 'medium' for feature work. 'low' for docs/typos.\n"
        "- summary: one sentence describing what changed and why.\n"
        "- affected_files: list the files mentioned in the diff.\n"
        "- project: extract the project or service name from the PR context."
    )
    return analyze_pr_with_prompt(
        title=title,
        diff=diff,
        prompt_template=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        method=method,
    )


def analyze_pr_with_prompt(
    title: str,
    diff: str,
    prompt_template: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    method: str = "function_calling",
) -> BuildCheck:
    """Run a PR classification using a custom prompt template for prompt-testing demos."""
    llm = get_llm(temperature=temperature, max_tokens=max_tokens)
    structured = llm.with_structured_output(BuildCheck, method=method)

    prompt = prompt_template.replace("{{title}}", title).replace("{{diff}}", diff)
    result = structured.invoke([
        SystemMessage(content=(
            "You are a careful code reviewer. Follow the instructions exactly and "
            "return only a valid JSON object that matches the schema."
        )),
        HumanMessage(content=prompt),
    ])

    return result


def generate_readiness_report(
    service_name: str,
    build_data: dict,
    deploy_data: dict,
    temperature: float = 0.0,
) -> ServiceReadinessReport:
    """
    Generate a ServiceReadinessReport from mock build/deploy data.

    This is the capstone pattern: take context (mock data standing in for
    RAG + tool output), feed it to the LLM, get back a typed, validated
    ServiceReadinessReport. No API calls to real services — just the LLM.

    Args:
        service_name: e.g. 'auth-service'
        build_data: dict with build status fields (status, last_deploy, failing_since)
        deploy_data: dict with deployment history (recent_deploys, active_incidents)
        temperature: 0.0 for deterministic output

    Returns:
        ServiceReadinessReport — composed, nested, validated
    """
    llm = get_llm(temperature=temperature)
    structured = llm.with_structured_output(ServiceReadinessReport)

    result = structured.invoke([
        SystemMessage(content=(
            "You are a site reliability engineer assessing whether a service is ready "
            "for its next release. You are given build health data and recent deployment "
            "history. Produce a ServiceReadinessReport.\n\n"
            "RULES:\n"
            "- If the build status is 'healthy' with no active incidents and recent "
            "deploys are all 'success', the service is ready with high confidence.\n"
            "- If the build is 'degraded' or there are active incidents, the service is "
            "NOT ready. List specific blockers.\n"
            "- If there is no data at all, set confidence to 'low'.\n"
            "- Every verdict must be supported by evidence. Reference the data you were given.\n"
            "- Blockers should be specific and actionable, not vague."
        )),
        HumanMessage(content=(
            f"Service: {service_name}\n\n"
            f"Build data:\n{json.dumps(build_data, indent=2)}\n\n"
            f"Deployment data:\n{json.dumps(deploy_data, indent=2)}"
        )),
    ])

    return result
