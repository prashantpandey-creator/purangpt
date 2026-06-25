"""graph_health — tests-first (Rule 0, precondition A).

Fixtures are real-sliced data from the actual graph memory, committed beside this
file. Tests run against those fixtures so we never need to load the full 14MB
manifest just to verify the tool logic.

Run: venv/bin/python -m tools.graph_health.test_check   (from purangpt/ repo root)
"""
from __future__ import annotations

import json
import os
import sys

DIR = os.path.dirname(__file__)
FIX = os.path.join(DIR, "fixtures")


def _load_json(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


def _load_jsonl(name):
    rows = []
    with open(os.path.join(FIX, name)) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


from tools.graph_health.check import (
    run,
    analyze_manifest,
    analyze_records,
    cite_contamination,
    _MARKER_RE,
)


def test_manifest_counts():
    m = _load_json("mini_manifest.json")
    result = analyze_manifest(m)
    assert result["n_entities"] == 4
    assert result["n_edges"] == 4
    assert result["n_isolated"] == 1, f"lonely node should be isolated, got {result['n_isolated']}"


def test_manifest_kind_distribution():
    m = _load_json("mini_manifest.json")
    result = analyze_manifest(m)
    kinds = result["kind_distribution"]
    assert kinds["sage"] == 2
    assert kinds["deity"] == 1
    assert kinds["place"] == 1


def test_manifest_top_entities_by_degree():
    m = _load_json("mini_manifest.json")
    result = analyze_manifest(m)
    top = result["top_entities_by_degree"]
    assert len(top) > 0
    assert top[0]["id"] in ("vyāsa", "kṛṣṇa"), f"top should be vyāsa or kṛṣṇa, got {top[0]['id']}"
    assert top[0]["degree"] == 3


def test_manifest_rel_types():
    m = _load_json("mini_manifest.json")
    result = analyze_manifest(m)
    rels = result["relationship_types"]
    assert "disciple" in rels
    assert "same as" in rels
    assert rels["disciple"] == 1


def test_cite_contamination_detects_bhp_on_mahabharata():
    records = _load_jsonl("maha_head.records.jsonl")
    result = cite_contamination(records, "mahabharata")
    assert result["total_cites"] > 0, "should find cites"
    assert result["bhp_on_non_bhagavata"] > 0, "mahabharata records carry bhp_ markers"
    assert 0 < result["contamination_pct"] <= 100


def test_cite_contamination_clean_on_bhagavata():
    records = _load_jsonl("gita_head.records.jsonl")
    result = cite_contamination(records, "bhagavata")
    assert result["bhp_on_non_bhagavata"] == 0, "bhagavata text should not flag bhp_ as contamination"


def test_cite_contamination_bare_numbers():
    records = _load_jsonl("maha_head.records.jsonl")
    result = cite_contamination(records, "mahabharata")
    assert result["bare_number_cites"] >= 0


def test_records_analysis():
    records = _load_jsonl("maha_head.records.jsonl")
    result = analyze_records(records)
    assert result["n_records"] == 2
    assert result["n_entities"] > 0
    assert result["n_relationships"] > 0
    assert "provider_mix" in result
    assert "deepseek" in result["provider_mix"]
    assert "salvage_rate" in result
    assert "lens_applied_rate" in result


def test_records_teaching_fill():
    records = _load_jsonl("maha_head.records.jsonl")
    result = analyze_records(records)
    assert "teaching_fill_pct" in result
    assert "story_fill_pct" in result


def test_marker_regex_matches_canonical():
    assert _MARKER_RE.search("bhp_01.03.040")
    assert _MARKER_RE.search("bg_01.15")
    assert _MARKER_RE.search("GhS_1.0")
    assert _MARKER_RE.search("RV_1")


def test_marker_regex_rejects_snakecase():
    assert not _MARKER_RE.fullmatch("chapter_1")
    assert not _MARKER_RE.fullmatch("foo_bar")


def test_envelope_shape():
    env = run(
        manifest_path=os.path.join(FIX, "mini_manifest.json"),
        records_dir=FIX,
    )
    assert "success" in env
    assert "data" in env
    assert "metadata" in env
    assert "errors" in env
    if env["success"]:
        d = env["data"]
        assert "manifest" in d
        assert "per_text" in d
        assert "citation_health" in d


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
