"""Tests for retrieval_qc — run: venv/bin/python -m tools.retrieval_qc.test_check

Tests the PURE analyzer against fixtures modeled on REAL production output
(captured 2026-06-21): GRETIL alphabetic bias (Agni/Atharvaveda/Amarakosha win
slots) and Sharma-corpus source-name fragmentation. Validates both the
bug-detecting (fail) path and the healthy (pass) path. No DB needed.
"""
from __future__ import annotations

import sys

from tools.retrieval_qc.analyze import (
    analyze,
    check_distribution,
    check_alphabetic_bias,
    check_metadata_quality,
    check_known_items,
    check_hybrid_contribution,
    check_coverage,
    check_corpus_separation,
    _spearman,
)
from tools.retrieval_qc.check import run


# ── Fixtures modeling REAL captured production behavior ──────────────────────

def _gretil_alphabetic_bias_payload():
    """GRETIL walks corpus alphabetically and stops at max_results, so earlier-
    alphabet texts are scanned first and fill slots before later ones are reached.
    Models the real symptom: a frequency GRADIENT by alphabetical position —
    A-texts appear most, Z-texts barely at all."""
    # Alphabetically ordered; earlier ones retrieved far more (the bias gradient).
    SOURCES = ["Agni Purana", "Amarakosha", "Atharvaveda", "Bhagavata Purana",
               "Brahma Purana", "Garuda Purana", "Kurma Purana", "Linga Purana",
               "Markandeya Purana", "Narada Purana", "Padma Purana", "Skanda Purana",
               "Vamana Purana", "Varaha Purana", "Vishnu Purana", "Yoga Vasistha"]
    queries = []
    for q in ["dharma", "moksha", "vishnu", "kundalini", "creation", "karma"]:
        results = []
        # Weight slots toward the front of the alphabet: source i appears with
        # probability ~ (N-i), so early letters dominate every query.
        slot = 0
        for i, src in enumerate(SOURCES):
            reps = max(0, (len(SOURCES) - i) // 4)  # 4,3,3,3,2,2,...,0
            for _ in range(reps):
                if slot >= 8:
                    break
                results.append({"source": src, "score": 1.0 - slot * 0.05,
                                "rank": slot, "fts_hit": True, "category": "mahapurana"})
                slot += 1
        queries.append({"query": q, "kind": "gretil", "results": results})
    return {"queries": queries}


def _healthy_payload():
    """A well-distributed result set across many real Purana names."""
    SOURCES = ["Skanda Purana", "Mahabharata", "Vishnu Purana (Critical Edition)",
               "Bhagavata Purana", "Ramayana (Valmiki)", "Garuda Purana",
               "Brahma Purana", "Markandeya Purana", "Linga Purana (Part 1, Ch. 1-108)",
               "Kurma Purana", "Matsya Purana (Ch. 1-176)", "Vamana Purana",
               "Narada Purana", "Padma Purana", "Agni Purana", "Yoga Vasistha"]
    queries = []
    for qi, q in enumerate(["dharma", "moksha", "vishnu", "kundalini", "creation",
                            "karma", "soul", "guru", "death", "devotion"]):
        results = [{"source": SOURCES[(qi * 3 + i) % len(SOURCES)],
                    "score": 0.9 - i * 0.05, "rank": i,
                    "fts_hit": (i % 2 == 0), "category": "mahapurana"}
                   for i in range(8)]
        queries.append({"query": q, "kind": "hybrid", "results": results})
    return {"queries": queries}


def _corpus_with_pollution():
    """Models the real DB: clean scripture names + fragmented Sharma names."""
    sources = [
        {"name": "Skanda Purana", "chunks": 55807, "category": "mahapurana"},
        {"name": "Mahabharata", "chunks": 53602, "category": "other"},
        {"name": "Agni Purana", "chunks": 2555, "category": "mahapurana"},
    ]
    for i in range(40):
        sources.append({"name": f"Shailendra Sharma Darshan — darshans20{i:04d}-2",
                        "chunks": 30, "category": "yogic-discourse"})
    return {"sources": sources}


# ── Tests ────────────────────────────────────────────────────────────────────

def test_spearman_basic():
    assert abs(_spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(_spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert _spearman([1], [1]) == 0.0
    print("✓ spearman correlation correct")


def test_distribution_detects_concentration():
    env = check_distribution(_gretil_alphabetic_bias_payload(), "gretil")
    assert env["pass"] is False, "alphabetic-bias payload should fail distribution"
    # Agni (first alphabetically) should be the worst-concentrated source.
    assert env["worst_source_pct"] > 15.0
    assert env["top"][0]["source"] == "Agni Purana"
    print(f"✓ distribution flags over-concentration "
          f"(worst={env['top'][0]['source']} @ {env['worst_source_pct']}%)")


def test_distribution_passes_when_healthy():
    env = check_distribution(_healthy_payload(), "hybrid")
    assert env["pass"] is True, f"healthy payload should pass: {env}"
    assert env["distinct_sources"] >= 15
    print("✓ distribution passes on a well-spread result set")


def test_alphabetic_bias_detected():
    env = check_alphabetic_bias(_gretil_alphabetic_bias_payload(), "gretil")
    assert env["pass"] is False, f"should detect alphabetic bias: {env}"
    print(f"✓ alphabetic bias detected (corr={env['correlation']})")


def test_metadata_quality_flags_pollution():
    payload = {"queries": [], "corpus": _corpus_with_pollution()}
    env = check_metadata_quality(payload)
    assert env["pass"] is False, "fragmented Sharma names should fail metadata QC"
    assert env["polluted_count"] >= 40
    assert any("darshans" in ex for ex in env["polluted_examples"])
    print(f"✓ metadata QC flags {env['polluted_count']} polluted source names")


def test_metadata_quality_passes_clean():
    payload = {"corpus": {"sources": [
        {"name": "Skanda Purana"}, {"name": "Mahabharata"},
        {"name": "Bhagavata Purana"}, {"name": "Vishnu Purana"}]}}
    env = check_metadata_quality(payload)
    assert env["pass"] is True
    print("✓ metadata QC passes clean names")


def test_known_item_recall():
    payload = {"queries": [
        {"query": "Gayatri mantra", "results": [
            {"source": "Rigveda (Aufrecht ed.)"}, {"source": "Agni Purana"}]},
        {"query": "Nataraja dance", "results": [
            {"source": "Agni Purana"}, {"source": "Skanda Purana"}]},
    ]}
    expectations = [
        {"query": "Gayatri mantra", "expect_source_contains": "Rigveda", "top_k": 5},
        {"query": "Nataraja dance", "expect_source_contains": "Shiva", "top_k": 5},
    ]
    env = check_known_items(payload, expectations)
    assert env["hits"] == 1 and env["total"] == 2
    assert env["pass"] is False
    print(f"✓ known-item recall: {env['recall_pct']}%")


def test_hybrid_contribution_detects_dead_fts():
    payload = {"queries": [
        {"query": q, "results": [{"source": "X", "fts_hit": False}]}
        for q in ["a", "b", "c", "d"]
    ]}
    env = check_hybrid_contribution(payload)
    assert env["pass"] is False
    assert env["fts_fire_rate_pct"] == 0.0
    print("✓ hybrid-contribution detects dead FTS (the 0.000 kw_sim bug)")


def test_coverage():
    corpus = {"sources": [{"name": f"Text{i}"} for i in range(10)]}
    payload = {"corpus": corpus, "queries": [
        {"query": "q", "results": [{"source": "Text0"}, {"source": "Text1"},
                                    {"source": "Text2"}]}]}
    env = check_coverage(payload)
    assert env["pass"] is False
    assert env["coverage_pct"] == 30.0
    print(f"✓ coverage: {env['coverage_pct']}%")


def test_corpus_separation_recommends_split():
    payload = {"corpus": _corpus_with_pollution()}
    env = check_corpus_separation(payload)
    assert env["fragmentation_index"] >= 3.0, f"should flag fragmentation: {env}"
    assert "SEPARATE" in env["recommendation"]
    print(f"✓ corpus separation: frag_index={env['fragmentation_index']}, "
          f"vol={env['guruji_volume_pct']}%, names={env['guruji_sourcename_pct']}%")


def test_analyze_combines_and_gates():
    payload = _gretil_alphabetic_bias_payload()
    data = analyze(payload)
    assert data["healthy"] is False
    assert "distribution" in data["failed_checks"] or "alphabetic_bias" in data["failed_checks"]
    assert "corpus_separation" not in data["failed_checks"]
    print("✓ analyze() gates on failing checks, excludes advisory ones")


def test_envelope_shape():
    env = run(payload=_healthy_payload())
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert isinstance(env["data"], dict) and "checks" in env["data"]
    bad = run(payload={"queries": []})
    assert bad["success"] is False
    assert bad["errors"] and "code" in bad["errors"][0]
    print("✓ envelope shape correct (success + failure paths)")


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nALL {len(fns)} TESTS PASSED")


if __name__ == "__main__":
    try:
        _run_all()
    except AssertionError as e:
        print(f"\nFAIL: {e}")
        sys.exit(1)
    sys.exit(0)
