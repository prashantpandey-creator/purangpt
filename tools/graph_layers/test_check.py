"""graph_layers — tests-first (Rule 0, precondition A).

Run: venv/bin/python -m tools.graph_layers.test_check   (from purangpt/ repo root)
"""
from __future__ import annotations

import sys

from tools.graph_layers.check import (
    layer_of, build_layer_adjacency, walk, separated_lineage, run,
)


def _manifest():
    # Lahiri is BOTH father and guru to Tinkori; Satyacharan→Sharma is guru ONLY.
    ents = [{"id": i, "name": i.title()} for i in
            ["lahiri", "tinkori", "satyacharan", "sharma", "krishna", "arjuna"]]
    edges = [
        {"src": "lahiri", "dst": "tinkori", "rel": "father"},
        {"src": "lahiri", "dst": "tinkori", "rel": "guru_of"},
        {"src": "tinkori", "dst": "satyacharan", "rel": "father"},
        {"src": "tinkori", "dst": "satyacharan", "rel": "guru_of"},
        {"src": "satyacharan", "dst": "sharma", "rel": "guru_of"},  # teaching ONLY
        {"src": "krishna", "dst": "arjuna", "rel": "teaches"},      # teaching, not kin
    ]
    return {"entities": ents, "edges": edges}


def test_layer_of_classifies():
    assert layer_of("father") == "kinship"
    assert layer_of("guru_of") == "transmission"
    assert layer_of("avatar") == "identity"
    assert layer_of("killed") == "conflict"
    assert layer_of("totally_made_up") == "other"


def test_kinship_and_transmission_are_separate_adjacencies():
    adj = build_layer_adjacency(_manifest()["edges"])
    assert "tinkori" in adj["kinship"]["lahiri"]
    assert "tinkori" in adj["transmission"]["lahiri"]
    # the teaching-only hop must NOT appear in kinship
    assert "sharma" not in adj["kinship"].get("satyacharan", set())
    assert "sharma" in adj["transmission"]["satyacharan"]


def test_blood_line_stops_where_blood_stops():
    d = separated_lineage(_manifest(), "lahiri")
    blood = d["layers"]["kinship_down"]
    teach = d["layers"]["transmission_down"]
    # blood line: Lahiri → Tinkori → Satyacharan (stops; Sharma not blood)
    assert "Sharma" not in blood, f"Sharma must NOT be in the blood line: {blood}"
    # teaching line runs all the way to Sharma
    assert "Sharma" in teach, f"Sharma must be in the teaching line: {teach}"


def test_coincidence_detected_not_deleted():
    d = separated_lineage(_manifest(), "lahiri")
    # Lahiri→Tinkori is both father and guru — must be REPORTED, both edges kept
    assert d["coincide_count"] >= 2
    assert any("Lahiri" in c and "Tinkori" in c for c in d["coincide_sample"])


def test_lineage_is_vertical_no_sibling_hops():
    m = _manifest()
    m["edges"].append({"src": "sharma", "dst": "sibling_x", "rel": "brother"})
    m["entities"].append({"id": "sibling_x", "name": "Sibling X"})
    d = separated_lineage(m, "sharma")
    flat = sum(d["layers"].values(), [])
    assert "Sibling X" not in flat, "a lineage must not step sideways to a sibling"


def test_include_lateral_flag_drops_siblings():
    edges = [{"src": "a", "dst": "b", "rel": "brother"}]
    with_lat = build_layer_adjacency(edges, include_lateral=True)
    without = build_layer_adjacency(edges, include_lateral=False)
    assert with_lat["kinship"].get("a")
    assert not without["kinship"].get("a"), "lateral edges must be dropped when off"


def test_walk_is_cycle_guarded():
    adj = {"a": {"b"}, "b": {"a"}}  # a↔b cycle
    chain = walk(adj, "a", depth=10)
    assert chain == ["a", "b"], f"cycle must not loop: {chain}"


def test_envelope_and_errors():
    env = run(person="")
    assert env["success"] is False and env["errors"][0]["code"] == "no_person"
    env2 = run(person="nonexistent_xyz", manifest_path=__import__("os").path.abspath(
        __import__("os").path.join(__import__("os").path.dirname(__file__),
                                   "..", "read_pass", "out", "graph_manifest.json")))
    # either unknown_person (manifest present) or missing_manifest — both clean failures
    assert env2["success"] is False
    assert env2["errors"][0]["code"] in ("unknown_person", "missing_manifest")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1; print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1; print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
