"""graph_viz — tests-first (Rule 0, precondition A).

Run: venv/bin/python -m tools.graph_viz.test_check   (from purangpt/ repo root)
"""
from __future__ import annotations

import sys

from tools.graph_viz.check import distill, run


def _fake_manifest():
    # a pantheon hub + an isolated low-degree lineage that must be force-included
    ents = [{"id": f"deity{i}", "name": f"Deity{i}", "kind": "deity"} for i in range(10)]
    ents += [
        {"id": "babaji", "name": "Babaji", "kind": "sage"},
        {"id": "lahiri mahasaya", "name": "Lahiri Mahasaya", "kind": "sage"},
        {"id": "shailendra sharma", "name": "Shailendra Sharma", "kind": "sage"},
    ]
    edges = []
    for i in range(1, 10):
        edges.append({"src": "deity0", "dst": f"deity{i}", "rel": "father"})
    edges += [
        {"src": "babaji", "dst": "lahiri mahasaya", "rel": "guru_of"},
        {"src": "lahiri mahasaya", "dst": "shailendra sharma", "rel": "guru"},
        {"src": "babaji", "dst": "deity0", "rel": "guru"},
    ]
    return {"entities": ents, "edges": edges}


def test_distill_includes_top_degree_hub():
    v = distill(_fake_manifest(), top_n=5)
    assert "deity0" in {n["id"] for n in v["nodes"]}


def test_distill_force_includes_lineage_even_if_low_degree():
    v = distill(_fake_manifest(), top_n=3)
    ids = {n["id"] for n in v["nodes"]}
    for lid in ("babaji", "lahiri mahasaya", "shailendra sharma"):
        assert lid in ids, f"{lid} must be force-included despite low degree"
    assert v["stats"]["lineage_present"]


def test_lineage_edges_flagged():
    v = distill(_fake_manifest(), top_n=5)
    lin = [l for l in v["links"] if l["lineage"]]
    assert any(l["s"] == "babaji" and l["t"] == "lahiri mahasaya" for l in lin)


def test_bridge_pulls_pantheon_node_in():
    v = distill(_fake_manifest(), top_n=1)
    assert "deity0" in {n["id"] for n in v["nodes"]}


def test_node_has_degree_and_kind():
    v = distill(_fake_manifest(), top_n=5)
    for n in v["nodes"]:
        assert "deg" in n and "kind" in n and "lineage" in n


def test_envelope_and_html_written():
    tmp_out = "/tmp/_graphviz_test.html"
    env = run(top_n=20, out_html=tmp_out)
    assert "success" in env and "data" in env and "errors" in env
    if env["success"]:
        import os
        assert os.path.isfile(tmp_out)
        html = open(tmp_out).read()
        assert "<svg" in html and "d3" in html.lower()
        assert env["data"]["n_nodes"] > 0


def test_missing_manifest_fails_cleanly():
    env = run(manifest_path="/nonexistent/x.json")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "missing_manifest"


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
