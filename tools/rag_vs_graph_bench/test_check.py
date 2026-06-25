"""Tests for rag_vs_graph_bench — written FIRST (Rule 0, precondition A).

Run: venv/bin/python -m tools.rag_vs_graph_bench.test_check   (from purangpt/ root)

What "works" means here:
  1. the crude keyword-RAG scorer ranks the *right* chunk first on a tiny
     DETERMINISTIC synthetic corpus (no dependence on the 291k-chunk file);
  2. `rag_correct` is true iff the top hit comes from the expected text;
  3. the per-class verdict logic maps (rag_correct, graph_correct) → label
     exactly;
  4. the envelope shape ({success,data,metadata,errors}) and the missing-graph
     failure path both hold.

These tests touch ONLY pure functions — they never read the real corpus or the
real graph, so the suite runs in well under a second.
"""
from tools.rag_vs_graph_bench.check import (
    keyword_rag, verdict_for, run, _DATA_KEYS, _SUMMARY_KEYS, _CLASS_KEYS,
)

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}

# A tiny synthetic corpus — same SHAPE as data/chunks/all_chunks.jsonl rows
# (id prefix = text code, plus text). Deterministic; the right answer is obvious.
_CORPUS = [
    {"id": "bhagavata-1-1", "purana": "Bhagavata", "text": "Krishna spoke to Arjuna on the battlefield of Kurukshetra"},
    {"id": "agni-0-1", "purana": "Agni", "text": "rules of fire ritual and temple construction"},
    {"id": "brahma-2-3", "purana": "Brahma", "text": "the churning of the ocean of milk yielded amrita and the poison halahala"},
    {"id": "atharvaveda-9-9", "purana": "Atharvaveda", "text": "hymns and charms unrelated to any of this"},
]


def test_keyword_rag_ranks_right_chunk_first():
    """A churning-of-the-ocean query must surface the brahma chunk on top."""
    hits = keyword_rag("churning of the ocean of milk amrita", _CORPUS, k=3)
    assert hits, "expected at least one hit"
    assert hits[0]["id"] == "brahma-2-3", hits[0]
    print("ok: keyword_rag ranks right chunk first")


def test_keyword_rag_battlefield_hits_bhagavata():
    hits = keyword_rag("Krishna Arjuna battlefield", _CORPUS, k=2)
    assert hits[0]["id"].startswith("bhagavata"), hits[0]
    print("ok: keyword_rag battlefield -> bhagavata")


def test_keyword_rag_no_overlap_returns_empty_or_zero_score():
    """A query sharing no terms must not fabricate a confident hit."""
    hits = keyword_rag("xyzzy quux nothingmatches", _CORPUS, k=3)
    # either no hits, or all hits have zero overlap score
    assert all(h["score"] == 0 for h in hits) or hits == [], hits
    print("ok: keyword_rag no-overlap is honest")


def test_keyword_rag_normalizes_by_query_length():
    """Score is normalized term-overlap (0..1), not raw count."""
    hits = keyword_rag("Krishna Arjuna battlefield", _CORPUS, k=1)
    assert 0.0 < hits[0]["score"] <= 1.0, hits[0]["score"]
    print("ok: keyword_rag score normalized 0..1")


def test_verdict_logic_is_total():
    """Every (rag, graph) combination maps to a defined verdict label."""
    assert verdict_for(True, True) == "both"
    assert verdict_for(False, True) == "graph_only"
    assert verdict_for(True, False) == "rag_only"
    assert verdict_for(False, False) == "neither"
    print("ok: verdict logic total")


def test_missing_graph_fails_cleanly():
    """If the graph manifest is absent the tool returns success=false, not crash."""
    env = run(quick=True, graph_path="/nonexistent/graph_manifest.json",
              ram_path="/nonexistent/ram.json")
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] == "graph_missing", env["errors"]
    print("ok: missing graph fails cleanly")


def test_envelope_and_data_schema_on_success():
    """Full run on the REAL corpus+graph (quick mode) yields the declared schema.

    Skips gracefully if the real artifacts aren't present in this checkout (so
    the pure-logic tests above still gate); the missing-graph path is covered by
    its own test regardless.
    """
    import os
    g = "tools/read_pass/out/graph_manifest.json"
    r = "tools/read_pass/out/guruji_ram.json"
    corpus = "data/chunks/all_chunks.jsonl"
    if not (os.path.exists(g) and os.path.exists(r) and os.path.exists(corpus)):
        print("skip: real artifacts absent (pure-logic tests still gate)")
        return
    env = run(quick=True)
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True, env["errors"]
    d = env["data"]
    assert set(d.keys()) == _DATA_KEYS, d.keys()
    assert len(d["classes"]) == 5, [c["class"] for c in d["classes"]]
    for c in d["classes"]:
        assert _CLASS_KEYS <= set(c.keys()), c.keys()
        assert c["verdict"] in {"both", "graph_only", "rag_only", "neither"}
    assert _SUMMARY_KEYS <= set(d["summary"].keys()), d["summary"].keys()
    print("ok: success envelope + data schema (real artifacts)")


if __name__ == "__main__":
    test_keyword_rag_ranks_right_chunk_first()
    test_keyword_rag_battlefield_hits_bhagavata()
    test_keyword_rag_no_overlap_returns_empty_or_zero_score()
    test_keyword_rag_normalizes_by_query_length()
    test_verdict_logic_is_total()
    test_missing_graph_fails_cleanly()
    test_envelope_and_data_schema_on_success()
    print("\nALL TESTS PASSED")
