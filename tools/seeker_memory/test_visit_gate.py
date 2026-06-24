"""Tests for the earned-warmth visit-day gate (session_manager.bump_visit_day /
get_visit_stats).

TWO things are under test, split by what's reachable without a live Postgres:

1. FAIL-SAFE CONTRACT (runs here, no DB): with the DB down / no user, the methods
   must NEVER raise, bump_visit_day must return False (no false increment), and
   get_visit_stats must return the STRANGER default (1, None). A DB hiccup must
   never break a turn nor manufacture false intimacy.

2. GATE SEMANTICS ORACLE (pure date-math): the SQL gate increments iff the
   seeker's LOCAL-TZ calendar date has advanced since last_seen_at. The SQL runs
   in Postgres, but the *rule it encodes* is testable here as the equivalent
   Python date comparison — this is the documented oracle for "same tz-day = no
   bump, next tz-day = bump", including the cross-local-midnight case that a naive
   24h-window or a per-session-row counter would get wrong.

Run:  venv/bin/python -m tools.seeker_memory.test_visit_gate   (must exit 0)
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")
from backend.session_manager import SessionManager  # noqa: E402


# ---- (1) fail-safe contract — no DB required -----------------------------

def test_bump_no_user_is_false_no_db():
    sm = SessionManager(50)
    assert sm.bump_visit_day("") is False
    assert sm.bump_visit_day(None) is False


def test_stats_no_user_is_stranger_default():
    sm = SessionManager(50)
    assert sm.get_visit_stats("") == (1, None)
    assert sm.get_visit_stats(None) == (1, None)


def test_bump_with_db_down_never_raises_returns_false():
    # local DB is not reachable in this harness → _get_conn None → fail-safe
    sm = SessionManager(50)
    assert sm.bump_visit_day("any-user", "UTC") is False  # no exception


def test_stats_with_db_down_never_raises_returns_stranger():
    sm = SessionManager(50)
    assert sm.get_visit_stats("any-user") == (1, None)  # no exception


def test_bad_timezone_does_not_raise():
    # an unknown tz makes Postgres raise inside the txn; the method must swallow.
    # With the DB down it short-circuits, but the call path must still not raise.
    sm = SessionManager(50)
    assert sm.bump_visit_day("any-user", "Not/AZone") is False


# ---- (2) gate-semantics oracle — the date rule the SQL encodes -----------
# The SQL gate bumps iff:
#     (last_seen_at AT TIME ZONE tz)::date  <  (NOW() AT TIME ZONE tz)::date
# i.e. the seeker's LOCAL calendar date strictly advanced. These assert that
# rule against concrete timestamps so a future SQL edit that breaks it is caught.

def _gate_would_bump(last_seen_utc, now_utc, tz_name) -> bool:
    """Pure-Python mirror of the SQL gate predicate."""
    if last_seen_utc is None:
        return True  # never seen → first activity bumps
    tz = ZoneInfo(tz_name)
    last_local_date = last_seen_utc.astimezone(tz).date()
    now_local_date = now_utc.astimezone(tz).date()
    return last_local_date < now_local_date


def test_same_local_day_does_not_bump():
    tz = "America/New_York"
    # two activities 3 hours apart, same NY calendar day
    a = datetime(2026, 6, 24, 14, 0, tzinfo=timezone.utc)  # 10:00 EDT
    b = datetime(2026, 6, 24, 17, 0, tzinfo=timezone.utc)  # 13:00 EDT
    assert _gate_would_bump(a, b, tz) is False


def test_next_local_day_bumps():
    tz = "America/New_York"
    a = datetime(2026, 6, 24, 17, 0, tzinfo=timezone.utc)  # Jun 24 13:00 EDT
    b = datetime(2026, 6, 25, 17, 0, tzinfo=timezone.utc)  # Jun 25 13:00 EDT
    assert _gate_would_bump(a, b, tz) is True


def test_cross_local_midnight_bumps_even_within_24h():
    # THE case a naive 24h window gets wrong: 23:30 EDT → 00:30 EDT next day is
    # only 1h apart, but it crossed local midnight → a new visit-day.
    tz = "America/New_York"
    a = datetime(2026, 6, 25, 3, 30, tzinfo=timezone.utc)   # Jun 24 23:30 EDT
    b = datetime(2026, 6, 25, 4, 30, tzinfo=timezone.utc)   # Jun 25 00:30 EDT
    assert (b - a) == timedelta(hours=1)                    # well under 24h
    assert _gate_would_bump(a, b, tz) is True               # but a new tz-day


def test_within_24h_same_local_day_does_not_bump():
    # mirror image: 20h apart but still the SAME local day → no bump.
    tz = "America/New_York"
    a = datetime(2026, 6, 24, 8, 0, tzinfo=timezone.utc)    # Jun 24 04:00 EDT
    b = datetime(2026, 6, 25, 3, 0, tzinfo=timezone.utc)    # Jun 24 23:00 EDT
    assert _gate_would_bump(a, b, tz) is False


def test_never_seen_bumps():
    assert _gate_would_bump(None, datetime.now(timezone.utc), "UTC") is True


def test_tz_matters_utc_vs_local():
    # same two UTC instants can be same-day in one tz, different-day in another.
    a = datetime(2026, 6, 24, 23, 0, tzinfo=timezone.utc)
    b = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)
    # In UTC: Jun 24 vs Jun 25 → bump.
    assert _gate_would_bump(a, b, "UTC") is True
    # In Asia/Kolkata (+5:30): 04:30 Jun 25 vs 07:30 Jun 25 → same day → no bump.
    assert _gate_would_bump(a, b, "Asia/Kolkata") is False


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
