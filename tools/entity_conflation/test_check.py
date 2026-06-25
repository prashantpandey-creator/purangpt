"""entity_conflation — tests-first (Rule 0, precondition A).

Detect graph nodes that CONFLATE distinct beings sharing an ambiguous bare alias.
The Ram/Parashuram bug: one 'rama' node carries Dasharatha's-son AND Jamadagni's-son
AND Balarama forms — three distinct figures collapsed by the shared bare name "Rama".

The detector must FLAG true conflations (incompatible identity markers in one node)
WITHOUT flagging legitimate shared epithets (Vishnu's 1000 names on Vishnu-cluster nodes).

Run: venv/bin/python -m tools.entity_conflation.test_check   (from purangpt/ repo root)
"""
from __future__ import annotations

import sys

from tools.entity_conflation.check import (
    incompatible_markers,
    detect_conflations,
    run,
)


def test_incompatible_markers_flags_two_parentages():
    # a node claiming two different fathers = two beings
    forms = ["Rama", "Dasharatha's son", "Jamadagni's son"]
    groups = incompatible_markers(forms)
    assert len(groups) >= 2, f"should detect 2 distinct parentages, got {groups}"


def test_clean_single_identity_not_conflated():
    # one coherent being (only Dasharatha-Rama markers) must NOT be flagged as a conflation,
    # even though it triggers both the rama_dasharatha signature and a dasharatha patronym —
    # those point at the SAME being, not two.
    entities = [{"id": "rama", "name": "Rama",
                 "all_forms": ["Rama", "Dasharatha Nandana", "Raghava", "Lord Rama"]}]
    flagged = detect_conflations(entities)
    assert not flagged, f"single coherent identity must not be flagged, got {flagged}"


def test_detect_flags_rama_parashurama_conflation():
    entities = [
        {"id": "rama", "name": "Rama",
         "all_forms": ["Rama", "Dasharatha's son", "Parashurama", "Jamadagnya", "Balarama"]},
        {"id": "hanuman", "name": "Hanuman", "all_forms": ["Hanuman", "Anjaneya"]},
    ]
    flagged = detect_conflations(entities)
    ids = {f["id"] for f in flagged}
    assert "rama" in ids, "the conflated rama node must be flagged"
    assert "hanuman" not in ids, "a clean node must not be flagged"


def test_detect_skips_legit_epithet_cluster():
    # Vishnu carrying many of his OWN sahasranama names is NOT a conflation
    entities = [
        {"id": "vishnu", "name": "Vishnu",
         "all_forms": ["Vishnu", "Achyuta", "Govinda", "Madhava", "Keshava", "Hari"]},
    ]
    flagged = detect_conflations(entities)
    assert not flagged, "a coherent epithet cluster must not be flagged as conflation"


def test_detect_reports_the_conflicting_groups():
    entities = [
        {"id": "rama", "name": "Rama",
         "all_forms": ["Rama", "Dasharatha's son", "Jamadagni's son"]},
    ]
    flagged = detect_conflations(entities)
    assert flagged
    assert "groups" in flagged[0]
    assert len(flagged[0]["groups"]) >= 2


def test_envelope_shape():
    env = run()
    assert "success" in env and "data" in env and "metadata" in env and "errors" in env
    if env["success"]:
        d = env["data"]
        assert "n_conflated" in d
        assert "conflations" in d


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
