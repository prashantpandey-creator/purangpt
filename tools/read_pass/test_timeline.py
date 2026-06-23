"""Tests-first for the cosmic timeline layer.

The Puranas have their own timescale — cosmic cycles (Kalpa → Manvantara →
Mahā-Yuga → Yuga). Every event is implicitly or explicitly placed on this
scale. This module:

1. Defines the canonical Puranic time hierarchy as a structured reference
2. Extracts temporal placement from existing graph data (entities, edges,
   teachings that mention Yugas/Kalpas/Manvantaras)
3. Propagates epochs through the graph (Krishna → Dvāpara, therefore Arjuna → Dvāpara)
4. Uses the reasoning model for ambiguous placements (Phase 2)

The timeline is NOT historical — it's the Puranas' own internal coordinate
system. An event's "time" is (Kalpa, Manvantara, Mahā-Yuga, Yuga), not a
year in CE/BCE.

Run: venv/bin/python -m tools.read_pass.test_timeline   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import timeline


def test_cosmic_hierarchy_is_well_ordered():
    h = timeline.COSMIC_HIERARCHY
    assert h["kalpa"]["sub_unit"] == "manvantara"
    assert h["manvantara"]["sub_unit"] == "maha_yuga"
    assert h["maha_yuga"]["sub_unit"] == "yuga"
    yugas = h["yuga"]["sequence"]
    assert yugas == ["satya", "treta", "dvapara", "kali"]


def test_epoch_ordering():
    e1 = timeline.Epoch(yuga="satya")
    e2 = timeline.Epoch(yuga="treta")
    e3 = timeline.Epoch(yuga="dvapara")
    e4 = timeline.Epoch(yuga="kali")
    assert e1 < e2 < e3 < e4
    e5 = timeline.Epoch(manvantara=1, yuga="kali")
    e6 = timeline.Epoch(manvantara=7, yuga="satya")
    assert e5 < e6


def test_canonical_avatar_placements():
    placements = timeline.AVATAR_EPOCH_MAP
    assert placements["rama"].yuga == "treta"
    assert placements["krishna"].yuga == "dvapara"
    assert placements["narasimha"].yuga == "satya"
    assert placements["parashurama"].yuga == "treta"


def test_place_entity_by_known_avatar():
    events = [
        {"entity": "Rāma", "kind": "deity", "predicates": ["avatar"]},
    ]
    placed = timeline.place_events(events)
    assert len(placed) >= 1
    assert placed[0]["epoch"].yuga == "treta"
    assert placed[0]["method"] == "avatar_map"


def test_place_entity_by_yuga_keyword():
    events = [
        {"entity": "Kali personified", "kind": "demon",
         "context": "appears at the onset of Kali Yuga"},
    ]
    placed = timeline.place_events(events)
    assert len(placed) >= 1
    assert placed[0]["epoch"].yuga == "kali"
    assert placed[0]["method"] == "keyword"


def test_extract_temporal_markers_from_graph():
    entities = [
        {"id": "rama", "name": "Rāma", "kind": "deity",
         "all_forms": ["Rāma", "Rāghava"], "chapters": ["Ch 10"]},
        {"id": "kali", "name": "Kali", "kind": "demon",
         "all_forms": ["Kali"], "chapters": ["Ch 1"]},
    ]
    edges = [
        {"src": "rama", "rel": "avatar", "dst": "vishnu",
         "src_name": "Rāma", "dst_name": "Vishnu",
         "chapters": ["Ch 10"], "verse_ranges": []},
        {"src": "kali", "rel": "worshipped_in_yuga", "dst": "kali_yuga",
         "src_name": "Kali", "dst_name": "Kali Yuga",
         "chapters": ["Ch 1"], "verse_ranges": []},
    ]
    markers = timeline.extract_temporal_markers(entities, edges)
    names = {m["entity"] for m in markers}
    assert "Rāma" in names


def test_propagate_epoch_through_graph():
    """If Krishna is placed in Dvāpara, entities sharing chapters/edges
    with Krishna should inherit Dvāpara via propagation."""
    entities = [
        {"id": "krishna", "name": "Krishna", "kind": "deity",
         "all_forms": ["Krishna"], "chapters": ["Ch 10", "Ch 50"]},
        {"id": "arjuna", "name": "Arjuna", "kind": "warrior",
         "all_forms": ["Arjuna"], "chapters": ["Ch 10"]},
        {"id": "brahma", "name": "Brahma", "kind": "deity",
         "all_forms": ["Brahma"], "chapters": ["Ch 3"]},
    ]
    edges = [
        {"src": "krishna", "rel": "friend", "dst": "arjuna",
         "src_name": "Krishna", "dst_name": "Arjuna",
         "chapters": ["Ch 10"], "verse_ranges": []},
    ]
    markers = timeline.extract_temporal_markers(entities, edges)
    placed = timeline.place_events(markers)
    placements = {p["entity"]: p for p in placed}
    assert placements["Krishna"]["epoch"].yuga == "dvapara"
    # propagate
    propagated = timeline.propagate_epochs(placed, edges)
    prop_map = {p["entity"]: p for p in propagated}
    assert prop_map["Arjuna"]["epoch"].yuga == "dvapara"
    assert prop_map["Arjuna"]["method"] == "propagated"
    # Brahma has no edge to Krishna and chapter 3 ≠ chapter 10, so stays unplaced
    assert prop_map["Brahma"]["method"] == "unplaced"


def test_envelope_shape():
    events = [
        {"entity": "Rāma", "kind": "deity", "predicates": ["avatar"]},
    ]
    env = timeline.run(events)
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"]
    assert len(env["data"]["placed_events"]) >= 1
    assert "timeline_summary" in env["data"]


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
