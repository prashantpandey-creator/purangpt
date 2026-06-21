"""retrieval_qc.collect — LIVE query collection against the real search stack.

This is the I/O half (runs where the DB is reachable: backend container / server).
It drives a battery of diverse queries through BOTH retrieval paths and emits a
JSON payload that `check.py`/`analyze.py` consume. Kept separate from the pure
analyzer so the decision logic stays DB-free and fixture-testable.

Run inside the backend container:
  python -m tools.retrieval_qc.collect > /tmp/retrieval_run.json
Then analyze (anywhere):
  venv/bin/python -m tools.retrieval_qc.check --payload /tmp/retrieval_run.json --json

It collects:
  - hybrid_search results per query (with fts_hit per result)
  - GRETIL search_sanskrit results per query (the alphabetical path)
  - the corpus source list (name, chunks, category) for coverage/metadata/separation
  - known-item expectations
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

# Diverse, topic-spread queries — chosen to span deities, philosophy, practice,
# cosmology, ethics, so NO single text should dominate a healthy system.
QUERIES = [
    "what is dharma", "how to attain moksha", "the nature of Vishnu",
    "what is kundalini", "the story of creation", "the duties of a king",
    "what happens after death", "the power of devotion", "Shiva and meditation",
    "the four yugas", "what is karma", "how was the universe created",
    "the importance of the guru", "what is the soul", "rituals for ancestors",
    "the goddess Durga", "liberation and rebirth", "the practice of yoga",
    "sacred rivers and pilgrimage", "the cosmic egg",
]

# Known-item recall: (query → a source that SHOULD appear in top-k).
EXPECTATIONS = [
    {"query": "the practice of yoga", "expect_source_contains": "Yoga", "top_k": 8},
    {"query": "the goddess Durga", "expect_source_contains": "Markandeya", "top_k": 8},
    {"query": "the nature of Vishnu", "expect_source_contains": "Vishnu", "top_k": 8},
]


def _source_name(r) -> str:
    if hasattr(r, "purana"):
        return r.purana
    if isinstance(r, dict):
        return r.get("purana") or r.get("text_name") or r.get("source") or "?"
    return "?"


async def _collect_hybrid(searcher, query: str):
    res = await searcher.hybrid_search(query=query, top_k=8, sharma_weighting=True)
    out = []
    for r in res:
        chunk = getattr(r, "chunk", {}) or {}
        out.append({
            "source": _source_name(r),
            "score": round(float(getattr(r, "score", 0.0)), 4),
            "rank": getattr(r, "rank", 0),
            "category": (chunk.get("category") if isinstance(chunk, dict) else None),
            "id": getattr(r, "id", None),
            # fts_hit unknown at this layer (SQL fuses internally) — left absent.
        })
    return {"query": query, "kind": "hybrid", "results": out}


def _collect_gretil(search_sanskrit_fn, query: str):
    # The GRETIL path is the alphabetical one. We probe it with the raw query.
    rows = search_sanskrit_fn(query, max_results=8)
    out = [{
        "source": row.get("text_name") or row.get("text_id") or "?",
        "score": None,
        "rank": i,
        "fts_hit": True,  # gretil is keyword-match by construction
    } for i, row in enumerate(rows)]
    return {"query": query, "kind": "gretil", "results": out}


def _collect_corpus(conn) -> dict:
    """Pull the corpus source list (name, chunks, category) from pgvector."""
    cur = conn.cursor()
    cur.execute("""
        SELECT metadata->>'purana' AS name,
               count(*) AS chunks,
               (array_agg(metadata->>'category'))[1] AS category
        FROM purana_verses
        GROUP BY metadata->>'purana'
        ORDER BY count(*) DESC
    """)
    sources = [{"name": r[0] or "?", "chunks": int(r[1]), "category": r[2]}
               for r in cur.fetchall()]
    cur.close()
    return {"sources": sources}


async def main() -> int:
    # Import the live stack lazily so the pure analyzer never needs these.
    sys.path.insert(0, "/app")
    from indexer.search import HybridSearcher

    payload = {"queries": [], "expectations": EXPECTATIONS}

    searcher = HybridSearcher()
    await searcher.initialize()

    for q in QUERIES:
        payload["queries"].append(await _collect_hybrid(searcher, q))

    # GRETIL path (optional — only if backend exposes it & corpus is loaded).
    try:
        from backend.main import search_sanskrit, state  # noqa
        if getattr(state, "gretil_corpus", None):
            for q in QUERIES:
                payload["queries"].append(_collect_gretil(search_sanskrit, q))
    except Exception as e:
        payload["gretil_skipped"] = str(e)

    # Corpus source list for coverage / metadata / separation checks.
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("VECTOR_DB_URL"), connect_timeout=5)
        payload["corpus"] = _collect_corpus(conn)
        conn.close()
    except Exception as e:
        payload["corpus_skipped"] = str(e)

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
