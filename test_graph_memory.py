"""Tests-first for backend.graph_memory — the graph→chat context block.

The corpus RAG retrieves verses (facts). graph_memory adds the WISDOM layer:
the relational truth RAG can't reach (Krishna's brother; Babaji→Lahiri lineage),
proven graph_only 4/5 vs RAG-floor 0/5 by tools/rag_vs_graph_bench.

Architecture (MEMORY_ARCHITECTURE.md): facts=RAG, wisdom=graph, never mixed. This
block is ADDITIVE and fail-graceful — flag-off / missing file / empty recall / any
error → "" and the chat behaves byte-identical to today. Flag-gated OFF by default.

Real graph file is the fixture (Rule 0 precond A: test against real captured output).
Run from repo root:  venv/bin/python test_graph_memory.py   (exit 0)
"""
from __future__ import annotations

import os
import sys

from backend import graph_memory as gm


def _reset():
    gm._memory = None
    gm._load_failed = False
    gm._GRAPH_PATH = "tools/read_pass/out/graph_manifest.json"
    gm._RAM_PATH = "tools/read_pass/out/guruji_ram.json"


def test_disabled_returns_empty_string():
    _reset()
    # flag OFF must be byte-identical to no-graph behaviour
    assert gm.build_graph_context("who is the brother of Krishna", enabled=False) == ""


def test_flag_default_is_off():
    # with no env set, the gate is OFF — ships dark
    old = os.environ.pop("GRAPH_MEMORY_ENABLED", None)
    try:
        _reset()
        assert gm.build_graph_context("Krishna", enabled=None) == ""
    finally:
        if old is not None:
            os.environ["GRAPH_MEMORY_ENABLED"] = old


def test_empty_query_returns_empty():
    _reset()
    assert gm.build_graph_context("", enabled=True) == ""
    assert gm.build_graph_context("   ", enabled=True) == ""


def test_enabled_surfaces_relational_truth_rag_cannot():
    # THE POINT: enabled + a cross-text-identity query → the block names the
    # relationship RAG floor scored 0/5 on. Real graph is the fixture.
    _reset()
    block = gm.build_graph_context("Babaji and Lahiri Mahasaya and the Kriya lineage",
                                   enabled=True)
    assert block, "enabled recall on a known entity must return a non-empty block"
    low = block.lower()
    assert "babaji" in low and "lahiri" in low, f"relational truth missing: {block[:200]}"


def test_never_raises_on_missing_graph_file():
    # fail-graceful: a bad path must yield "" not an exception (never break a chat turn)
    _reset()
    gm._memory = None
    gm._load_failed = False
    gm._GRAPH_PATH = "tools/read_pass/out/DOES_NOT_EXIST.json"
    try:
        out = gm.build_graph_context("Krishna", enabled=True)
    except Exception as e:  # noqa
        assert False, f"must not raise into the request path, got {type(e).__name__}: {e}"
    assert out == ""
    _reset()


def test_nonsense_query_returns_empty():
    # a cue that matches no entity → empty block, not a crash or garbage
    _reset()
    out = gm.build_graph_context("zzqx wibble fnord nonsense", enabled=True)
    assert out == "", f"nonsense should recall nothing, got: {out[:120]}"


def test_lineage_chain_assembles_full_sharma_spine():
    # THE FIX: recall is one-hop, so the multi-hop guru spine drifted to Yogananda.
    # _lineage_chain walks the clean guru_of edges to assemble the REAL transmission
    # chain through any seed. Babaji must resolve all the way to Shailendra Sharma.
    from tools.read_pass import recall
    _reset()
    mem = recall.Memory.load(gm._GRAPH_PATH, gm._RAM_PATH)
    chain = gm._lineage_chain(mem, ["Babaji"])
    joined = " → ".join(chain)
    for link in ["Babaji", "Lahiri Mahasaya", "Tinkori Lahiri",
                 "Satyacharan Lahiri", "Shailendra Sharma"]:
        assert link in joined, f"spine missing {link!r}: {joined}"
    # order: guru precedes disciple
    assert joined.index("Babaji") < joined.index("Lahiri Mahasaya") < \
           joined.index("Tinkori Lahiri") < joined.index("Satyacharan Lahiri") < \
           joined.index("Shailendra Sharma"), f"out of order: {joined}"


def test_lineage_chain_empty_when_no_guru_seed():
    from tools.read_pass import recall
    _reset()
    mem = recall.Memory.load(gm._GRAPH_PATH, gm._RAM_PATH)
    assert gm._lineage_chain(mem, ["zzqx nonsense entity"]) == []


def test_build_context_surfaces_the_spine_for_lineage_query():
    # end-to-end: the lineage cue's block now NAMES the Sharma spine, not Yogananda
    _reset()
    block = gm.build_graph_context(
        "Who is Babaji, and how is he connected to Lahiri Mahasaya and the Kriya lineage?",
        enabled=True)
    assert "Shailendra Sharma" in block, f"spine not surfaced: {block[:300]}"
    assert "Satyacharan" in block and "Tinkori" in block, f"chain incomplete: {block[:300]}"


def test_singleton_loads_once_not_per_call():
    # the 8.8MB graph must load once and be cached (latency: 83ms once, not per query)
    _reset()
    gm.build_graph_context("Krishna", enabled=True)
    first = gm._memory
    assert first is not None, "memory should be populated after first enabled call"
    gm.build_graph_context("Arjuna", enabled=True)
    assert gm._memory is first, "memory must be the SAME cached object (loaded once)"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
