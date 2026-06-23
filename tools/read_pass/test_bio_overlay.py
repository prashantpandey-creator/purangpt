"""Tests-first for the biography overlay (Rule 0 precond A).

Daddy: "anything we learned from the biography to implement? surprised you didn't."
Caught. The biography distilled 285 entity-encounters + 230 places but they sat
in a JSON trophy. This overlay JOINS them onto the Puranic graph:

  - guruji_encountered: deity/being nodes get the realized-yogi EXPERIENTIAL layer
    (Shiva: 44 lived encounters — what Shiva IS to a yogi, not just "in Skanda P.")
  - tirtha places: 230 sacred sites become place-nodes, linked where a graph deity
    is worshipped there (Govardhan = Krishna's hill AND Guruji's ashram)

This is the join across the abstract-texts / lived-lineage divide. Deterministic
name-matching against the existing graph entities — zero LLM.

Run: venv/bin/python -m tools.read_pass.test_bio_overlay   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import bio_overlay


_GRAPH_ENTITIES = [
    {"id": "shiva", "name": "Shiva", "kind": "deity",
     "all_forms": ["Shiva", "Mahadev", "Rudra"], "chapters": ["c1"]},
    {"id": "krishna", "name": "Krishna", "kind": "deity",
     "all_forms": ["Krishna", "Govinda"], "chapters": ["c2"]},
    {"id": "random_king", "name": "Some King", "kind": "king",
     "all_forms": ["Some King"], "chapters": ["c3"]},
]

_BIO = {
    "entity_encounters": [
        {"entity": "Shiva (Mahadev)", "encounter": "Vision at Devaldhar on Nanda Devi"},
        {"entity": "Shiva", "encounter": "Shivalingam appeared over his head"},
        {"entity": "Krishna", "encounter": "shadow revealed in an aura"},
        {"entity": "Babaji", "encounter": "recognized as immortal master"},  # not in graph
    ],
    "places": ["Govardhan", "Kashi Vishwanath Temple", "Mehandipur"],
}


def test_encounters_attach_to_matching_graph_entities():
    overlay = bio_overlay.build_overlay(_GRAPH_ENTITIES, _BIO)
    enc = overlay["entity_encounters"]
    # Shiva node should get BOTH shiva encounters
    assert "shiva" in enc
    assert len(enc["shiva"]) == 2
    # Krishna gets one
    assert len(enc["krishna"]) == 1


def test_unmatched_encounters_recorded_separately():
    # Babaji isn't in this graph — must not be lost, parked in unmatched
    overlay = bio_overlay.build_overlay(_GRAPH_ENTITIES, _BIO)
    unmatched = {u["entity"].lower() for u in overlay["unmatched_encounters"]}
    assert any("babaji" in u for u in unmatched)


def test_king_with_no_encounters_gets_nothing():
    overlay = bio_overlay.build_overlay(_GRAPH_ENTITIES, _BIO)
    assert "random_king" not in overlay["entity_encounters"]


def test_places_become_tirtha_nodes():
    overlay = bio_overlay.build_overlay(_GRAPH_ENTITIES, _BIO)
    tirthas = {t["name"] for t in overlay["tirthas"]}
    assert "Govardhan" in tirthas
    assert "Mehandipur" in tirthas


def test_encounter_count_summary():
    overlay = bio_overlay.build_overlay(_GRAPH_ENTITIES, _BIO)
    # most-encountered entity surfaces in the summary
    top = overlay["summary"]["most_encountered"]
    assert top[0]["entity"] == "Shiva"
    assert top[0]["n"] == 2


def test_envelope_shape():
    env = bio_overlay.run(_GRAPH_ENTITIES, _BIO)
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"]
    assert "entity_encounters" in env["data"]
    assert "tirthas" in env["data"]


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
