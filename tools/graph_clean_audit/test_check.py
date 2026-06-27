"""Tests for graph_clean_audit — written FIRST (Rule 0 precondition A).

Run: venv/bin/python -m tools.graph_clean_audit.test_check  (from purangpt/ root)

Two layers: (1) synthetic fixtures with KNOWN violations prove each detector
counts what it should; (2) a run against the REAL graph proves the envelope shape
and that a known real offender (the practice 'Kriya Yoga' as a guru) is caught.
"""
from tools.graph_clean_audit.check import run, _OUTPUT_SCHEMA, _GRAPH, _RAM

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}

# --- synthetic fixtures: a tiny graph with one of each violation --------------
_ENTITIES = [
    {"id": "rama", "name": "Rama", "kind": "king"},
    {"id": "dasharatha", "name": "Dasharatha", "kind": "king"},
    {"id": "lava", "name": "Lava", "kind": "king"},
    {"id": "kriya_yoga", "name": "Kriya Yoga", "kind": "practice"},
    {"id": "sharma", "name": "Shailendra Sharma", "kind": "sage"},
    {"id": "narrator", "name": "Narrator", "kind": "sage"},
    {"id": "babaji", "name": "Babaji", "kind": "sage"},
    {"id": "x", "name": "X", "kind": "sage"},
    {"id": "y", "name": "Y", "kind": "sage"},
    # a real being MIS-TYPED as a concept (the Devaki=concept case)
    {"id": "devaki", "name": "Devaki", "kind": "concept"},
    {"id": "krishna", "name": "Krishna", "kind": "deity"},
]
_EDGES = [
    # clean kin: both encode Dasharatha=parent of Rama (same direction → no clash)
    {"src": "dasharatha", "rel": "son", "dst": "rama", "src_name": "Dasharatha", "dst_name": "Rama"},
    {"src": "dasharatha", "rel": "father", "dst": "rama", "src_name": "Dasharatha", "dst_name": "Rama"},
    {"src": "rama", "rel": "son", "dst": "lava", "src_name": "Rama", "dst_name": "Lava"},
    # MIS-TYPED being: Devaki (kind=concept) is Krishna's mother → kin participant,
    # so a re-type candidate, NOT a genuine relation violation
    {"src": "devaki", "rel": "mother", "dst": "krishna", "src_name": "Devaki", "dst_name": "Krishna"},
    # KIN direction contradiction: X is father of Y AND Y is father of X
    {"src": "x", "rel": "father", "dst": "y", "src_name": "X", "dst_name": "Y"},
    {"src": "y", "rel": "father", "dst": "x", "src_name": "Y", "dst_name": "X"},
    # GENUINE non-being guru: the practice 'Kriya Yoga' (never a kin participant)
    {"src": "sharma", "rel": "guru", "dst": "kriya_yoga", "src_name": "Shailendra Sharma", "dst_name": "Kriya Yoga"},
    # GENUINE artifact guru: 'Narrator' (kind=sage but artifact name, no kin)
    {"src": "babaji", "rel": "guru", "dst": "narrator", "src_name": "Babaji", "dst_name": "Narrator"},
    # clean guru: Babaji is guru of Sharma (one direction only)
    {"src": "babaji", "rel": "guru", "dst": "sharma", "src_name": "Babaji", "dst_name": "Shailendra Sharma"},
    # GURU direction contradiction via mixed predicates: X teaches Y AND X taught_by Y
    {"src": "x", "rel": "teaches", "dst": "y", "src_name": "X", "dst_name": "Y"},
    {"src": "x", "rel": "taught_by", "dst": "y", "src_name": "X", "dst_name": "Y"},
    # self loop
    {"src": "babaji", "rel": "alias", "dst": "babaji", "src_name": "Babaji", "dst_name": "Babaji"},
]


def _fix():
    return run(edges=_EDGES, entities=_ENTITIES, n_samples=10)


def test_envelope_and_schema():
    env = _fix()
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True and env["errors"] == []
    assert set(env["data"].keys()) == set(_OUTPUT_SCHEMA.keys()), env["data"].keys()
    print("ok: envelope_and_schema")


