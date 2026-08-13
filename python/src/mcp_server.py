"""
DevBuddy — MCP Server (Week 5)

    ┌──────────────────┐     ┌──────────────────┐     ┌─────┐
    │   MCP Server     │ <── │   MCP Client     │ <── │ LLM │
    │  (this file)     │     │  (DevBuddy)      │     │     │
    │                  │     │                  │     │     │
    │ search_docs      │     │ 1. Discover tools│     │     │
    │ get_build_status │     │ 2. Model decides │     │     │
    │ get_recent_      │     │ 3. Client calls  │     │     │
    │   deploys        │     │    server        │     │     │
    │ get_active_      │     │ 4. Returns result│     │     │
    │   incidents      │     │                  │     │     │
    └──────────────────┘     └──────────────────┘     └─────┘

Week 4's tools read hardcoded dicts. These read the Week 3 Qdrant index and
synthesise an answer with the LLM. The tool *signatures* are unchanged — which
is the whole point. A tool is an interface; where its data comes from is an
implementation detail its callers never see.

Write once, consume anywhere: any MCP client in any language can call these.

Running it:

    python src/mcp_server.py           # network transport (Week 6 connects here)
    python src/mcp_server.py sse       # legacy SSE, as docs/week-05.md describes
    python src/mcp_server.py stdio     # stdio, for a client that spawns us
    python src/mcp_server.py demo      # Week 5 checkpoint: connect as a client and call the tools

Imports: src.rag (Week 3), src.schemas (Week 2), src.llm (Week 1).
Imported by: src.agent (Week 6), over the network rather than as a Python import.
"""

import asyncio
import json
import logging
import re
import sys
from typing import Literal

# Renamed in MCP SDK 2.0: what docs/week-05.md calls
# `from mcp.server.fastmcp import FastMCP` is now `mcp.server.MCPServer`.
# Same decorator API, same protocol. Pin `mcp>=1.0.0,<2.0.0` in pyproject if
# you would rather follow the session's snippets literally.
from mcp import Client
from mcp.server import MCPServer
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings
from src.rag import index_documents, retrieve
from src.schemas import call_structured

mcp = MCPServer(
    "devbuddy-mcp",
    instructions=(
        "Release-readiness data for internal services. All answers are grounded "
        "in the team's own documentation, not in model knowledge."
    ),
    log_level="WARNING",
)

