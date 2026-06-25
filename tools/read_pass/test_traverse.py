"""Tests-first for traverse — the deterministic multi-hop path finder over the
graph (Rule 0 precond A). This is STEP 3 / axis C of CONSCIOUSNESS_ROADMAP.md.

WHY IT EXISTS — the consciousness bar (memory consciousness-over-rag): the
canonical query daddy wants is "which weapons were god-given, by whom?" That is a
TWO-HOP pattern — (deity) --[gives/demands]--> (weapon) --[wielded_by]--> (hero) —
not a passage that exists to retrieve. recall.py reaches exactly ONE hop
(_expand_one_hop), so it can surface the neighbours of a seed but never the PATH
that ties giver→gift→wielder. traverse() walks the real graph edges to assemble
those whole paths. It is the first axis where the engine still falls short of
"the mind, not the librarian".

WHAT THE REAL GRAPH FORCED THESE TESTS TO PIN (observed in graph_manifest.json,
8755 entities / 24474 edges / 2853 rel verbs):
  - Real chains exist and are verse-cited: Krishna --[charioteer]--> Arjuna
    --[killed]--> Karna. Good — find them.
  - Cycles abound: Krishna --[killed]--> Putana --[attempted_to_kill]--> Krishna.
    A path must NEVER revisit a node, or hub traversal loops forever.
  - Identity edges (alias / is / identical_to) are NOT meaning-hops — that is
    axis B's job (cross-text identity). A "path" made of aliases is a renamed
    single node pretending to be a journey. They must not count as traversal hops.
  - Hubs are huge (Krishna has 649 out-edges). Fan-out MUST be bounded or the
    result set explodes.
  - Consciousness = VERIFIABLE facts: each hop must carry grounded cites, run
    through verify's marker grammar exactly as factsheet does — no 'verse 17' of
    nothing.

Run: venv/bin/python -m tools.read_pass.test_traverse   (exit 0)
"""
from __future__ import annotations
import os

from tools.read_pass import traverse
from tools.read_pass import recall as R

HERE = os.path.dirname(__file__)
GRAPH = os.path.join(HERE, "out", "graph_manifest.json")
RAM = os.path.join(HERE, "out", "guruji_ram.json")


def _memory():
    """The real brain — traverse walks the SAME Memory.edges recall/factsheet use."""
    return R.Memory.load(GRAPH, RAM)


# ── envelope shape (precond B) ───────────────────────────────────────────────
def test_envelope_shape():
    env = traverse.traverse("Krishna", _memory())
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}, env.keys()
    assert isinstance(env["errors"], list)


def test_empty_symbol_is_clean_failure_not_raise():
    env = traverse.traverse("", _memory())
    assert env["success"] is False
    assert env["data"] in (None, {}, {"found": False})
    assert env["errors"] and env["errors"][0]["code"] == "empty"


def test_unknown_symbol_is_found_false_not_crash():
    env = traverse.traverse("Zxqwvplmnobody", _memory())
    # a real, clean answer: nothing found — NOT an exception, NOT success:false
    assert env["success"] is True
    assert env["data"]["found"] is False
    assert env["data"]["paths"] == []


# ── the core capability: assemble a whole multi-hop path ─────────────────────
def test_finds_a_real_two_hop_path_that_one_hop_cannot():
    """Krishna --[charioteer]--> Arjuna --[killed]--> Karna is a genuine chain in
    the graph. A one-hop recall around Krishna can never produce it. traverse must."""
    env = traverse.traverse("Krishna", _memory(), max_hops=2)
    assert env["success"] and env["data"]["found"]
    paths = env["data"]["paths"]
    assert paths, "expected at least one multi-hop path from a 649-edge hub"
    # every returned path has 2..max_hops hops, each hop a {src_name,rel,dst_name}
    for p in paths:
        hops = p["hops"]
        assert 1 <= len(hops) <= 2
        for h in hops:
            assert h["rel"] and h["src_name"] and h["dst_name"]
    # at least one path is genuinely length-2 (a real chain, not just neighbours)
    assert any(len(p["hops"]) == 2 for p in paths), "no true 2-hop chain surfaced"


def test_a_path_reads_as_a_chain_endpoints_connect():
    """Within a path, hop[i].dst must equal hop[i+1].src — a real walk, not a
    bag of disconnected edges."""
    env = traverse.traverse("Krishna", _memory(), max_hops=2)
    for p in env["data"]["paths"]:
        hops = p["hops"]
        for a, b in zip(hops, hops[1:]):
            assert a["dst"] == b["src"], f"broken chain: {a} -> {b}"


# ── the failure modes the REAL graph forces ──────────────────────────────────
def test_paths_never_revisit_a_node_no_cycles():
    """Krishna --killed--> Putana --attempted_to_kill--> Krishna is a real cycle.
    A path must visit each node at most once."""
    env = traverse.traverse("Krishna", _memory(), max_hops=3)
    for p in env["data"]["paths"]:
        nodes = [p["hops"][0]["src"]] + [h["dst"] for h in p["hops"]]
        assert len(nodes) == len(set(nodes)), f"cycle in path: {nodes}"