def test_genuine_non_being_guru_detected():
    d = _fix()["data"]
    # Kriya Yoga (practice) + Narrator (artifact) = 2 GENUINE non-being guru
    # relations; neither is a kin participant, so both are genuine noise.
    nbr = d["guru"]["non_being_relations"]
    assert nbr["genuine"] == 2, nbr
    flagged = {s["non_being"] for s in nbr["samples_genuine"]}
    assert "Kriya Yoga" in flagged and "Narrator" in flagged, flagged
    print("ok: genuine_non_being_guru_detected")


def test_mistyped_being_is_not_a_violation():
    d = _fix()["data"]
    # Devaki (concept) is Krishna's mother → a kin participant → classified as a
    # MIS-TYPED being (re-type candidate), NOT a genuine relation violation.
    assert d["kin"]["non_being_relations"]["mistyped"] == 1, d["kin"]["non_being_relations"]
    assert d["kin"]["non_being_relations"]["genuine"] == 0, d["kin"]["non_being_relations"]
    names = {s["name"] for s in d["retype_candidates"]["samples"]}
    assert "Devaki" in names, d["retype_candidates"]
    assert d["retype_candidates"]["count"] == 1, d["retype_candidates"]
    print("ok: mistyped_being_is_not_a_violation")


def test_kin_direction_contradiction_detected():
    d = _fix()["data"]
    # X<->Y mutual father is exactly one contradictory pair
    assert d["kin"]["direction_contradictions"]["count"] == 1, \
        d["kin"]["direction_contradictions"]
    # the clean Dasharatha/Rama pair (both edges same direction) is NOT flagged
    pairs = {(s["a"], s["b"]) for s in d["kin"]["direction_contradictions"]["samples"]}
    assert ("dasharatha", "rama") not in pairs and ("rama", "dasharatha") not in pairs
    print("ok: kin_direction_contradiction_detected")


def test_guru_direction_contradiction_detected():
    d = _fix()["data"]
    # teaches (X=guru) + taught_by (Y=guru) on X->Y = one contradiction
    assert d["guru"]["direction_contradictions"]["count"] == 1, \
        d["guru"]["direction_contradictions"]
    print("ok: guru_direction_contradiction_detected")


def test_self_loop_detected():
    d = _fix()["data"]
    assert d["self_loops"]["count"] == 1, d["self_loops"]
    assert d["self_loops"]["samples"][0]["name"] == "Babaji"
    print("ok: self_loop_detected")


def test_clean_pct_math():
    d = _fix()["data"]
    s = d["summary"]
    # violations = 2 (non-being) + 1 (kin contra) + 1 (guru contra) = 4
    assert s["violations"] == 4, s
    assert s["relationship_edges"] == d["kin"]["n_edges"] + d["guru"]["n_edges"]
    print("ok: clean_pct_math")


def test_bad_path_returns_false_envelope():
    env = run(graph_path="/no/such/file.json", ram_path=_RAM)
    assert env["success"] is False and env["data"] is None
    assert env["errors"][0]["code"] == "load_failed", env["errors"]
    print("ok: bad_path_returns_false_envelope")


def test_real_graph_catches_kriya_yoga():
    env = run(graph_path=_GRAPH, ram_path=_RAM, n_samples=50)
    assert env["success"] is True, env["errors"]
    d = env["data"]
    assert d["n_edges"] > 20000 and d["n_entities"] > 8000, (d["n_edges"], d["n_entities"])
    # the real, known offender: 'Kriya Yoga' (practice) listed as a guru
    flagged = {s["non_being"] for s in d["guru"]["non_being_relations"]["samples_genuine"]}
    assert any("kriya" in f.lower() for f in flagged), \
        f"Kriya Yoga not among flagged genuine non-being gurus: {sorted(flagged)[:20]}"
    # and Devaki (concept, but Krishna's mother) must be a re-type candidate,
    # NOT counted as a broken relation
    retype_names = {s["name"] for s in d["retype_candidates"]["samples"]}
    assert d["retype_candidates"]["count"] > 100, d["retype_candidates"]["count"]
    print(f"ok: real_graph (clean={d['summary']['clean_pct']}%, "
          f"retype_candidates={d['retype_candidates']['count']})")


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
