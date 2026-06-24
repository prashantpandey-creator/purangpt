"""Tests-first (Rule 0, precondition A) for seeker_memory.warmth.

The warmth classifier is a PURE decision tree: (visit_days, days_since_last,
is_guest) -> familiarity tier + a hand-authored prompt directive. No I/O, no LLM,
no network — so every branch is deterministically assertable here.

Run:  venv/bin/python -m tools.seeker_memory.test_warmth   (must exit 0)
"""
from __future__ import annotations

import sys

from tools.seeker_memory.warmth import classify_warmth, TIERS


def _data(env):
    assert env["success"] is True, env
    assert env["errors"] == []
    return env["data"]


# ---- tier boundaries (visit_days thresholds) -----------------------------

def test_stranger_at_one_visit():
    d = _data(classify_warmth(visit_days=1))
    assert d["tier"] == "stranger"
    assert d["disclose_arc"] is False  # withhold specifics at the lowest tier


def test_acquainted_band():
    for v in (2, 3, 4):
        d = _data(classify_warmth(visit_days=v))
        assert d["tier"] == "acquainted", v


def test_known_band():
    for v in (5, 9, 14):
        d = _data(classify_warmth(visit_days=v))
        assert d["tier"] == "known", v
    # KNOWN is the first tier that discloses the arc as felt sense
    assert _data(classify_warmth(visit_days=5))["disclose_arc"] is True


def test_intimate_band():
    for v in (15, 40, 999):
        d = _data(classify_warmth(visit_days=v))
        assert d["tier"] == "intimate", v


def test_exact_boundaries_are_inclusive_lower():
    # 4 is the top of acquainted; 5 is the bottom of known
    assert _data(classify_warmth(visit_days=4))["tier"] == "acquainted"
    assert _data(classify_warmth(visit_days=5))["tier"] == "known"
    # 14 top of known; 15 bottom of intimate
    assert _data(classify_warmth(visit_days=14))["tier"] == "known"
    assert _data(classify_warmth(visit_days=15))["tier"] == "intimate"


# ---- the directive string is always present and warmth-as-recognition ----

def test_directive_present_and_nonempty_each_tier():
    for v in (1, 3, 9, 50):
        d = _data(classify_warmth(visit_days=v))
        assert isinstance(d["directive"], str) and d["directive"].strip()


def test_directive_never_claims_a_record():
    # the whole model: warmth-as-recognition, NEVER "you told me X on Tuesday"
    for v in (1, 3, 9, 50):
        d = _data(classify_warmth(visit_days=v))
        low = d["directive"].lower()
        assert "you told me" not in low
        assert "you said" not in low
        assert "last time you" not in low


# ---- 90-day recency decay drops exactly one tier -------------------------

def test_long_absence_drops_one_tier():
    # an INTIMATE seeker gone 100 days returns as KNOWN, glad-but-gentle
    d = _data(classify_warmth(visit_days=20, days_since_last=100))
    assert d["tier"] == "known"
    assert d["decayed"] is True
    assert "absence" in d["directive"].lower() or "return" in d["directive"].lower()


def test_decay_floors_at_stranger():
    # a STRANGER (already lowest) gone a year cannot drop below stranger
    d = _data(classify_warmth(visit_days=1, days_since_last=400))
    assert d["tier"] == "stranger"
    assert d["decayed"] is True  # the flag still records that decay applied


def test_no_decay_within_90_days():
    d = _data(classify_warmth(visit_days=20, days_since_last=89))
    assert d["tier"] == "intimate"
    assert d["decayed"] is False


def test_decay_at_exactly_90_does_not_fire():
    # strictly greater-than 90 (90 itself is still fresh)
    d = _data(classify_warmth(visit_days=20, days_since_last=90))
    assert d["tier"] == "intimate"
    assert d["decayed"] is False


# ---- guests are pinned to stranger by design -----------------------------

def test_guest_pinned_to_stranger_regardless_of_visit_days():
    # a guest cannot earn warmth (no durable identity) even with high counts
    d = _data(classify_warmth(visit_days=999, is_guest=True))
    assert d["tier"] == "stranger"
    assert d["disclose_arc"] is False


# ---- envelope / error contract -------------------------------------------

def test_zero_or_negative_visit_days_is_an_error_envelope():
    env = classify_warmth(visit_days=0)
    assert env["success"] is False
    assert env["data"] is None
    assert env["errors"] and env["errors"][0]["code"] == "bad_visit_days"


def test_negative_days_since_last_is_an_error_envelope():
    env = classify_warmth(visit_days=5, days_since_last=-3)
    assert env["success"] is False
    assert env["errors"][0]["code"] == "bad_days_since_last"


def test_metadata_echoes_inputs():
    env = classify_warmth(visit_days=7, days_since_last=10)
    assert env["metadata"]["visit_days"] == 7
    assert env["metadata"]["days_since_last"] == 10


def test_tiers_registry_is_ordered_and_complete():
    # the module exposes the 4 tiers in ascending order for callers/eval
    assert [t["name"] for t in TIERS] == [
        "stranger", "acquainted", "known", "intimate"
    ]


def _run():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
