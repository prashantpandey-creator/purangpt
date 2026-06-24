"""Behaviour test for the seeker-memory READ path (the earned-warmth Phase 1 wire
in backend/main.py): build_seeker_memory + _maybe_update_seeker_warmth.

Run: venv/bin/python test_seeker_memory_read.py   (from purangpt/ repo root)

py_compile + the slot/kwarg dry-run prove the prompt won't KeyError. This proves
the BEHAVIOUR a compile can't:
  build_seeker_memory:
    1. flag OFF                  → "" (byte-identical prompt; ships dark).
    2. guest (no user_id)        → "" (signed-in only; no earned identity).
    3. STRANGER tier             → warmth line ONLY, arc WITHHELD even if a profile exists.
    4. KNOWN tier + profile      → warmth line + arc, both present.
    5. KNOWN tier, blank profile → warmth line only (no empty "felt sense:" dangling).
    6. every non-empty block     → carries the DO-NOT-REVEAL header + present-wins INVARIANT.
    7. DB down (stats raise)     → "" (fail-graceful, never raises).
  _maybe_update_seeker_warmth:
    8. flag OFF / guest          → no bump, no profile gen.
    9. below KNOWN tier          → bumps the day, but does NOT generate a profile (saves the LLM call).
   10. KNOWN + stale             → bumps AND generates + saves the profile.

We monkeypatch session_manager so nothing hits the DB or network.
"""
import os
import sys
import asyncio

os.environ.setdefault("SEEKER_MEMORY_ENABLED", "0")

import backend.main as main  # noqa: E402


class _FakeSM:
    """Scriptable stand-in: returns canned warmth signals, records writes."""
    def __init__(self, visit_days=1, days_since_last=None, profile="",
                 profile_stale=True, stats_raise=False):
        self._visit_days = visit_days
        self._dsl = days_since_last
        self._profile = profile
        self._profile_stale = profile_stale
        self._stats_raise = stats_raise
        self.bumps = []
        self.profile_saves = []
        self.generate_calls = 0

    def get_visit_stats(self, user_id):
        if self._stats_raise:
            raise RuntimeError("db down")
        return (self._visit_days, self._dsl)

    def get_seeker_profile(self, user_id):
        return self._profile

    def bump_visit_day(self, user_id, tz="UTC"):
        self.bumps.append((user_id, tz))
        return True

    def seeker_profile_stale(self, user_id, max_age_minutes=1440):
        return (self._profile_stale, self._profile)

    async def generate_user_profile(self, user_id, limit=20):
        self.generate_calls += 1
        return "Daily meditator now; restlessness fading."

    def save_seeker_profile(self, user_id, profile):
        self.profile_saves.append((user_id, profile))
        return True


def _run(coro):
    return asyncio.run(coro)


def _patch(sm):
    orig = main.session_manager
    main.session_manager = sm
    def restore():
        main.session_manager = orig
    return restore


# ---- build_seeker_memory --------------------------------------------------

def test_flag_off_returns_empty():
    main.SEEKER_MEMORY_ENABLED = False
    restore = _patch(_FakeSM(visit_days=99, profile="rich arc"))
    try:
        assert _run(main.build_seeker_memory("u1")) == ""
    finally:
        restore()
    print("ok: flag_off_returns_empty")


def test_guest_returns_empty():
    main.SEEKER_MEMORY_ENABLED = True
    restore = _patch(_FakeSM(visit_days=99, profile="rich arc"))
    try:
        assert _run(main.build_seeker_memory(None)) == ""   # no user_id = guest
        assert _run(main.build_seeker_memory("")) == ""
    finally:
        restore()
    print("ok: guest_returns_empty")


def test_stranger_tier_withholds_arc():
    main.SEEKER_MEMORY_ENABLED = True
    # visit_days=1 = stranger; a profile EXISTS but must NOT be disclosed.
    restore = _patch(_FakeSM(visit_days=1, profile="They grieve a death and seek stillness."))
    try:
        block = _run(main.build_seeker_memory("u2"))
        assert block != "", "stranger still gets a warmth line"
        assert "A felt sense of this person:" not in block, "stranger must NOT disclose the arc"
        assert "grieve" not in block.lower()
        assert "INVARIANT" in block
    finally:
        restore()
    print("ok: stranger_tier_withholds_arc")


# The block's arc LINE has this exact prefix; the KNOWN directive happens to use
# the words "felt sense" too, so we assert on the line prefix, not the bare phrase.
_ARC_PREFIX = "A felt sense of this person:"


