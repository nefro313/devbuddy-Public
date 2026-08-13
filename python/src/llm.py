"""
DevBuddy — OpenRouter LLM Client Factory (Week 1)

Uses LangChain's ChatOpenAI pointed at OpenRouter.
One client. Any model. Swap by changing DEVBUDDY_MODEL in .env.

This is the foundation module: schemas, rag, tools, mcp_server and agent all
import ``get_llm()`` from here. None of them construct a client themselves.
"""

from langchain_openai import ChatOpenAI

from src.config import settings, validate


def get_llm(
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """
    Return a LangChain chat model pointed at OpenRouter.

    Args:
        model: OpenRouter model string (e.g. "openai/gpt-4o-mini",
               "anthropic/claude-sonnet-4"). Defaults to DEVBUDDY_MODEL.
        temperature: 0.0 for deterministic, higher for creative.
        max_tokens: Cap on response length. None = model default.

    Raises:
        ValueError: If OPENROUTER_API_KEY is not configured.
    """
    validate()

    kwargs = {
        "model": model or settings.devbuddy_model,
        "base_url": settings.openrouter_base,
        "api_key": settings.openrouter_api_key,
        "temperature": temperature,
        "default_headers": {
            "HTTP-Referer": "https://github.com/your-org/devbuddy",
            "X-Title": "DevBuddy",
        },
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    return ChatOpenAI(**kwargs)


def usage_of(response) -> tuple[int, int]:
    """
    Pull (prompt_tokens, completion_tokens) off any LangChain response.

    OpenRouter reports usage in different places depending on whether the call
    went through ``.invoke()``, ``.with_structured_output(include_raw=True)``,
    or a tool-calling loop. Every week needs these two numbers for cost, so the
    lookup lives here once instead of being re-guessed in five modules.
    """
    if response is None:
        return 0, 0

    # with_structured_output(include_raw=True) returns a dict, not a message.
    if isinstance(response, dict):
        response = response.get("raw")
        if response is None:
            return 0, 0

    usage = getattr(response, "usage_metadata", None)
    if usage:
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    meta = getattr(response, "response_metadata", {}) or {}
    token_usage = meta.get("token_usage", {}) or {}
    return token_usage.get("prompt_tokens", 0), token_usage.get("completion_tokens", 0)


if __name__ == "__main__":
    # Week 1 checkpoint: python src/llm.py
    from langchain_core.messages import HumanMessage

    llm = get_llm()
    print(f"Model: {settings.devbuddy_model}")
    reply = llm.invoke([HumanMessage(content="Reply with exactly: pong")])
    prompt_tokens, completion_tokens = usage_of(reply)
    print(f"Reply: {reply.content.strip()}")
    print(
        f"Tokens: {prompt_tokens} in / {completion_tokens} out  "
        f"Cost: ${settings.cost_of(prompt_tokens, completion_tokens):.6f}"
    )
