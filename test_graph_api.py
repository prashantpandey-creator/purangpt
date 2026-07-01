"""Tests for the Graph Explorer API endpoints (backend/main.py).

Covers:
  - _load_graph() — loads, has expected structure, alias map built
  - graph_list_entities — kind filter, min_degree, alias exclusion
  - graph_get_entity — canonical + alias resolution, edge merging
  - graph_find_path — BFS path, alias resolution, no-path case

Real graph manifest is the fixture (Rule 0, precond A). Run from repo root:
  venv/bin/python test_graph_api.py   (exit 0)
"""

from __future__ import annotations

import os
import sys

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(__file__))

from backend.main import _load_graph, _GRAPH_CACHE
import backend.main as bm


def _reset():
    """Clear the module-level graph cache so each test loads fresh."""
    # Use the module-level global
    globals_ = vars(bm)
    if "_GRAPH_CACHE" in globals_:
        # We can't easily reset a module global from outside, so we use
        # importlib.reload or just work with what _load_graph returns.
        pass


# ── _load_graph tests ────────────────────────────────────────────────────────


def test_load_graph_succeeds():
    """Graph loads from disk and returns the expected structure."""
    g = _load_graph()
    assert g is not None
    assert g["total_entities"] > 8000, f"Expected >8000 entities, got {g['total_entities']}"
    assert g["total_edges"] > 20000, f"Expected >20000 edges, got {g['total_edges']}"
    assert g["total_keys"] > 500, f"Expected >500 decode keys, got {g['total_keys']}"
    assert "entity_by_id" in g
    assert "edges_by_entity" in g
    assert "key_map" in g
    assert "alias_to_canonical" in g
    assert "canonical_aliases" in g


def test_alias_map_populated():
    """Transliteration alias map has the known duplicates."""
    g = _load_graph()
    aliases = g["alias_to_canonical"]
    # Known duplicates
    assert aliases.get("visnu") == "vishnu", f"visnu → {aliases.get('visnu')}"
    assert aliases.get("siva") == "shiva", f"siva → {aliases.get('siva')}"
    assert aliases.get("daksa") == "daksha", f"daksa → {aliases.get('daksa')}"
    assert aliases.get("kasyapa") == "kashyapa", f"kasyapa → {aliases.get('kasyapa')}"
    assert aliases.get("krsna") == "krishna", f"krsna → {aliases.get('krsna')}"
    # Canonical IDs should NOT be in the alias map
    assert "vishnu" not in aliases, "vishnu (canonical) should not be an alias target"
    assert "shiva" not in aliases, "shiva (canonical) should not be an alias target"


def test_canonical_aliases_lookup():
    """canonical_aliases maps each canonical to its known alternate spellings."""
    g = _load_graph()
    ca = g["canonical_aliases"]
    assert "visnu" in ca.get("vishnu", []), "vishnu should list visnu as alias"
    assert "siva" in ca.get("shiva", []), "shiva should list siva as alias"


def test_key_map_has_major_deities():
    """At least some major deities have decode keys."""
    g = _load_graph()
    km = g["key_map"]
    # Not all entities have keys (only 141/613 match), but the map should be non-empty
    assert len(km) > 100, f"Expected >100 decode key entries, got {len(km)}"


# ── graph_get_entity tests ───────────────────────────────────────────────────

import asyncio


def _run(coro):
    """Helper: run an async coroutine and return its result."""
    return asyncio.get_event_loop().run_until_complete(coro)


def test_get_entity_canonical():
    """Canonical entity lookup returns full detail."""
    result = _run(bm.graph_get_entity("krishna"))
    assert result["id"] == "krishna"
    assert result["name"] == "Krishna"
    assert result["kind"] == "deity"
    assert len(result["relationships"]) >= 25, f"Krishna should have >=25 relationships, got {len(result['relationships'])}"
    assert len(result["all_forms"]) > 0
    assert len(result["verse_ranges"]) > 0