def test_known_tier_discloses_arc():
    main.SEEKER_MEMORY_ENABLED = True
    restore = _patch(_FakeSM(visit_days=9, profile="They grieve a death and seek stillness."))
    try:
        block = _run(main.build_seeker_memory("u3"))
        assert _ARC_PREFIX in block, "known tier discloses the arc line"
        assert "grieve" in block.lower()
        assert "INVARIANT" in block
    finally:
        restore()
    print("ok: known_tier_discloses_arc")


def test_known_tier_blank_profile_no_dangling_arc():
    main.SEEKER_MEMORY_ENABLED = True
    # known tier but the profile is the placeholder → no arc LINE injected
    restore = _patch(_FakeSM(visit_days=9, profile="New seeker. No established philosophical baseline yet."))
    try:
        block = _run(main.build_seeker_memory("u4"))
        assert block != ""
        assert _ARC_PREFIX not in block, "placeholder profile must not become an arc line"
    finally:
        restore()
    print("ok: known_tier_blank_profile_no_dangling_arc")


def test_block_has_donotreveal_header_and_invariant():
    main.SEEKER_MEMORY_ENABLED = True
    restore = _patch(_FakeSM(visit_days=20, profile="A long companion on the path."))
    try:
        block = _run(main.build_seeker_memory("u5"))
        low = block.lower()
        assert "never reveal" in low, "must carry the DO-NOT-REVEAL header"
        assert "you told me" in low, "header explicitly forbids the phrase 'you told me'"
        assert "present wins" in low, "must carry the present-turn-wins invariant"
    finally:
        restore()
    print("ok: block_has_donotreveal_header_and_invariant")


def test_db_down_returns_empty_never_raises():
    main.SEEKER_MEMORY_ENABLED = True
    restore = _patch(_FakeSM(stats_raise=True))
    try:
        assert _run(main.build_seeker_memory("u6")) == ""   # swallowed, no raise
    finally:
        restore()
    print("ok: db_down_returns_empty")


# ---- _maybe_update_seeker_warmth -----------------------------------------

def test_warmth_update_flag_off_noop():
    main.SEEKER_MEMORY_ENABLED = False
    sm = _FakeSM(visit_days=9)
    restore = _patch(sm)
    try:
        _run(main._maybe_update_seeker_warmth("u7"))
        assert sm.bumps == [] and sm.generate_calls == 0
    finally:
        restore()
    print("ok: warmth_update_flag_off_noop")


def test_warmth_update_guest_noop():
    main.SEEKER_MEMORY_ENABLED = True
    sm = _FakeSM(visit_days=9)
    restore = _patch(sm)
    try:
        _run(main._maybe_update_seeker_warmth(None))
        assert sm.bumps == [] and sm.generate_calls == 0
    finally:
        restore()
    print("ok: warmth_update_guest_noop")


def test_warmth_update_below_known_bumps_but_no_profile():
    main.SEEKER_MEMORY_ENABLED = True
    # visit_days 3 = acquainted (below KNOWN=5) → bump the day, but DON'T burn an LLM call
    sm = _FakeSM(visit_days=3, profile_stale=True)
    restore = _patch(sm)
    try:
        _run(main._maybe_update_seeker_warmth("u8"))
        assert sm.bumps == [("u8", "UTC")], "must still bump the visit day"
        assert sm.generate_calls == 0, "below KNOWN must NOT generate a profile"
        assert sm.profile_saves == []
    finally:
        restore()
    print("ok: warmth_update_below_known_bumps_but_no_profile")


def test_warmth_update_known_and_stale_generates_profile():
    main.SEEKER_MEMORY_ENABLED = True
    sm = _FakeSM(visit_days=9, profile_stale=True)
    restore = _patch(sm)
    try:
        _run(main._maybe_update_seeker_warmth("u9"))
        assert sm.bumps == [("u9", "UTC")]
        assert sm.generate_calls == 1, "known + stale must generate the arc"
        assert len(sm.profile_saves) == 1
        assert sm.profile_saves[0][0] == "u9"
    finally:
        restore()
    print("ok: warmth_update_known_and_stale_generates_profile")


def test_warmth_update_known_but_fresh_skips_generation():
    main.SEEKER_MEMORY_ENABLED = True
    sm = _FakeSM(visit_days=9, profile_stale=False)  # fresh profile → don't regenerate
    restore = _patch(sm)
    try:
        _run(main._maybe_update_seeker_warmth("u10"))
        assert sm.bumps == [("u10", "UTC")], "still bumps the day"
        assert sm.generate_calls == 0, "fresh profile must not be regenerated"
    finally:
        restore()
    print("ok: warmth_update_known_but_fresh_skips_generation")


_TESTS = [v for k, v in sorted(globals().items())
          if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    failed = 0
    for t in _TESTS:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    if failed:
        print(f"\n{failed} FAILED")
        sys.exit(1)
    print("\nALL READ-PATH TESTS PASSED")
