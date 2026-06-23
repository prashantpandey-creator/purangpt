"""Tests-first for the two-layer identity model (Rule 0 precond A).

Inspired by Sharma's metaphysics: the One appears as many. The graph must
keep manifestations as distinct nodes (manifest layer) and connect them with
typed identity EDGES (ground layer) — never collapse by alias.

See IDENTITY_MODEL.md.

Run: venv/bin/python -m tools.read_pass.test_identity   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import identity


def test_exact_name_same_kind_yields_same_as():
    # Rāma (deity) appearing in two texts → same_as edge, NOT merge
    entities = [
        {"id": "rama@a", "name": "Rāma", "kind": "deity", "all_forms": ["Rāma"],
         "chapters": ["Ch 1"], "source_text": "garuda_v1"},
        {"id": "rama@b", "name": "rama", "kind": "deity", "all_forms": ["rama"],
         "chapters": ["Ch 5"], "source_text": "padma_v1"},
    ]
    edges = identity.build_identity_edges(entities, [])
    same = [e for e in edges if e["type"] == "same_as"]
    assert len(same) >= 1
    pair = {same[0]["src"], same[0]["dst"]}
    assert pair == {"rama@a", "rama@b"}


def test_macron_blocks_same_as():
    # Kṛṣṇa (deity) and Kṛṣṇā (queen) must NOT get a same_as edge
    entities = [
        {"id": "k1", "name": "Kṛṣṇa", "kind": "deity", "all_forms": ["Kṛṣṇa"],
         "chapters": ["Ch 1"], "source_text": "a"},
        {"id": "k2", "name": "Kṛṣṇā", "kind": "queen", "all_forms": ["Kṛṣṇā"],
         "chapters": ["Ch 1"], "source_text": "a"},
    ]
    edges = identity.build_identity_edges(entities, [])
    same = [e for e in edges if e["type"] == "same_as"
            and {e["src"], e["dst"]} == {"k1", "k2"}]
    assert not same, "macron gender distinction must block same_as"


def test_incompatible_kind_blocks_same_as():
    # Same name, different kind → no same_as
    entities = [
        {"id": "h1", "name": "Hari", "kind": "deity", "all_forms": ["Hari"],
         "chapters": ["Ch 1"], "source_text": "a"},
        {"id": "h2", "name": "Hari", "kind": "king", "all_forms": ["Hari"],
         "chapters": ["Ch 2"], "source_text": "b"},
    ]
    edges = identity.build_identity_edges(entities, [])
    same = [e for e in edges if e["type"] == "same_as"
            and {e["src"], e["dst"]} == {"h1", "h2"}]
    assert not same


def test_avatar_alias_becomes_avatar_of_edge():
    # An alias "avatar of Vishnu" on Matsya → avatar_of edge to Vishnu, NOT merge
    entities = [
        {"id": "matsya", "name": "Matsya", "kind": "deity",
         "all_forms": ["Matsya", "Fish avatar"],
         "aliases": ["avatar of Vishnu", "Fish avatar"],
         "chapters": ["Ch 1"], "source_text": "garuda_v1"},
        {"id": "vishnu", "name": "Vishnu", "kind": "deity",
         "all_forms": ["Vishnu"], "aliases": [], "chapters": ["Ch 1"],
         "source_text": "garuda_v1"},
    ]
    edges = identity.build_identity_edges(entities, [])
    avatar = [e for e in edges if e["type"] == "avatar_of"]
    assert len(avatar) >= 1
    assert avatar[0]["src"] == "matsya"
    assert avatar[0]["dst"] == "vishnu"


def test_explicit_avatar_relationship_becomes_edge():
    # An LLM relationship "Krishna is_avatar_of Vishnu" → avatar_of edge
    entities = [
        {"id": "krishna", "name": "Krishna", "kind": "deity",
         "all_forms": ["Krishna"], "chapters": ["Ch 1"], "source_text": "a"},
        {"id": "vishnu", "name": "Vishnu", "kind": "deity",
         "all_forms": ["Vishnu"], "chapters": ["Ch 1"], "source_text": "a"},
    ]
    rels = [{"src": "Krishna", "rel": "is_avatar_of", "dst": "Vishnu",
             "src_id": "krishna", "dst_id": "vishnu"}]
    edges = identity.build_identity_edges(entities, rels)
    avatar = [e for e in edges if e["type"] == "avatar_of"
              and e["src"] == "krishna" and e["dst"] == "vishnu"]
    assert len(avatar) >= 1


def test_no_alias_chaining_merge():
    # The killer test: Buddha shares "Achyuta" with Vishnu, Vishnu shares "Hari"
    # with Brahma. In the OLD model all three merged. In the new model they stay
    # SEPARATE nodes — at most connected by adjudicated edges (not built here).
    entities = [
        {"id": "buddha", "name": "Buddha", "kind": "deity",
         "all_forms": ["Buddha", "Achyuta"], "chapters": ["Ch 1"], "source_text": "a"},
        {"id": "vishnu", "name": "Vishnu", "kind": "deity",
         "all_forms": ["Vishnu", "Achyuta", "Hari"], "chapters": ["Ch 2"], "source_text": "a"},
        {"id": "brahma", "name": "Brahma", "kind": "deity",
         "all_forms": ["Brahma", "Hari"], "chapters": ["Ch 3"], "source_text": "a"},
    ]
    edges = identity.build_identity_edges(entities, [])
    # No same_as edges should be created purely from shared aliases
    same = [e for e in edges if e["type"] == "same_as"]
    assert not same, f"shared aliases must NOT create same_as edges, got {same}"


def test_high_overlap_pairs_selected_for_reasoner():
    # The selector picks only pairs sharing >= threshold aliases (cost control)
    entities = [
        {"id": "a", "name": "A", "kind": "deity",
         "all_forms": ["A"] + [f"shared{i}" for i in range(20)],
         "chapters": [], "source_text": "x"},
        {"id": "b", "name": "B", "kind": "deity",
         "all_forms": ["B"] + [f"shared{i}" for i in range(20)],
         "chapters": [], "source_text": "x"},
        {"id": "c", "name": "C", "kind": "deity",
         "all_forms": ["C", "shared0"],  # only 1 shared
         "chapters": [], "source_text": "x"},
    ]
    pairs = identity.select_pairs_for_reasoner(entities, min_shared=5)
    keys = {frozenset(p["pair"]) for p in pairs}
    assert frozenset({"a", "b"}) in keys
    assert frozenset({"a", "c"}) not in keys  # below threshold


def test_envelope_shape():
    entities = [
        {"id": "rama@a", "name": "Rāma", "kind": "deity", "all_forms": ["Rāma"],
         "chapters": ["Ch 1"], "source_text": "a"},
        {"id": "rama@b", "name": "Rāma", "kind": "deity", "all_forms": ["Rāma"],
         "chapters": ["Ch 2"], "source_text": "b"},
    ]
    env = identity.run(entities, [])
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"]
    assert "identity_edges" in env["data"]
    assert "edge_type_counts" in env["data"]


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
    raise SystemExit(1 if failed else 0)
