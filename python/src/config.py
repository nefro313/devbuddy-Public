"""
DevBuddy — Central Configuration (Week 1)

One module reads the environment. Everything else imports from here.

Why a settings object instead of scattered ``os.environ.get()`` calls: by Week 6
the agent touches OpenRouter, Qdrant, an embedding model, an MCP server and two
runaway guards. If each module reads its own env var, changing the model means
grepping six files. Here it is one line.

The .env path is resolved from ``__file__``, not the current working directory,
so ``python src/rag.py``, ``pytest`` from ``python/``, and an MCP server spawned
as a subprocess from the repo root all load the same file.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

# python/ — holds .env and src/. shared/ is a sibling of python/, at the repo root.
PYTHON_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PYTHON_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PYTHON_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── Week 1 — OpenRouter ─────────────────────────────────────
    openrouter_api_key: str = ""
    openrouter_base: str = "https://openrouter.ai/api/v1"
    # Any OpenRouter model string. gpt-4o-mini is the series default: fast,
    # cheap, and reliable at both structured output and tool calling.
    devbuddy_model: str = "openai/gpt-4o-mini"
    # Optional second model, used only by the model-swap exercise.
    devbuddy_model_alt: str = ""

    # ─── Week 3 — RAG ────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "devbuddy-docs"
    # Local sentence-transformers model. Free, no API call, ~80MB on first use.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_k: int = 3

    # ─── Week 5 — MCP server ─────────────────────────────────────
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    # docs/week-05.md was written for MCP SDK 1.x, where SSE was the network
    # transport. SDK 2.0's Client negotiates streamable-http by default and
    # errors against a legacy SSE endpoint, so that is the default here.
    # Set MCP_TRANSPORT=sse to serve the older path instead.
    mcp_transport: Literal["streamable-http", "sse"] = "streamable-http"

    # ─── Week 6 — Agent guards ───────────────────────────────────
    # A runaway agent is a billing incident. These are hard stops, not hints.
    max_steps: int = 10
    max_cost: float = 2.00

    # ─── Cost model (USD per 1M tokens) ──────────────────────────
    # Matches gpt-4o-mini. Change both if you change devbuddy_model, otherwise
    # the cost numbers printed by every week are quietly wrong.
    price_input_per_m: float = 0.15
    price_output_per_m: float = 0.60

    @property
    def data_dir(self) -> Path:
        """The RAG corpus: shared/data/ at the repo root."""
        return REPO_ROOT / "shared" / "data"

    @property
    def mcp_url(self) -> str:
        """The endpoint the Week 6 agent connects to, for the active transport."""
        path = "/sse" if self.mcp_transport == "sse" else "/mcp"
        return f"http://{self.mcp_host}:{self.mcp_port}{path}"

    def cost_of(self, prompt_tokens: int, completion_tokens: int) -> float:
        """USD cost of one call. The single place this arithmetic lives."""
        return (
            prompt_tokens * self.price_input_per_m
            + completion_tokens * self.price_output_per_m
        ) / 1_000_000


def _propagate_to_environ(s: Settings) -> None:
    """Push values into ``os.environ`` for libraries that read it directly.

    Uses ``setdefault`` so a real OS-level env var always beats .env.
    """
    if s.openrouter_api_key:
        os.environ.setdefault("OPENROUTER_API_KEY", s.openrouter_api_key)
    # sentence-transformers/transformers chatter on every import otherwise.
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    _propagate_to_environ(s)
    return s


settings = get_settings()


def validate() -> None:
    """Raise if required config is missing.

    Called explicitly by ``get_llm()`` rather than at import time, so that
    importing any module — including in tests that never hit the network —
    does not require a key.
    """
    if not settings.openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not set.\n"
            f"Copy .env.example to .env in {PYTHON_DIR} and add your key."
        )


if __name__ == "__main__":
    # Week 1 checkpoint: python src/config.py
    key = settings.openrouter_api_key
    print("DevBuddy configuration")
    print(f"  .env path      {PYTHON_DIR / '.env'}")
    print(f"  API key        {'set (' + key[:8] + '…)' if key else 'MISSING'}")
    print(f"  model          {settings.devbuddy_model}")
    print(f"  qdrant         {settings.qdrant_url} → {settings.qdrant_collection}")
    print(f"  embeddings     {settings.embedding_model}")
    print(f"  chunking       size={settings.chunk_size} overlap={settings.chunk_overlap}")
    print(f"  corpus         {settings.data_dir} ({'found' if settings.data_dir.is_dir() else 'MISSING'})")
    print(f"  mcp            {settings.mcp_url}  ({settings.mcp_transport})")
    print(f"  guards         max_steps={settings.max_steps} max_cost=${settings.max_cost:.2f}")
