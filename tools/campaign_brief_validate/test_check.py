"""Tests for campaign_brief_validate — written FIRST (Rule 0 precondition A).

Run: venv/bin/python -m tools.campaign_brief_validate.test_check  (from purangpt/)

A campaign brief is the JSON that drives the content generator. This tool is the
gate that catches a malformed/unsafe brief BEFORE expensive LLM+media generation
runs. Tests assert real-brief-in -> envelope-out for the valid case, each
missing/invalid field, and the normalized output.
"""
from tools.campaign_brief_validate.check import run

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}

VALID_BRIEF = {
    "name": "Daily Gita Verse",
    "app_slug": "purangpt",
    "goal": "app_installs",
    "audience": "Hindu diaspora reconnecting with Vedic wisdom",
    "channels": ["x_twitter", "telegram"],
    "cadence": "daily",
}


def test_valid_brief_passes():
    env = run(brief=VALID_BRIEF)
    assert env["success"] is True, env["errors"]
    assert set(env.keys()) == ENVELOPE_KEYS
    d = env["data"]
    assert d["valid"] is True
    assert d["normalized"]["channels"] == ["x_twitter", "telegram"]
    assert d["normalized"]["app_slug"] == "purangpt"
    print("ok: valid_brief_passes")


def test_missing_required_field():
    bad = dict(VALID_BRIEF)
    del bad["goal"]
    env = run(brief=bad)
    assert env["success"] is False
    codes = [e["code"] for e in env["errors"]]
    assert "missing_field" in codes
    assert any("goal" in e["message"] for e in env["errors"])
    print("ok: missing_required_field")


def test_unknown_channel_rejected():
    bad = dict(VALID_BRIEF)
    bad["channels"] = ["x_twitter", "myspace"]
    env = run(brief=bad)
    assert env["success"] is False
    codes = [e["code"] for e in env["errors"]]
    assert "unknown_channel" in codes, env["errors"]
    print("ok: unknown_channel_rejected")


def test_empty_channels_rejected():
    bad = dict(VALID_BRIEF)
    bad["channels"] = []
    env = run(brief=bad)
    assert env["success"] is False
    assert "empty_channels" in [e["code"] for e in env["errors"]]
    print("ok: empty_channels_rejected")


def test_bad_cadence_rejected():
    bad = dict(VALID_BRIEF)
    bad["cadence"] = "hourly-ish"
    env = run(brief=bad)
    assert env["success"] is False
    assert "bad_cadence" in [e["code"] for e in env["errors"]]
    print("ok: bad_cadence_rejected")


def test_not_a_dict():
    env = run(brief="not a dict")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "bad_type"
    print("ok: not_a_dict")


def test_app_slug_defaults():
    b = dict(VALID_BRIEF)
    del b["app_slug"]
    env = run(brief=b)
    assert env["success"] is True, env["errors"]
    assert env["data"]["normalized"]["app_slug"] == "purangpt"
    print("ok: app_slug_defaults")


def test_channels_deduped_and_trimmed():
    b = dict(VALID_BRIEF)
    b["channels"] = [" x_twitter ", "x_twitter", "telegram"]
    env = run(brief=b)
    assert env["success"] is True, env["errors"]
    assert env["data"]["normalized"]["channels"] == ["x_twitter", "telegram"]
    print("ok: channels_deduped_and_trimmed")


if __name__ == "__main__":
    test_valid_brief_passes()
    test_missing_required_field()
    test_unknown_channel_rejected()
    test_empty_channels_rejected()
    test_bad_cadence_rejected()
    test_not_a_dict()
    test_app_slug_defaults()
    test_channels_deduped_and_trimmed()
    print("\nALL TESTS PASSED")