def test_identity_edges_are_not_traversal_hops():
    """alias / is / identical_to are cross-text IDENTITY (axis B), not a journey.
    No hop in any returned path may be one of them — a path made of aliases is a
    single node wearing different names, not multi-hop reasoning."""
    identity_rels = {"alias", "is", "identical_to", "same_as", "aka"}
    env = traverse.traverse("Vishnu", _memory(), max_hops=2)
    for p in env["data"]["paths"]:
        for h in p["hops"]:
            assert h["rel"].lower() not in identity_rels, \
                f"identity edge leaked into a path as a hop: {h}"


def test_depth_bound_is_respected():
    env1 = traverse.traverse("Krishna", _memory(), max_hops=1)
    for p in env1["data"]["paths"]:
        assert len(p["hops"]) <= 1
    env2 = traverse.traverse("Krishna", _memory(), max_hops=2)
    assert max((len(p["hops"]) for p in env2["data"]["paths"]), default=0) <= 2


def test_typed_edge_filter_restricts_relations():
    """The 'weapons god-given by whom' query needs to follow ONLY giving-type
    edges. rel_filter must constrain which relations a walk may traverse."""
    mem = _memory()
    # pick a relation that exists; constrain to it and assert nothing else appears
    env = traverse.traverse("Krishna", mem, max_hops=2, rel_filter={"killed"})
    for p in env["data"]["paths"]:
        for h in p["hops"]:
            assert h["rel"] == "killed", f"rel_filter breached: {h['rel']}"


def test_fanout_is_bounded_on_a_hub():
    """Krishna has 649 out-edges; without a bound a 2-hop walk is hundreds of
    thousands of paths. The result set must be capped (max_paths)."""
    env = traverse.traverse("Krishna", _memory(), max_hops=2, max_paths=50)
    assert len(env["data"]["paths"]) <= 50


# ── consciousness = VERIFIABLE: each hop carries grounded cites ───────────────
def test_hops_carry_grounded_cites_only():
    """Every hop's cites must be canonical markers (verify grammar) — the same
    honesty discipline factsheet enforces. No bare-number garbage; a path you
    can't verify is a confident liar, not a mind."""
    from tools.read_pass import verify
    env = traverse.traverse("Krishna", _memory(), max_hops=2)
    saw_a_cite = False
    for p in env["data"]["paths"]:
        for h in p["hops"]:
            for c in h.get("cites", []):
                saw_a_cite = True
                m = verify._MARKER_RE.search(str(c))
                assert m and (m.group(0) == str(c).strip()
                              or str(c).strip().startswith(m.group(0))), \
                    f"ungrounded cite leaked into a hop: {c!r}"
    assert saw_a_cite, "expected at least one grounded cite across all hops"


# ── grounding signal: a caller must know how SOLID each path is ──────────────
# The real graph (measured across 8 hubs / 1600 paths) is only ~46% fully
# grounded — 43% have an uncited hop, 10% none. A chain you can't verify is not a
# fact; traverse must REPORT each path's grounding so decode/daddy can prefer the
# gold instead of trusting every chain equally (the factsheet honesty discipline).
def test_each_path_reports_whether_fully_grounded():
    env = traverse.traverse("Krishna", _memory(), max_hops=2)
    assert env["data"]["paths"], "need paths to check grounding flags"
    for p in env["data"]["paths"]:
        assert "grounded" in p, "path missing 'grounded' flag"
        assert isinstance(p["grounded"], bool)
        # the flag must MATCH reality: grounded iff every hop carries >=1 cite
        every_hop_cited = all(h.get("cites") for h in p["hops"])
        assert p["grounded"] == every_hop_cited, \
            f"grounded flag lies: flag={p['grounded']} hops_cited={every_hop_cited}"


def test_grounded_only_returns_solely_fully_cited_paths():
    """With grounded_only=True, EVERY returned path must be fully grounded — the
    'give me only what I can defend with a verse' mode."""
    env = traverse.traverse("Vishnu", _memory(), max_hops=2, max_paths=100,
                            grounded_only=True)
    for p in env["data"]["paths"]:
        assert p["grounded"] is True
        for h in p["hops"]:
            assert h.get("cites"), f"ungrounded hop in grounded_only result: {h}"


def test_metadata_counts_grounded_vs_total():
    """metadata reports how many of the returned paths are fully grounded — a
    caller sees the solidity of the whole result at a glance."""
    env = traverse.traverse("Krishna", _memory(), max_hops=2, max_paths=40)
    md = env["metadata"]
    assert "n_paths" in md and "n_grounded" in md
    assert md["n_paths"] == len(env["data"]["paths"])
    assert 0 <= md["n_grounded"] <= md["n_paths"]


# ── metadata reports the search so a caller/orchestrator can reason about it ──
def test_metadata_reports_search_params():
    env = traverse.traverse("Krishna", _memory(), max_hops=2, max_paths=20)
    md = env["metadata"]
    assert md.get("max_hops") == 2
    assert md.get("max_paths") == 20
    assert "start" in md  # the resolved start entity (name or id)


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
