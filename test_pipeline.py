#!/usr/bin/env python3
"""
PuranGPT — end-to-end chat pipeline smoke test.

Tests every stage in order; stops at first critical failure with a clear error.
Run from the repo root with a populated .env (DB url + LLM keys) present:

    venv/bin/python test_pipeline.py               # all stages, all modes
    venv/bin/python test_pipeline.py --stage db    # single stage
    venv/bin/python test_pipeline.py --api         # hit live HTTP server instead

Stages:
    db       — Postgres connection + purana_verses table readable
    search   — pgvector hybrid_search RPC returns results
    embed    — sentence-transformers encode works, correct dim (384)
    llm      — active LLM provider streams tokens for a minimal prompt
    chat     — full /api/chat SSE round-trip (needs server running or --api)
    gretil   — GRETIL corpus is on disk and text is loadable
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ── Bootstrap ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

BOLD = "\033[1m"
RED  = "\033[31m"
GRN  = "\033[32m"
YEL  = "\033[33m"
RST  = "\033[0m"

_passed = _failed = _skipped = 0

def ok(label: str, detail: str = ""):
    global _passed
    _passed += 1
    print(f"  {GRN}✓{RST} {label}" + (f"  {detail}" if detail else ""))

def fail(label: str, detail: str = "", fatal: bool = True):
    global _failed
    _failed += 1
    print(f"  {RED}✗{RST} {label}" + (f"\n    {RED}{detail}{RST}" if detail else ""))
    if fatal:
        summary()
        sys.exit(1)

def skip(label: str, reason: str):
    global _skipped
    _skipped += 1
    print(f"  {YEL}~{RST} {label}  ({reason})")

def header(title: str):
    print(f"\n{BOLD}── {title} {'─' * (50 - len(title))}{RST}")

def summary():
    total = _passed + _failed + _skipped
    color = GRN if _failed == 0 else RED
    print(f"\n{color}{BOLD}Results: {_passed}/{total} passed, {_failed} failed, {_skipped} skipped{RST}\n")


# ── Stage: DB ────────────────────────────────────────────────────────────────
def stage_db():
    header("DB — Postgres connectivity")
    from backend.db_client import get_db_conn

    conn = get_db_conn()
    if not conn:
        fail("get_db_conn()", "VECTOR_DB_URL not set or unreachable")

    try:
        with conn.cursor() as cur:
            # 1. basic liveness
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
            ok("SELECT 1")

            # 2. pgvector extension
            cur.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
            if cur.fetchone():
                ok("pgvector extension present")
            else:
                fail("pgvector extension", "extension 'vector' not found — run CREATE EXTENSION vector", fatal=False)

            # 3. purana_verses table
            cur.execute("SELECT COUNT(*) FROM purana_verses")
            count = cur.fetchone()[0]
            if count > 0:
                ok("purana_verses", f"{count:,} rows")
            else:
                fail("purana_verses", "table exists but has 0 rows — index not built", fatal=False)

            # 4. hybrid_search function exists
            cur.execute("""
                SELECT proname FROM pg_proc
                WHERE proname = 'hybrid_search'
                LIMIT 1
            """)
            if cur.fetchone():
                ok("hybrid_search() function exists")
            else:
                fail("hybrid_search() function", "not found — run schema.sql migrations", fatal=False)

    except Exception as e:
        fail("DB query", str(e))
    finally:
        conn.close()


# ── Stage: EMBED ─────────────────────────────────────────────────────────────
def stage_embed():
    header("EMBED — sentence-transformers model load + encode")
    try:
        from sentence_transformers import SentenceTransformer
        t0 = time.time()
        model = SentenceTransformer("intfloat/multilingual-e5-small")
        ok("model loaded", f"{time.time()-t0:.1f}s")
    except Exception as e:
        fail("SentenceTransformer load", str(e))

    try:
        vec = model.encode("query: What is dharma?").tolist()
        dim = len(vec)
        if dim == 384:
            ok("encode() → 384-dim vector", f"sample[0]={vec[0]:.4f}")
        else:
            fail("encode() dimension", f"got {dim}, expected 384 — DB was indexed with e5-small (384-dim)")
    except Exception as e:
        fail("encode()", str(e))


# ── Stage: SEARCH ────────────────────────────────────────────────────────────
async def stage_search():
    header("SEARCH — pgvector hybrid search")
    try:
        from indexer.search import HybridSearcher
        searcher = HybridSearcher()
        await searcher.initialize()
        ok("HybridSearcher initialized")
    except Exception as e:
        fail("HybridSearcher.initialize()", str(e))

    try:
        t0 = time.time()
        results = await searcher.hybrid_search("What is dharma?", top_k=5)
        elapsed = time.time() - t0
        if results:
            top = results[0]
            ok(f"hybrid_search → {len(results)} results", f"{elapsed:.2f}s — top: {top.purana!r} score={top.score:.3f}")
            for i, r in enumerate(results[:3]):
                print(f"     [{i+1}] {r.reference}  score={r.score:.3f}  lang={r.language}")
        else:
            fail("hybrid_search", "returned 0 results — check pgvector index", fatal=False)
    except Exception as e:
        fail("hybrid_search()", str(e))


# ── Stage: LLM ───────────────────────────────────────────────────────────────
async def stage_llm():
    header("LLM — provider validation + streaming")
    import aiohttp
    from backend.main import _validate_llm_providers, stream_llm, state, AppState

    # bootstrap state for the test
    if not state.http_client:
        state.http_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10),
        )

    try:
        await _validate_llm_providers()
        if state.active_provider in ("none", "unknown"):
            fail("provider validation", "no working LLM provider — check API keys in .env")
        ok("active provider", f"{state.active_provider} / {state.active_model}")
    except Exception as e:
        fail("_validate_llm_providers()", str(e))

    # minimal stream test
    messages = [{"role": "user", "content": "Reply with exactly: pong"}]
    tokens = []
    t0 = time.time()
    try:
        async for item in stream_llm(messages, temperature=0.0, max_retries=2):
            if isinstance(item, str):
                tokens.append(item)
            elif isinstance(item, dict) and item.get("type") == "error":
                fail("stream_llm token", item.get("message", "unknown error"))
        full = "".join(tokens)
        elapsed = time.time() - t0
        if full.strip():
            ok("stream_llm", f"{elapsed:.2f}s — {len(full)} chars — {full[:80]!r}")
        else:
            fail("stream_llm", "returned empty response", fatal=False)
    except Exception as e:
        fail("stream_llm()", str(e))
    finally:
        if state.http_client:
            await state.http_client.close()
            state.http_client = None


# ── Stage: GRETIL ────────────────────────────────────────────────────────────
def stage_gretil():
    header("GRETIL — Sanskrit corpus on disk")
    from backend.main import GRETIL_DIR, load_gretil_corpus, state

    if not GRETIL_DIR.exists():
        skip("GRETIL directory", f"{GRETIL_DIR} not found — fetch with data_pipeline/")
        return

    txt_files = list(GRETIL_DIR.glob("*.txt"))
    if not txt_files:
        skip("GRETIL .txt files", "directory exists but is empty")
        return

    ok("GRETIL directory exists", f"{len(txt_files)} .txt files")

    try:
        load_gretil_corpus()
        total_chars = sum(len(v) for v in state.gretil_corpus.values())
        ok("load_gretil_corpus()", f"{len(state.gretil_corpus)} texts, {total_chars:,} chars")
    except Exception as e:
        fail("load_gretil_corpus()", str(e), fatal=False)


# ── Stage: CHAT (HTTP SSE round-trip) ────────────────────────────────────────
async def stage_chat(base_url: str):
    header(f"CHAT — SSE /api/chat round-trip against {base_url}")
    import aiohttp

    test_cases = [
        ("research mode", {"query": "What does the Bhagavata Purana say about dharma?", "mode": "research", "session_id": "test-research", "top_k": 3}),
        ("guide mode",    {"query": "How should one deal with grief?",                   "mode": "guide",    "session_id": "test-guide",    "top_k": 3}),
    ]

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as sess:
        # Check status first
        try:
            async with sess.get(f"{base_url}/api/status") as r:
                data = await r.json()
                status_ok = data.get("status") == "ok"
                color = GRN if status_ok else YEL
                print(f"  {color}ℹ{RST}  /api/status: status={data.get('status')} provider={data.get('llm_provider')} model={data.get('model')} index_ready={data.get('index_ready')} verses={data.get('total_verses',0):,} gretil={data.get('gretil_texts',0)} texts")
        except Exception as e:
            fail("/api/status", str(e))

        # Check modes endpoint matches code
        try:
            async with sess.get(f"{base_url}/api/modes") as r:
                modes_data = await r.json()
                modes = [m["id"] for m in modes_data.get("modes", [])]
                ok("/api/modes", f"→ {modes}")
        except Exception as e:
            fail("/api/modes", str(e), fatal=False)

        # SSE chat tests
        for label, payload in test_cases:
            print(f"\n  {BOLD}► {label}{RST}")
            t0 = time.time()
            event_counts = {"sources": 0, "token": 0, "reasoning": 0, "done": 0, "error": 0}
            sources = []
            tokens = []
            grounding = None
            try:
                async with sess.post(
                    f"{base_url}/api/chat",
                    json=payload,
                    headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        fail(f"/api/chat {label}", f"HTTP {resp.status}: {body[:200]}", fatal=False)
                        continue

                    buf = ""
                    async for raw in resp.content:
                        buf += raw.decode("utf-8")
                        while "\n\n" in buf:
                            frame, buf = buf.split("\n\n", 1)
                            for line in frame.split("\n"):
                                if not line.startswith("data:"):
                                    continue
                                payload_str = line[5:].strip()
                                if not payload_str or payload_str == "[DONE]":
                                    continue
                                try:
                                    evt = json.loads(payload_str)
                                    t = evt.get("type", "")
                                    event_counts[t] = event_counts.get(t, 0) + 1
                                    if t == "sources":
                                        sources = evt.get("sources", [])
                                    elif t == "token":
                                        tokens.append(evt.get("content", ""))
                                    elif t == "done":
                                        grounding = evt.get("grounding_quality")
                                except json.JSONDecodeError:
                                    pass

                elapsed = time.time() - t0
                answer = "".join(tokens)

                # Assertions
                if event_counts.get("error", 0):
                    fail(f"{label}: no error events", f"got error event — check logs", fatal=False)
                elif event_counts.get("done", 0) == 0:
                    fail(f"{label}: done event", "stream ended without done event", fatal=False)
                elif not answer.strip():
                    fail(f"{label}: non-empty answer", "token stream was empty", fatal=False)
                else:
                    ok(f"{label}", f"{elapsed:.1f}s  tokens={event_counts['token']}  sources={len(sources)}  grounding={grounding}")
                    if answer:
                        print(f"     answer[:120]: {answer[:120].strip()!r}")
                    if sources:
                        print(f"     top source:   {sources[0].get('text_name') or sources[0].get('purana')} — {sources[0].get('reference')}")

            except asyncio.TimeoutError:
                fail(f"{label}: timeout", "no response within 60s — is the server up?", fatal=False)
            except Exception as e:
                fail(f"{label}", str(e), fatal=False)


# ── Entry point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="PuranGPT pipeline smoke test")
    parser.add_argument("--stage", choices=["db", "embed", "search", "llm", "gretil", "chat"], help="Run only one stage")
    parser.add_argument("--api", metavar="URL", nargs="?", const="http://localhost:8000",
                        help="Base URL for HTTP /api/chat test (default: http://localhost:8000)")
    parser.add_argument("--prod", action="store_true", help="Use production server (204.168.176.229:8000)")
    args = parser.parse_args()

    base_url = "http://204.168.176.229:8000" if args.prod else (args.api or "http://localhost:8000")

    stages = [args.stage] if args.stage else ["db", "embed", "search", "llm", "gretil", "chat"]

    print(f"\n{BOLD}PuranGPT pipeline test — {time.strftime('%Y-%m-%d %H:%M:%S')}{RST}")
    print(f"Backend URL: {base_url}")

    async def run():
        for stage in stages:
            if stage == "db":
                stage_db()
            elif stage == "embed":
                stage_embed()
            elif stage == "search":
                await stage_search()
            elif stage == "llm":
                await stage_llm()
            elif stage == "gretil":
                stage_gretil()
            elif stage == "chat":
                await stage_chat(base_url)

    asyncio.run(run())
    summary()

if __name__ == "__main__":
    main()
