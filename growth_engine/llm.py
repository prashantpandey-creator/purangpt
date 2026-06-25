"""LLM adapter — thin re-export of the backend's generic, key-driven LLM router.

ALL text generation in growth_engine goes through these. They are
provider-agnostic (any OpenAI-compatible key), with circuit-breaker + failover
already built in.

DO NOT add provider-named functions (stream_deepseek / stream_groq / ...) here
or anywhere. That pattern caused recurring NameError crashes — providers are
selected at runtime from whichever keys are set. See purangpt/CLAUDE.md.
"""

import aiohttp

from backend.main import (  # noqa: F401  (re-exported)
    get_providers,
    stream_llm,
    call_llm_once,
    any_llm_configured,
)
from backend import main as _backend_main

__all__ = [
    "get_providers", "stream_llm", "call_llm_once", "any_llm_configured",
    "ensure_http_client", "close_http_client",
]


async def ensure_http_client() -> None:
    """Create the shared aiohttp session used by stream_one_provider.

    The chat backend creates state.http_client in its FastAPI lifespan; when we
    run standalone (worker, scripts, tests) that startup never runs, so
    state.http_client is None and every LLM call fails with
    `'NoneType' object has no attribute 'post'`. Call this once before any
    stream_llm/call_llm_once in a non-FastAPI context. Idempotent.
    """
    if getattr(_backend_main.state, "http_client", None) is None:
        _backend_main.state.http_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=100),
        )


async def close_http_client() -> None:
    """Close the shared aiohttp session if we opened one (clean shutdown)."""
    client = getattr(_backend_main.state, "http_client", None)
    if client is not None:
        await client.close()
        _backend_main.state.http_client = None
