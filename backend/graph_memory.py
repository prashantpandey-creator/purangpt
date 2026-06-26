"""Graph memory — the WISDOM layer of the chat prompt (facts stay with RAG).

The corpus RAG retrieves verses — the facts, which it cannot hallucinate. This
module adds what RAG structurally cannot reach: the **relational truth** of the
graph — who relates to whom, the multi-hop chains, the cross-text identities
(Krishna's brother; the Babaji→Lahiri→Sharma Kriya spine). Proven graph_only
**4/5 vs the RAG floor's 0/5** by `tools/rag_vs_graph_bench`.

Architecture (LOCKED — `tools/read_pass/MEMORY_ARCHITECTURE.md`): **facts = RAG,
wisdom = graph, never mixed.** This is the wisdom side. The block it returns is
fed into the SAME `{context}` slot the RAG passages use (no new template slot, so
no KeyError-500 risk) — verses and relational truth, side by side.

**Safety contract — this NEVER breaks a chat turn:**
  - Flag-gated OFF by default (`GRAPH_MEMORY_ENABLED=1` to enable). Ships dark;
    flipped on deliberately, never half-wired into the live path.
  - Fail-graceful: flag-off / blank query / missing graph file / empty recall /
    ANY exception → returns `""`, and the chat behaves byte-identical to today.
  - The 8.8MB graph loads ONCE (a module singleton, ~83ms) and is reused; a failed
    load is remembered so we don't retry it every request.

The recall engine itself lives in `tools/read_pass/recall.py` (the moat). It is
imported lazily INSIDE the functions so a missing/broken moat can never stop
`backend` from importing.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("graph_memory")

# Overridable via env so the deploy can point at the image's copy of the graph.
_GRAPH_PATH = os.getenv("GRAPH_MEMORY_PATH", "tools/read_pass/out/graph_manifest.json")
_RAM_PATH = os.getenv("GRAPH_RAM_PATH", "tools/read_pass/out/guruji_ram.json")

_memory = None          # lazy singleton (recall.Memory) — load once, reuse
_load_failed = False    # remember a broken load; don't retry it every request


def _enabled(override: Optional[bool]) -> bool:
    """Flag gate. Explicit `enabled=` wins (for tests); else the env, default OFF."""
    if override is not None:
        return override
    return os.getenv("GRAPH_MEMORY_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def _get_memory():
    """Load the graph once into a module singleton. Returns None (never raises) if
    the moat/graph isn't present — caller degrades to ""."""
    global _memory, _load_failed
    if _memory is not None or _load_failed:
        return _memory
    try:
        from tools.read_pass import recall  # lazy: a missing moat must not break import
        _memory = recall.Memory.load(_GRAPH_PATH, _RAM_PATH)
        logger.info("graph_memory loaded: %d entities, %d edges, %d keys",
                    len(_memory.entities), len(_memory.edges), len(_memory.keys))
    except Exception as e:  # noqa — fail-graceful: no graph → no graph context, ever silent
        _load_failed = True
        _memory = None
        logger.warning("graph_memory load failed (%s) — graph context disabled this run",
                       type(e).__name__)
    return _memory


def build_graph_context(query: str, *, enabled: Optional[bool] = None) -> str:
    """The injectable graph block for the chat `{context}` slot, or "".

    NEVER raises into the request path. "" means "behave exactly like today".
    """
    if not _enabled(enabled):
        return ""
    if not query or not query.strip():
        return ""
    try:
        from tools.read_pass import recall
        mem = _get_memory()
        if mem is None:
            return ""
        env = recall.recall(query, mem)
        if not env.get("success"):
            return ""
        block = recall.render_context(env.get("data") or {})
        return block or ""
    except Exception as e:  # noqa — a graph hiccup must never break a chat turn
        logger.warning("build_graph_context failed (%s) — degrading to no graph context",
                       type(e).__name__)
        return ""