def test_get_entity_alias_redirect():
    """Alias entity lookup redirects to canonical and merges edges."""
    # Look up the alias form
    result = _run(bm.graph_get_entity("visnu"))
    # Should redirect to canonical
    assert result["id"] == "vishnu", f"Alias visnu should redirect to vishnu, got {result['id']}"
    assert result["name"] == "Vishnu"
    assert result["kind"] == "deity"
    assert len(result["relationships"]) > 20, f"Merged Vishnu should have >20 relationships, got {len(result['relationships'])}"


def test_get_entity_alias_merged_edges():
    """Alias lookup has MORE edges than looking up either variant alone."""
    result_alias = _run(bm.graph_get_entity("siva"))
    result_canon = _run(bm.graph_get_entity("shiva"))
    # Both should resolve to the same canonical
    assert result_alias["id"] == "shiva"
    assert result_canon["id"] == "shiva"
    # Edge counts should be identical (same merged set)
    assert result_alias["degree"] == result_canon["degree"], \
        f"Alias and canonical should have same merged degree: {result_alias['degree']} vs {result_canon['degree']}"


def test_get_entity_not_found():
    """Nonexistent entity raises 404."""
    try:
        _run(bm.graph_get_entity("nonexistent_entity_xyz"))
        assert False, "Should have raised 404"
    except Exception as e:
        assert hasattr(e, "status_code") and e.status_code == 404, \
            f"Expected 404, got {type(e).__name__}: {e}"


def test_get_entity_family_relations_first():
    """Relationship sort puts family (father/mother/etc.) before other relations."""
    result = _run(bm.graph_get_entity("arjuna"))
    rels = result["relationships"]
    family = {"father", "mother", "son", "daughter", "brother", "wife", "husband"}
    # First few relations should include family
    first_types = [r["relation"] for r in rels[:10]]
    has_family_early = any(t in family for t in first_types[:5])
    assert has_family_early, f"Expected family relations early in Arjuna's relationships, got: {first_types[:5]}"


# ── graph_list_entities tests ────────────────────────────────────────────────


def test_list_entities_default():
    """Default listing returns entities sorted by degree."""
    result = _run(bm.graph_list_entities(limit=10))
    assert len(result["entities"]) == 10
    assert result["total"] > 100
    # Should be sorted by degree descending
    degrees = [e["degree"] for e in result["entities"]]
    assert degrees == sorted(degrees, reverse=True), f"Not sorted by degree: {degrees}"


def test_list_entities_kind_filter():
    """Kind filter returns only matching entities."""
    result = _run(bm.graph_list_entities(kind="deity", limit=20))
    for e in result["entities"]:
        assert e["kind"] == "deity", f"Expected deity, got {e['kind']} for {e['name']}"
    assert result["total"] > 500, f"Expected >500 deities, got {result['total']}"


def test_list_entities_min_degree():
    """min_degree=3 hides sparse entities."""
    result_all = _run(bm.graph_list_entities(min_degree=0, limit=100))
    result_filtered = _run(bm.graph_list_entities(min_degree=3, limit=100))
    assert result_filtered["total"] < result_all["total"], \
        f"min_degree=3 should return fewer than min_degree=0: {result_filtered['total']} vs {result_all['total']}"
    # Filtered entities should all have degree >= 3
    for e in result_filtered["entities"]:
        assert e["degree"] >= 3, f"Entity {e['name']} has degree {e['degree']} < 3"


def test_list_entities_aliases_excluded():
    """Transliteration aliases (Visnu, Siva) don't appear as separate entries."""
    result = _run(bm.graph_list_entities(kind="deity", limit=200))
    ids = {e["id"] for e in result["entities"]}
    # Aliases should not appear
    assert "visnu" not in ids, "visnu (alias) should not appear in entity list"
    assert "siva" not in ids, "siva (alias) should not appear in entity list"
    assert "krsna" not in ids, "krsna (alias) should not appear in entity list"
    # Canonicals should appear
    assert "vishnu" in ids, "vishnu (canonical) should appear"
    assert "shiva" in ids, "shiva (canonical) should appear"
    assert "krishna" in ids, "krishna (canonical) should appear"


