"""
PuranGPT — RAG Query Engine
Orchestrates hybrid search + LLM generation for Puranic Q&A.
Supports both Ollama (local) and Groq API (cloud) with streaming SSE.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import AsyncGenerator, Any, Optional

from dotenv import load_dotenv

from indexer.search import HybridSearcher, SearchResult
from engine.prompts import get_prompt, format_context, FIND_INSTANCES_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)


# ── LLM Factory ───────────────────────────────────────────────────────────

def _make_ollama_llm(model: str, base_url: str):
    """Create an Ollama LLM client."""
    try:
        from llama_index.llms.ollama import Ollama
        return Ollama(
            model=model,
            base_url=base_url,
            request_timeout=120.0,
            context_window=8192,
        )
    except ImportError:
        logger.error("llama-index-llms-ollama not installed. Run: pip install llama-index-llms-ollama")
        raise

def _make_openai_llm(model: str, api_key: str, base_url: str):
    """Create an OpenAI-compatible LLM client (works with Groq, Together, etc.)."""
    try:
        from llama_index.llms.openai import OpenAI
        return OpenAI(
            model=model,
            api_key=api_key,
            api_base=base_url,
            max_tokens=4096,
        )
    except ImportError:
        logger.error("llama-index-llms-openai not installed. Run: pip install llama-index-llms-openai")
        raise


# ── Streaming helper (raw HTTP) ────────────────────────────────────────────

async def _stream_ollama(prompt: str, model: str, base_url: str) -> AsyncGenerator[str, None]:
    """Low-level Ollama streaming via aiohttp (avoids llama-index overhead)."""
    import aiohttp, json
    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model":  model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.3,  # Low temp = more factual
            "top_p": 0.9,
            "num_ctx": 8192,
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if token := data.get("response", ""):
                        yield token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue


async def _stream_groq(prompt: str, model: str, api_key: str) -> AsyncGenerator[str, None]:
    """Stream from Groq API using OpenAI-compatible endpoint."""
    import aiohttp, json
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model":  model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        token = data["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

async def _stream_deepseek(prompt: str, model: str, api_key: str) -> AsyncGenerator[str, None]:
    """Stream from DeepSeek API using OpenAI-compatible endpoint."""
    import aiohttp, json
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model":  model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        token = data["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue



# ── Query Engine ───────────────────────────────────────────────────────────

class PuranGPTEngine:
    """
    Main RAG query engine for PuranGPT.

    Workflow:
    1. Run hybrid search (semantic + BM25) to find relevant passages
    2. Format passages as context
    3. Build prompt (mode-specific)
    4. Stream LLM response token by token
    5. Yield SSE-compatible events: {type: 'token'} and {type: 'sources'}
    """

    def __init__(
        self,
        searcher:      HybridSearcher,
        llm_provider:  str = "auto",   # "ollama" | "groq" | "deepseek" | "auto"
        ollama_model:  str = "qwen2.5:7b",
        ollama_url:    str = "http://localhost:11434",
        groq_api_key:  str = "",
        groq_model:    str = "llama-3.3-70b-versatile",
        deepseek_api_key: str = "",
        deepseek_model: str = "deepseek-chat",
    ) -> None:
        self.searcher      = searcher
        self.ollama_model  = ollama_model
        self.ollama_url    = ollama_url.rstrip("/")
        self.groq_api_key  = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.groq_model    = groq_model
        self.deepseek_api_key = deepseek_api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_model = deepseek_model

        # Auto-detect provider
        if llm_provider == "auto":
            self.provider = self._detect_provider()
        else:
            self.provider = llm_provider

        logger.info("PuranGPTEngine initialized with provider=%s", self.provider)

    def _detect_provider(self) -> str:
        """Auto-detect: try DeepSeek, then Groq, then Ollama."""
        if self.deepseek_api_key:
            logger.info("Using DeepSeek API (key found)")
            return "deepseek"

        if self.groq_api_key:
            logger.info("Using Groq API (key found)")
            return "groq"

        import urllib.request
        try:
            urllib.request.urlopen(f"{self.ollama_url}/api/tags", timeout=3)
            logger.info("Ollama detected at %s", self.ollama_url)
            return "ollama"
        except Exception:
            logger.info("Ollama not available")

        logger.warning("No LLM provider available. Set DEEPSEEK_API_KEY, GROQ_API_KEY, or start Ollama.")
        return "none"

    @property
    def model_name(self) -> str:
        if self.provider == "ollama":
            return self.ollama_model
        elif self.provider == "groq":
            return self.groq_model
        elif self.provider == "deepseek":
            return self.deepseek_model
        return "none"

    async def query(
        self,
        question: str,
        mode:     str                   = "scholar",
        filters:  dict[str, Any] | None = None,
        top_k:    int                   = 10,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Stream a response to a Puranic question.

        Yields dicts:
          {"type": "sources",  "sources": [...]}      — emitted first
          {"type": "token",    "content": "..."}      — streamed tokens
          {"type": "done"}                             — end signal
          {"type": "error",    "message": "..."}      — on failure
        """
        # 1. Hybrid search
        try:
            results = self.searcher.hybrid_search(
                query=question, top_k=top_k, filters=filters
            )
        except Exception as e:
            logger.error("Search failed: %s", e, exc_info=True)
            yield {"type": "error", "message": f"Search error: {e}"}
            return

        # 2. Emit sources immediately (frontend shows them while LLM thinks)
        sources = [r.to_dict() for r in results]
        yield {"type": "sources", "sources": sources}

        # 3. Build prompt
        context    = format_context(results)
        prompt_tpl = get_prompt(mode)
        prompt     = prompt_tpl.format(context=context, question=question)

        # 4. Stream LLM response
        if self.provider == "none":
            yield {"type": "error", "message": "No LLM provider configured. Start Ollama or set GROQ_API_KEY."}
            return

        try:
            async for token in self._stream(prompt):
                yield {"type": "token", "content": token}
        except Exception as e:
            logger.error("LLM streaming error: %s", e, exc_info=True)
            yield {"type": "error", "message": f"LLM error: {e}"}
            return

        yield {"type": "done"}

    async def query_sync(
        self,
        question: str,
        mode:     str                   = "scholar",
        filters:  dict[str, Any] | None = None,
        top_k:    int                   = 10,
    ) -> dict[str, Any]:
        """Non-streaming version: collects full response and returns it."""
        answer_parts: list[str] = []
        sources: list[dict] = []

        async for event in self.query(question, mode=mode, filters=filters, top_k=top_k):
            if event["type"] == "sources":
                sources = event["sources"]
            elif event["type"] == "token":
                answer_parts.append(event["content"])

        return {
            "answer":  "".join(answer_parts),
            "sources": sources,
            "mode":    mode,
        }

    async def find_instances(
        self,
        topic:     str,
        category:  str | None = None,
        max_results: int       = 100,
    ) -> dict[str, Any]:
        """
        Find ALL instances of a topic across all indexed texts.
        Returns grouped results by Purana.
        """
        all_results = self.searcher.find_all_instances(
            query=topic, category=category, max_results=max_results
        )

        # Group by Purana
        grouped: dict[str, list[dict]] = {}
        for result in all_results:
            key = result.purana
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(result.to_dict())

        return {
            "topic":     topic,
            "total":     len(all_results),
            "instances": [r.to_dict() for r in all_results],
            "grouped":   grouped,
        }

    async def _stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Route to the correct LLM streaming backend."""
        if self.provider == "ollama":
            async for token in _stream_ollama(prompt, self.ollama_model, self.ollama_url):
                yield token
        elif self.provider == "groq":
            async for token in _stream_groq(prompt, self.groq_model, self.groq_api_key):
                yield token
        elif self.provider == "deepseek":
            async for token in _stream_deepseek(prompt, self.deepseek_model, self.deepseek_api_key):
                yield token
        else:
            raise RuntimeError(f"Unknown provider: {self.provider}")