# The server installs a root logging handler at INFO, which turns every Qdrant
# and HTTP round-trip into console output and buries the actual tool results.
for _noisy in ("httpx", "httpcore", "qdrant_client", "sentence_transformers", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# ═══════════════════════════════════════════════════════════════
#  Wire format
# ═══════════════════════════════════════════════════════════════
# These are the shapes clients receive. They live here rather than in
# schemas.py because they are this server's public contract — schemas.py owns
# DevBuddy's internal domain models, and conflating the two makes the wire
# format impossible to change without touching the agent.
class BuildStatusReading(BaseModel):
    service: str
    status: Literal["healthy", "degraded", "down", "unknown"]
    last_deploy: str | None = Field(default=None, description="ISO-8601, or null if unknown")
    failing_since: str | None = None
    evidence: str = Field(description="The sentence from the docs this is based on")


class DeploySummary(BaseModel):
    sha: str
    author: str | None = None
    timestamp: str | None = None
    status: str
    version: str | None = None


class RecentDeploysReading(BaseModel):
    service: str
    deploys: list[DeploySummary] = Field(default_factory=list)


class IncidentSummary(BaseModel):
    id: str
    # Which service the incident is about, per the document. Chunk-level
    # filtering cannot separate two incidents that share a chunk, so this field
    # exists to let the caller filter per incident. See get_active_incidents().
    service: str = Field(description="The service this incident affects, as named in the doc")
    severity: str
    status: str
    summary: str
    error_code: str | None = None


class ActiveIncidentsReading(BaseModel):
    service: str
    incidents: list[IncidentSummary] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  Index lifecycle
# ═══════════════════════════════════════════════════════════════
def _log(message: str) -> None:
    """Log to stderr, never stdout.

    Under stdio transport, stdout *is* the JSON-RPC channel. A stray print()
    corrupts the stream and the client fails to parse a frame — a confusing
    failure that looks like a protocol bug rather than a logging mistake.
    """
    print(message, file=sys.stderr, flush=True)


def ensure_index() -> int:
    """Index shared/data/ if the collection is not already populated.

    The session notes say to index at startup. Doing it unconditionally would
    re-embed the whole corpus on every stdio spawn, since a stdio client
    starts a fresh process per connection. Checking first keeps a warm
    collection warm and still builds one on a cold machine.
    """
    try:
        client = QdrantClient(url=settings.qdrant_url)
        if client.collection_exists(settings.qdrant_collection):
            existing = client.count(settings.qdrant_collection).count
            if existing:
                _log(f"[devbuddy-mcp] index ready: {existing} chunks")
                return existing
    except Exception as exc:
        _log(f"[devbuddy-mcp] could not reach Qdrant at {settings.qdrant_url}: {exc}")
        raise

    _log("[devbuddy-mcp] indexing shared/data/ …")
    count = index_documents()
    _log(f"[devbuddy-mcp] indexed {count} chunks")
    return count


def _normalise(text: str) -> str:
    """Strip to lowercase alphanumerics so 'Auth Service' matches 'auth-service'."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _about_service(chunks: list[str], service_name: str) -> list[str]:
    """Keep only chunks that actually name the service.

    Semantic retrieval returns what is *similar*, not what is *about* the thing
    you asked for. Asking for payment-api incidents surfaces the auth-service
    incident too — same document, same shape, near-identical wording — and the
    model, handed a chunk it was told is relevant, dutifully reports INC-799 as
    a payment-api incident. Nothing in the prompt reliably prevents that; a
    filter does. Wrong-service attribution is the failure mode that makes a
    grounded answer worse than no answer, because it looks sourced.
    """
    target = _normalise(service_name)
    return [chunk for chunk in chunks if target in _normalise(chunk)]


def _synthesise(
    instructions: str,
    query: str,
    schema: type[BaseModel],
    service_name: str | None = None,
    k: int = 8,
) -> BaseModel:
    """Retrieve from Qdrant, then have the LLM extract a typed answer.

    Two Week-2 guarantees ride along for free: the result is schema-validated,
    and a validator rejection is retried rather than returned as bad JSON.

    Returns the model instance rather than JSON so callers can apply their own
    filtering before serialising.
    """
    chunks = retrieve(query, k=k)

    if service_name:
        chunks = _about_service(chunks, service_name)
        if not chunks:
            # No document mentions this service. Returning the empty shape is
            # both cheaper and more honest than paying for a call that can only
            # produce a guess.
            return schema.model_validate(
                {"service": service_name, "status": "unknown", "evidence": "not in corpus"}
                if "status" in schema.model_fields
                else {"service": service_name}
            )

    context = "\n\n---\n\n".join(chunks)

    result, _ = call_structured(
        schema,
        [
            SystemMessage(
                content=(
                    f"{instructions}\n\n"
                    "Use ONLY the context provided. Every passage below is about "
                    f"{service_name or 'the subject of the request'}; ignore any "
                    "detail that names a different service.\n"
                    "If the context does not support a value, use null or an "
                    "empty list — never guess. Copy identifiers, timestamps and "
                    "error codes exactly as written, and do not add a time of "
                    "day to a date that does not have one."
                )
            ),
            HumanMessage(content=f"CONTEXT:\n{context}\n\nRequest: {query}"),
        ],
    )
    return result


# ═══════════════════════════════════════════════════════════════
#  Tools
# ═══════════════════════════════════════════════════════════════
@mcp.tool()
def search_docs(query: str, k: int = 5) -> str:
    """Search the team's documentation and return the most relevant passages.

    Use for open questions about specs, SLAs, runbooks or contribution
    process — anything not covered by the status, deploy or incident tools.
    """
    chunks = retrieve(query, k=k)
    return json.dumps({"query": query, "count": len(chunks), "chunks": chunks})


@mcp.tool()
def get_build_status(service_name: str) -> str:
    """Return the current build/health status for a given service.

    Use for whether a service is healthy, degraded or broken, and when it last
    deployed. Does not return deployment history or incidents.
    """
    return _synthesise(
        "Extract the current build and health status for the service.",
        f"{service_name} build status health deploy",
        BuildStatusReading,
        service_name=service_name,
    ).model_dump_json()


@mcp.tool()
def get_recent_deploys(service_name: str, limit: int = 5) -> str:
    """Return the last N deployments for a given service, newest first.

    Use for what shipped, who deployed it, and whether a deploy failed or was
    rolled back. Does not return current health.
    """
    return _synthesise(
        f"Extract up to {limit} of the most recent deployments for the service, "
        "newest first.",
        f"{service_name} deployment log deploy SHA rollback",
        RecentDeploysReading,
        service_name=service_name,
    ).model_dump_json()


@mcp.tool()
def get_active_incidents(service_name: str) -> str:
    """Return any active (unresolved) incidents for a given service.

    An incident whose status is resolved is not active and must be omitted.
    """
    reading = _synthesise(
        "Extract every incident in the context, recording the service each one "
        "affects and its resolution status exactly as written.",
        f"{service_name} incident severity error code status",
        ActiveIncidentsReading,
        service_name=service_name,
    )

    # Both filters are applied here, in code, rather than left to the prompt.
    #
    # Service: incident-log.md is small enough that several incidents share a
    # single 512-character chunk, so chunk-level filtering cannot separate
    # them — the chunk mentions payment-api, so it survives, auth-service
    # incident and all. Asked for payment-api the model then reliably returned
    # INC-799, an auth-service incident, because it was sitting right there.
    #
    # Resolved: "omit resolved incidents" is a rule with one correct answer,
    # and a rule with one correct answer belongs in code. Reporting a closed
    # Sev2 as active does not fail loudly — it just sends someone chasing a
    # problem that was fixed weeks ago.
    target = _normalise(service_name)
    closed = {"resolved", "closed", "mitigated"}
    reading.incidents = [
        incident
        for incident in reading.incidents
        if target in _normalise(incident.service)
        and incident.status.lower() not in closed
    ]
    return reading.model_dump_json()


# ═══════════════════════════════════════════════════════════════
#  Week 5 checkpoint:  python src/mcp_server.py demo
# ═══════════════════════════════════════════════════════════════
def _rule(title: str) -> None:
    print(f"\n{'─' * 68}\n  {title}\n{'─' * 68}")


def _text_of(result) -> str:
    """Pull the text payload out of a CallToolResult."""
    parts = [getattr(block, "text", "") for block in (result.content or [])]
    return "".join(parts)


async def _demo() -> None:
    print("=" * 68)
    print("  DevBuddy — Week 5: MCP")
    print("=" * 68)

    ensure_index()

    # Prefer a real network transport. Falling back in-process keeps the
    # checkpoint runnable without a second terminal, but it is worth knowing
    # which one you just exercised — Week 6 uses the SSE path.
    transport = settings.mcp_url
    try:
        probe = Client(transport)
        await asyncio.wait_for(probe.__aenter__(), timeout=4)
        client, mode = probe, f"{settings.mcp_transport} → {transport}"
    except Exception:
        client, mode = Client(mcp), "in-process (no SSE server running)"
        await client.__aenter__()

    try:
        print(f"\n  connected via {mode}")

        # ── DISCOVER ────────────────────────────────────────────
        _rule("DISCOVER — list_tools()")
        listing = await client.list_tools()
        for tool in listing.tools:
            summary = (tool.description or "").strip().splitlines()[0]
            print(f"  • {tool.name:22} {summary}")

        # ── QUERY ───────────────────────────────────────────────
        _rule("QUERY — get_build_status, grounded in the Qdrant index")
        for service in ("auth-service", "payment-api"):
            payload = json.loads(_text_of(await client.call_tool(
                "get_build_status", {"service_name": service}
            )))
            print(f"  {service:18} {payload['status'].upper():9} "
                  f"last deploy {payload.get('last_deploy')}")
            print(f"  {'':18} evidence: {payload.get('evidence', '')[:80]}")

        _rule("QUERY — get_recent_deploys(payment-api, limit=2)")
        payload = json.loads(_text_of(await client.call_tool(
            "get_recent_deploys", {"service_name": "payment-api", "limit": 2}
        )))
        for deploy in payload["deploys"]:
            print(f"  {deploy['sha']:14} {str(deploy.get('author')):8} "
                  f"{str(deploy.get('timestamp')):22} {deploy['status']}")

        _rule("QUERY — get_active_incidents")
        for service in ("payment-api", "inventory-service"):
            payload = json.loads(_text_of(await client.call_tool(
                "get_active_incidents", {"service_name": service}
            )))
            if not payload["incidents"]:
                print(f"  {service:18} no active incidents")
            for incident in payload["incidents"]:
                print(f"  {service:18} {incident['severity']:5} {incident['id']:9} "
                      f"{incident['summary'][:44]}")

        _rule("QUERY — search_docs (raw retrieval, no LLM)")
        payload = json.loads(_text_of(await client.call_tool(
            "search_docs", {"query": "payment API error codes", "k": 2}
        )))
        for i, chunk in enumerate(payload["chunks"], 1):
            print(f"  [{i}] {chunk.strip().splitlines()[0][:64]}")

        # ── ERRORS ──────────────────────────────────────────────
        _rule("Wrong tool name — a clear error, not a crash")
        try:
            bad = await client.call_tool("get_buildstatus", {"service_name": "payment-api"})
            print(f"  is_error={bad.is_error}")
            print(f"  {_text_of(bad)[:160]}")
        except Exception as exc:
            print(f"  {type(exc).__name__}: {str(exc)[:160]}")

    finally:
        await client.__aexit__(None, None, None)

    print("\n" + "=" * 68)
    print("  Week 5 complete. Same tool names as Week 4 — different data source,")
    print("  reachable from any MCP client in any language.")
    print("=" * 68)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "serve"

    if mode == "demo":
        asyncio.run(_demo())
        return

    ensure_index()

    if mode == "stdio":
        _log("[devbuddy-mcp] serving on stdio")
        mcp.run(transport="stdio")
        return

    transport = "sse" if mode == "sse" else settings.mcp_transport
    path = "/sse" if transport == "sse" else "/mcp"
    _log(f"[devbuddy-mcp] serving {transport} on "
         f"http://{settings.mcp_host}:{settings.mcp_port}{path}")
    mcp.run(transport=transport, host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
