"""rag_vs_graph_bench — re-runnable plain-RAG vs graph-recall benchmark.

WHY this exists: studies of "does the graph beat plain RAG?" kept citing a STATIC
JSON of numbers nobody could reproduce. This turns the comparison into a tested,
re-runnable Rule-0 tool: it stands up a crude keyword-RAG FLOOR (same retrieval
SHAPE as pgvector — top-k by normalized term overlap) over the real corpus,
calls the REAL graph recall (`tools.read_pass.recall`), runs both across 5 query
classes (PASSAGE, SINGLE-FACT, SCATTERED, MULTI-HOP, CROSS-TEXT-ID), times them,
and scores who answered.

The keyword-RAG is deliberately the FLOOR — it is the baseline pgvector would
have to beat, and its SLOWNESS over 291k chunks (~7s/query) IS THE POINT (it's
the cost a real dense retriever also pays). `--quick` samples the corpus so the
test suite and smoke runs finish fast.

Scoring per class:
  • rag_correct  — did the top keyword hit come from the EXPECTED text?
  • graph_correct— did graph recall surface the EXPECTED entities AND (where the
    class demands it) the EXPECTED relationship/edge?

Run from purangpt/ repo root so `tools.read_pass.recall` + relative paths resolve.

Input contract:  run(quick, k, corpus_path, graph_path, ram_path) -> envelope
Output (data):   {classes:[{class,query,rag_ms,rag_correct,rag_top,
                            graph_ms,graph_correct,graph_seeds,verdict}],
                  summary:{rag_score,graph_score,n_classes,speedup}}
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set

# --- schema constants (asserted by tests) ------------------------------------
_DATA_KEYS = {"classes", "summary"}
_CLASS_KEYS = {"class", "query", "rag_ms", "rag_correct", "rag_top",
               "graph_ms", "graph_correct", "graph_seeds", "verdict"}
_SUMMARY_KEYS = {"rag_score", "graph_score", "n_classes", "speedup"}

_DEFAULT_CORPUS = "data/chunks/all_chunks.jsonl"
_DEFAULT_GRAPH = "tools/read_pass/out/graph_manifest.json"
_DEFAULT_RAM = "tools/read_pass/out/guruji_ram.json"

# in --quick mode, keep ~this many corpus rows (keeps tests/smoke fast).
# CRITICAL: sample by STRIDING the file, not taking the alphabetical head — the
# corpus is ordered by text (agni, amarakosha, ... bhagavata, ...), so a head
# slice silently drops whole texts (bhagavata/awk) and the RAG floor would
# "lose" only because the expected text was never in the sample. Striding keeps
# every text represented so the measurement is real, not a sampling artifact.
# (Same class of scope bug sse_contract_check/FINDINGS.md warns about.)
_QUICK_KEEP = 40_000

_WORD = re.compile(r"[A-Za-zÀ-ɏ]+")


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# --- the FLOOR: crude keyword-RAG (stand-in for pgvector) --------------------
def _terms(s: str) -> Set[str]:
    """Lowercased word tokens (len>=3) — the bag a crude retriever matches on."""
    return {w.lower() for w in _WORD.findall(s) if len(w) >= 3}


def keyword_rag(query: str, corpus: List[Dict[str, Any]], k: int = 5
                ) -> List[Dict[str, Any]]:
    """Top-k chunks by NORMALIZED query-term overlap — the pgvector floor stand-in.

    Same retrieval SHAPE as a dense retriever (rank chunks by relevance to the
    query, take top-k) but with the crudest possible relevance signal so it's the
    deterministic FLOOR. Score = |query_terms ∩ chunk_terms| / |query_terms|, in
    [0,1]. Returns [{id, purana, score, text_code}] best-first.
    """
    q = _terms(query)
    if not q:
        return []
    scored: List[Dict[str, Any]] = []
    for ch in corpus:
        ct = _terms(ch.get("text", ""))
        overlap = len(q & ct)
        if overlap == 0:
            continue
        scored.append({
            "id": ch.get("id", ""),
            "purana": ch.get("purana", ""),
            "score": overlap / len(q),
            "text_code": _text_code(ch.get("id", "")),
        })
    scored.sort(key=lambda h: h["score"], reverse=True)
    return scored[:k]


def _count_lines(path: str) -> int:
    """Cheap line count so --quick can stride evenly across the whole corpus."""
    n = 0
    with open(path, "rb") as f:
        for _ in f:
            n += 1
    return n


def _text_code(chunk_id: str) -> str:
    """The text-namespace prefix of a chunk id ('bhagavata-1-1' -> 'bhagavata')."""
    # ids are '<code>-<chapter>-<verse>'; strip the trailing two numeric-ish parts
    return chunk_id.rsplit("-", 2)[0] if chunk_id.count("-") >= 2 else chunk_id


def verdict_for(rag_correct: bool, graph_correct: bool) -> str:
    """Per-class label from the two booleans — a total function (tests pin it)."""
    if rag_correct and graph_correct:
        return "both"
    if graph_correct:
        return "graph_only"
    if rag_correct:
        return "rag_only"
    return "neither"


# --- the 5 query classes + their expected-answer SIGNATURES -------------------
# Each signature is hardcoded so the bench is reproducible and self-checking.
#   expect_text   — text code the top RAG hit should come from
#   expect_entities — graph seeds/entities that MUST appear (normalized contains)
#   expect_edge   — (rel-substring) one relationship the graph must surface
#                   (None when the class doesn't require an edge, e.g. PASSAGE)
_QUERIES: List[Dict[str, Any]] = [
    {
        "class": "PASSAGE",
        "query": "describe the churning of the ocean of milk for amrita",
        "expect_text": "brahma",
        "expect_entities": ["samudra", "amrita"],
        "expect_edge": None,
    },
    {
        "class": "SINGLE-FACT",
        "query": "who is the brother of Krishna",
        "expect_text": "bhagavata",
        "expect_entities": ["krishna"],
        "expect_edge": "brother",
    },
    {
        "class": "SCATTERED",
        "query": "Krishna and Arjuna on the battlefield of Kurukshetra",
        "expect_text": "bhagavata",
        "expect_entities": ["krishna", "arjuna"],
        "expect_edge": None,
    },
    {
        "class": "MULTI-HOP",
        "query": "how is Krishna related to Vishnu and the avatars",
        "expect_text": "bhagavata",
        "expect_entities": ["krishna", "vishnu"],
        "expect_edge": "avatar",
    },
    {
        "class": "CROSS-TEXT-ID",
        "query": "Babaji and Lahiri Mahasaya and the Kriya Yoga lineage",
        "expect_text": "awk",  # The Awakener; falls back to any non-purana text
        "expect_entities": ["babaji", "lahiri"],
        "expect_edge": "guru",
    },
]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _graph_correct(rec_data: Dict[str, Any], spec: Dict[str, Any]) -> bool:
    """Did recall surface the expected entities AND (if required) the edge?"""
    if not rec_data:
        return False
    names = {_norm(e.get("name", "")) for e in rec_data.get("entities", [])}
    # entity check: every expected entity must be a substring of some recalled name
    for want in spec["expect_entities"]:
        if not any(_norm(want) in n for n in names):
            return False
    # edge check (only when the class demands a relationship)
    want_edge = spec["expect_edge"]
    if want_edge:
        rels = rec_data.get("relationships", [])
        if not any(want_edge.lower() in (r.get("rel", "") or "").lower() for r in rels):
            return False
    return True


def _rag_correct(hits: List[Dict[str, Any]], spec: Dict[str, Any]) -> bool:
    """Did the top RAG hit come from the expected text namespace?

    CROSS-TEXT-ID expects the lineage text ('awk'); if that text isn't in the
    sampled corpus the floor simply can't answer it — which is exactly the point
    being measured (plain RAG can't fuse identities across texts).
    """
    if not hits:
        return False
    return hits[0]["text_code"].startswith(spec["expect_text"])


def run(quick: bool = False, k: int = 5,
        corpus_path: str = _DEFAULT_CORPUS,
        graph_path: str = _DEFAULT_GRAPH,
        ram_path: str = _DEFAULT_RAM) -> Dict[str, Any]:
    """Run both retrievers across the 5 classes and return the bench envelope.

    Fail-clean (success=False) when the graph manifest or corpus is absent —
    never crash. The graph dependency is checked up front so we don't burn time
    scanning 291k chunks only to discover the graph is missing.
    """
    metadata = {"quick": quick, "k": k,
                "corpus_path": corpus_path, "graph_path": graph_path}

    if not os.path.exists(graph_path) or not os.path.exists(ram_path):
        return _envelope(False, None, metadata, [{
            "code": "graph_missing",
            "message": (f"graph manifest/ram not found "
                        f"(graph={graph_path}, ram={ram_path}); "
                        f"run tools.graph_rebuild first"),
        }])
    if not os.path.exists(corpus_path):
        return _envelope(False, None, metadata, [{
            "code": "corpus_missing",
            "message": f"corpus not found: {corpus_path}",
        }])

    # import the REAL graph recall (run from repo root so the package resolves)
    try:
        from tools.read_pass.recall import Memory, recall
    except Exception as e:  # pragma: no cover - import wiring
        return _envelope(False, None, metadata, [{
            "code": "recall_import_failed", "message": str(e)[:200]}])

    try:
        memory = Memory.load(graph_path, ram_path)
    except Exception as e:
        return _envelope(False, None, metadata, [{
            "code": "graph_load_failed", "message": str(e)[:200]}])

    # load corpus. In --quick mode, STRIDE the file (every Nth row) so every
    # text is represented — never an alphabetical head slice (see _QUICK_KEEP).
    stride = 1
    if quick:
        total = _count_lines(corpus_path)
        stride = max(1, total // _QUICK_KEEP)
        metadata["quick_stride"] = stride
    corpus: List[Dict[str, Any]] = []
    with open(corpus_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i % stride != 0:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                corpus.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    metadata["corpus_rows"] = len(corpus)
    metadata["graph_entities"] = len(memory.entities)
    metadata["graph_edges"] = len(memory.edges)

    classes: List[Dict[str, Any]] = []
    rag_total_ms = 0.0
    graph_total_ms = 0.0

    for spec in _QUERIES:
        # --- plain RAG (the floor) ---
        t0 = time.perf_counter()
        hits = keyword_rag(spec["query"], corpus, k=k)
        rag_ms = (time.perf_counter() - t0) * 1000.0
        rag_ok = _rag_correct(hits, spec)

        # --- graph recall (the real thing) ---
        t0 = time.perf_counter()
        rec = recall(spec["query"], memory)
        graph_ms = (time.perf_counter() - t0) * 1000.0
        rec_data = rec.get("data") if rec.get("success") else None
        graph_ok = _graph_correct(rec_data or {}, spec)
        graph_seeds = (
            [e["name"] for e in rec_data.get("entities", []) if e.get("is_seed")]
            if rec_data else []
        )

        rag_total_ms += rag_ms
        graph_total_ms += graph_ms

        classes.append({
            "class": spec["class"],
            "query": spec["query"],
            "rag_ms": round(rag_ms, 2),
            "rag_correct": rag_ok,
            "rag_top": (f'{hits[0]["text_code"]} ({hits[0]["score"]:.2f})'
                        if hits else None),
            "graph_ms": round(graph_ms, 2),
            "graph_correct": graph_ok,
            "graph_seeds": graph_seeds[:6],
            "verdict": verdict_for(rag_ok, graph_ok),
        })

    rag_score = sum(1 for c in classes if c["rag_correct"])
    graph_score = sum(1 for c in classes if c["graph_correct"])
    speedup = round(rag_total_ms / graph_total_ms, 1) if graph_total_ms else None

    data = {
        "classes": classes,
        "summary": {
            "rag_score": rag_score,
            "graph_score": graph_score,
            "n_classes": len(classes),
            "speedup": speedup,  # how many x faster graph recall is than the RAG floor
            "rag_total_ms": round(rag_total_ms, 1),
            "graph_total_ms": round(graph_total_ms, 1),
        },
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    quick = "--quick" in argv
    k = 5
    if "--k" in argv:
        k = int(argv[argv.index("--k") + 1])

    env = run(quick=quick, k=k)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"corpus_rows={env['metadata'].get('corpus_rows')} "
              f"entities={env['metadata'].get('graph_entities')} "
              f"(quick={quick})\n")
        hdr = f"{'CLASS':<14} {'RAG':>5} {'ms':>8}  {'GRAPH':>5} {'ms':>8}  VERDICT"
        print(hdr)
        print("-" * len(hdr))
        for c in d["classes"]:
            print(f"{c['class']:<14} "
                  f"{'Y' if c['rag_correct'] else '.':>5} {c['rag_ms']:>8.1f}  "
                  f"{'Y' if c['graph_correct'] else '.':>5} {c['graph_ms']:>8.1f}  "
                  f"{c['verdict']}")
        s = d["summary"]
        print(f"\nRAG {s['rag_score']}/{s['n_classes']}   "
              f"GRAPH {s['graph_score']}/{s['n_classes']}   "
              f"graph is ~{s['speedup']}x faster than the RAG floor")

    if not env["success"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