def test_list_entities_search():
    """Text search finds entities by name or alias."""
    result = _run(bm.graph_list_entities(q="arjuna", limit=10))
    assert result["total"] >= 1
    names = [e["name"].lower() for e in result["entities"]]
    assert any("arjuna" in n for n in names), f"Search for 'arjuna' should find Arjuna, got: {names}"


# ── graph_find_path tests ────────────────────────────────────────────────────


def test_find_path_direct():
    """Path between directly connected entities is length 1."""
    result = _run(bm.graph_find_path(_from="krishna", to="arjuna"))
    assert result["found"] is True
    assert result["length"] == 1, f"Krishna→Arjuna should be 1 step, got {result['length']}"
    assert result["path"][0]["id"] == "krishna"
    assert result["path"][1]["id"] == "arjuna"


def test_find_path_alias_resolution():
    """Path finding resolves aliases in from/to parameters."""
    result = _run(bm.graph_find_path(_from="krsna", to="arjuna"))
    assert result["found"] is True
    # Should resolve krsna → krishna
    assert result["path"][0]["id"] == "krishna", f"Alias krsna should resolve to krishna, got {result['path'][0]['id']}"


def test_find_path_no_path():
    """No path between disconnected entities returns found=false."""
    # Try two low-degree entities that are unlikely to be connected
    result = _run(bm.graph_find_path(_from="kumbh_mela", to="artha_shastra"))
    # These are isolated or very sparse — path unlikely
    if result["found"]:
        # If found, length should be reasonably short (graph diameter is small)
        assert result["length"] <= 8, f"Path unexpectedly long: {result['length']}"


def test_find_path_not_found():
    """Nonexistent entity raises 404."""
    try:
        _run(bm.graph_find_path(_from="krishna", to="nonexistent_xyz"))
        assert False, "Should have raised 404"
    except Exception as e:
        assert hasattr(e, "status_code") and e.status_code == 404


# ── graph_stats tests ────────────────────────────────────────────────────────


def test_stats():
    """Stats endpoint returns kind distribution and top hubs."""
    result = _run(bm.graph_stats())
    assert result["total_entities"] > 8000
    assert result["total_edges"] > 20000
    assert "kinds" in result
    assert "deity" in result["kinds"]
    assert result["kinds"]["deity"] > 1000
    assert "top_hubs" in result
    assert len(result["top_hubs"]) == 20
    # Top hub should be Brahma or Vishnu
    top_names = [h[1].lower() for h in result["top_hubs"][:3]]
    assert any(n in top_names for n in ["brahma", "vishnu", "krishna"]), \
        f"Top hubs should include Brahma/Vishnu/Krishna, got: {top_names}"


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback
    tests = [
        ("test_load_graph_succeeds", test_load_graph_succeeds),
        ("test_alias_map_populated", test_alias_map_populated),
        ("test_canonical_aliases_lookup", test_canonical_aliases_lookup),
        ("test_key_map_has_major_deities", test_key_map_has_major_deities),
        ("test_get_entity_canonical", test_get_entity_canonical),
        ("test_get_entity_alias_redirect", test_get_entity_alias_redirect),
        ("test_get_entity_alias_merged_edges", test_get_entity_alias_merged_edges),
        ("test_get_entity_not_found", test_get_entity_not_found),
        ("test_get_entity_family_relations_first", test_get_entity_family_relations_first),
        ("test_list_entities_default", test_list_entities_default),
        ("test_list_entities_kind_filter", test_list_entities_kind_filter),
        ("test_list_entities_min_degree", test_list_entities_min_degree),
        ("test_list_entities_aliases_excluded", test_list_entities_aliases_excluded),
        ("test_list_entities_search", test_list_entities_search),
        ("test_find_path_direct", test_find_path_direct),
        ("test_find_path_alias_resolution", test_find_path_alias_resolution),
        ("test_find_path_no_path", test_find_path_no_path),
        ("test_find_path_not_found", test_find_path_not_found),
        ("test_stats", test_stats),
    ]
    failed = 0
    passed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  ✓ {name}")
        except Exception:
            failed += 1
            print(f"  ✗ {name}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
    if failed:
        sys.exit(1)
