"""Tests-first for the citation verifier (Rule 0 precond A).

Verification is DETERMINISTIC and needs zero LLM calls: a cited verse marker is
"grounded" iff it literally appears in the window text the node claims to come
from. Hallucinated markers (not in the window) are flagged/pruned. Tested
against a REAL captured (window, record) fixture so we measure the right thing.

Run: venv/bin/python -m tools.read_pass.test_verify   (exit 0)
"""
from __future__ import annotations
import json
import os

from tools.read_pass import verify

HERE = os.path.dirname(__file__)
FIXTURE = os.path.join(HERE, "fixture_verify_pair.json")


def _fixture():
    with open(FIXTURE) as f:
        return json.load(f)


def test_extract_markers_finds_canonical_verse_ids():
    fx = _fixture()
    found = verify.extract_markers(fx["window_text"])
    # the fixture told us exactly which markers are present
    assert set(found) == set(fx["markers_present"]), (
        f"marker extraction drift: {set(found) ^ set(fx['markers_present'])}")


def test_grounded_citation_passes():
    present = ["bhp_01.01.001", "bhp_01.01.002"]
    node = {"name": "X", "verse_ranges": ["bhp_01.01.001"]}
    res = verify.check_node(node, set(present))
    assert res["grounded"] is True
    assert res["ungrounded_cites"] == []


def test_hallucinated_citation_is_flagged():
    present = {"bhp_01.01.001"}
    node = {"name": "Ghost", "verse_ranges": ["bhp_99.99.999"]}
    res = verify.check_node(node, present)
    assert res["grounded"] is False
    assert "bhp_99.99.999" in res["ungrounded_cites"]


def test_partial_grounding_keeps_node_but_lists_bad_cites():
    present = {"bhp_01.01.001"}
    node = {"verse_ranges": ["bhp_01.01.001", "bhp_02.02.002"]}
    res = verify.check_node(node, present)
    # at least one good cite -> node is grounded, but the bad one is reported
    assert res["grounded"] is True
    assert res["ungrounded_cites"] == ["bhp_02.02.002"]


def test_node_with_no_cites_is_ungrounded():
    res = verify.check_node({"verse_ranges": []}, {"bhp_01.01.001"})
    assert res["grounded"] is False


def test_verify_record_envelope_and_counts_on_real_fixture():
    fx = _fixture()
    rec = {
        "entities": fx["record_sample"]["entities"],
        "relationships": fx["record_sample"]["relationships"],
        "teachings": fx["record_sample"]["teachings"],
        "story": {"title": "t", "arc": "a"},
        "chapter_summary": "s",
        "_provenance": {"chapter_label": "Chapter 1"},
    }
    env = verify.verify_record(rec, fx["window_text"])
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"] is True
    d = env["data"]
    # real fixture cites are grounded -> grounded_rate should be high
    assert d["total_nodes"] > 0
    assert 0.0 <= d["grounded_rate"] <= 1.0
    assert d["grounded_rate"] >= 0.8, f"real fixture should mostly ground: {d}"


def test_prune_removes_ungrounded_nodes():
    rec = {
        "entities": [
            {"name": "Real", "kind": "deity", "verse_ranges": ["bhp_01.01.001"]},
            {"name": "Fake", "kind": "deity", "verse_ranges": ["bhp_77.77.777"]},
        ],
        "relationships": [], "teachings": [],
        "story": {"title": "t", "arc": "a"}, "chapter_summary": "s",
        "_provenance": {},
    }
    pruned = verify.prune(rec, "text with bhp_01.01.001 in it")
    names = [e["name"] for e in pruned["entities"]]
    assert names == ["Real"], names


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
        except Exception as e:  # noqa
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
