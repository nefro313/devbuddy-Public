"""
DevBuddy — OpenRouter LLM Client Factory

Uses LangChain's ChatOpenAI pointed at OpenRouter.
One client. Any model. Swap by changing DEVBUDDY_MODEL in .env.
"""
from langchain_openai import ChatOpenAI
from src.config import OPENROUTER_API_KEY, OPENROUTER_BASE, DEVBUDDY_MODEL, validate


def get_llm(model: str | None = None, temperature: float = 0.0) -> ChatOpenAI:
    """
    Return a LangChain chat model pointed at OpenRouter.

    Args:
        model: OpenRouter model string. Defaults to DEVBUDDY_MODEL from .env.
        temperature: 0.0 for deterministic, higher for creative.

    Raises:
        ValueError: If OPENROUTER_API_KEY is not configured.
    """
    validate()
    return ChatOpenAI(
        model=model or DEVBUDDY_MODEL,
        base_url=OPENROUTER_BASE,
        api_key=OPENROUTER_API_KEY,
        temperature=temperature,
        default_headers={
            "HTTP-Referer": "https://github.com/your-org/devbuddy",
            "X-Title": "DevBuddy",
        },
    )
