"""Tests-first for LLM-powered entity resolution (Rule 0 precond A).

The graph's mechanical alias merge (union-find) catches explicit alias
declarations. But IMPLICIT identities — "Pārtha" = Arjuna because Pṛthā =
Kuntī = Arjuna's mother — require REASONING. That's where the reasoning
model (deepseek-v4-pro) earns its keep.

This module takes the graph's alias_overlaps() + ambiguous entity pairs
and asks the reasoner to ADJUDICATE each one: same entity, avatar relation,
coincidental name, or context-dependent.

Run: venv/bin/python -m tools.read_pass.test_resolve   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import resolve


# fake entities as the graph would produce
_KRISHNA = {"id": "krishna", "name": "Krishna", "kind": "deity",
            "all_forms": ["Krishna", "Kṛṣṇa", "Govinda", "Hari", "Mādhava"],
            "chapters": ["Ch 1", "Ch 10", "Ch 50"]}
_VISHNU = {"id": "vishnu", "name": "Vishnu", "kind": "deity",
           "all_forms": ["Vishnu", "Hari", "Narayana", "Achyuta"],
           "chapters": ["Ch 3", "Ch 8", "Ch 15"]}
_VASUDEVA_FATHER = {"id": "vasudeva", "name": "Vasudeva", "kind": "kshatriya",
                    "all_forms": ["Vasudeva", "Vāsudeva", "Ānakadundubhi"],
                    "chapters": ["Ch 1", "Ch 10"]}


def _fake_reasoner(prompt, model, key):
    """Deterministic fake — returns a canned adjudication for the Krishna/Vishnu pair."""
    return json.dumps({
        "adjudications": [
            {"entity_a": "krishna", "entity_b": "vishnu",
             "verdict": "avatar_relation",
             "reasoning": "Krishna is the avatāra of Vishnu per Bhāgavata theology. "
                          "Shared epithets like Hari apply to both but in different contexts.",
             "shared_aliases_assessment": {
                 "hari": "both — general epithet of the supreme, used for both",
                 "achyuta": "primarily Krishna in direct address, Vishnu in cosmological context"
             }},
        ]
    })


def test_resolve_returns_adjudications_for_overlap_pairs():
    pairs = [
        (("krishna", "vishnu"), {"hari", "achyuta"}),
    ]
    entities = [_KRISHNA, _VISHNU]
    result = resolve.resolve_overlaps(pairs, entities, "fake-key",
                                      caller=_fake_reasoner)
    assert result["success"]
    adjs = result["data"]["adjudications"]
    assert len(adjs) == 1
    assert adjs[0]["verdict"] == "avatar_relation"
    assert "hari" in str(adjs[0].get("shared_aliases_assessment", {})).lower()


def test_resolve_prompt_includes_entity_evidence():
    pairs = [(("krishna", "vishnu"), {"hari"})]
    entities = [_KRISHNA, _VISHNU]
    prompt = resolve.build_prompt(pairs, entities)
    # prompt must include the entity forms and shared aliases as evidence
    assert "Krishna" in prompt and "Vishnu" in prompt
    assert "Hari" in prompt or "hari" in prompt
    assert "avatar" in prompt.lower() or "identity" in prompt.lower()


def test_resolve_envelope_shape():
    pairs = [(("krishna", "vishnu"), {"hari"})]
    entities = [_KRISHNA, _VISHNU]
    result = resolve.resolve_overlaps(pairs, entities, "fake-key",
                                      caller=_fake_reasoner)
    assert set(result.keys()) == {"success", "data", "metadata", "errors"}
    assert result["data"]["n_pairs_submitted"] == 1


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
