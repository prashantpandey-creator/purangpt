"""Tests for post_scheduler — written FIRST (Rule 0 precondition A).

Run: venv/bin/python -m tools.post_scheduler.test_check  (from purangpt/)

Pure time math: given a campaign's cadence, when each channel last posted, and
`now`, decide which (campaign, channel) slots are DUE and assign a stable
dedup_key so replaying the same tick never double-posts (plan verify #8). `now`
and `last_posted` are passed in (ISO strings) — the tool never reads the clock,
so tests are deterministic.
"""
from tools.post_scheduler.check import run, CADENCE_SECONDS

CAMPAIGN = {
    "campaign_id": "camp-1",
    "cadence": "daily",
    "channels": ["x_twitter", "telegram"],
}
ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}


def test_envelope_and_due_when_never_posted():
    # No last_posted at all → every channel is due.
    env = run(campaign=CAMPAIGN, last_posted={}, now="2026-06-22T10:00:00+00:00")
    assert set(env.keys()) == ENVELOPE_KEYS
    assert env["success"] is True
    due = env["data"]["due"]
    channels_due = sorted(d["channel"] for d in due)
    assert channels_due == ["telegram", "x_twitter"], channels_due
    print("ok: due_when_never_posted")


def test_dedup_key_stable_and_unique_per_slot():
    env = run(campaign=CAMPAIGN, last_posted={}, now="2026-06-22T10:00:00+00:00")
    due = env["data"]["due"]
    keys = [d["dedup_key"] for d in due]
    assert len(keys) == len(set(keys)), "dedup keys must be unique per channel"
    # Replaying the SAME tick yields the SAME keys (idempotent → UNIQUE constraint holds).
    env2 = run(campaign=CAMPAIGN, last_posted={}, now="2026-06-22T10:00:00+00:00")
    keys2 = [d["dedup_key"] for d in env2["data"]["due"]]
    assert keys == keys2, "dedup_key must be stable across identical ticks"
    print("ok: dedup_key_stable_and_unique")


def test_not_due_when_recently_posted():
    # Posted 1 hour ago on a daily cadence → not due yet.
    env = run(
        campaign=CAMPAIGN,
        last_posted={"x_twitter": "2026-06-22T09:00:00+00:00",
                     "telegram": "2026-06-22T09:00:00+00:00"},
        now="2026-06-22T10:00:00+00:00",
    )
    assert env["data"]["due"] == [], env["data"]["due"]
    print("ok: not_due_when_recently_posted")


def test_due_after_interval_elapsed():
    # Posted 25h ago on daily cadence → due again.
    env = run(
        campaign=CAMPAIGN,
        last_posted={"x_twitter": "2026-06-21T09:00:00+00:00",
                     "telegram": "2026-06-21T09:00:00+00:00"},
        now="2026-06-22T10:00:00+00:00",
    )
    assert sorted(d["channel"] for d in env["data"]["due"]) == ["telegram", "x_twitter"]
    print("ok: due_after_interval_elapsed")


def test_per_channel_independence():
    # X posted recently, telegram long ago → only telegram is due.
    env = run(
        campaign=CAMPAIGN,
        last_posted={"x_twitter": "2026-06-22T09:30:00+00:00",
                     "telegram": "2026-06-20T09:00:00+00:00"},
        now="2026-06-22T10:00:00+00:00",
    )
    due_channels = [d["channel"] for d in env["data"]["due"]]
    assert due_channels == ["telegram"], due_channels
    print("ok: per_channel_independence")


def test_bad_cadence_fails():
    bad = dict(CAMPAIGN, cadence="whenever")
    env = run(campaign=bad, last_posted={}, now="2026-06-22T10:00:00+00:00")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "bad_cadence"
    print("ok: bad_cadence_fails")


def test_bad_timestamp_fails():
    env = run(campaign=CAMPAIGN, last_posted={"x_twitter": "not-a-date"},
              now="2026-06-22T10:00:00+00:00")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "bad_timestamp"
    print("ok: bad_timestamp_fails")


def test_cadence_table_has_phase1_values():
    for c in ("daily", "weekly", "twice_daily", "hourly", "once"):
        assert c in CADENCE_SECONDS
    print("ok: cadence_table")


if __name__ == "__main__":
    test_envelope_and_due_when_never_posted()
    test_dedup_key_stable_and_unique_per_slot()
    test_not_due_when_recently_posted()
    test_due_after_interval_elapsed()
    test_per_channel_independence()
    test_bad_cadence_fails()
    test_bad_timestamp_fails()
    test_cadence_table_has_phase1_values()
    print("\nALL TESTS PASSED")
