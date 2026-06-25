"""Tests for content_policy_check — written FIRST (Rule 0 precondition A).

Run: venv/bin/python -m tools.content_policy_check.test_check  (from purangpt/)

This is a pure validation tool (no upstream command), so the "real fixtures" are
the real platform limits captured as constants: X/Twitter 280 chars, Telegram
message 4096 / photo caption 1024. Tests assert real-content-in -> envelope-out:
a 300-char X post MUST be rejected before any connector sees it (plan verify #5).
"""
from tools.content_policy_check.check import run, LIMITS

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"ok", "channel", "violations", "length", "hashtag_count"}


def test_envelope_shape():
    env = run(channel="x_twitter", text="A short verse.")
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    print("ok: envelope_shape")


def test_valid_x_post_passes():
    env = run(channel="x_twitter", text="Krishna says: act, but renounce the fruit. #BhagavadGita")
    assert env["success"] is True
    assert env["data"]["ok"] is True
    assert env["data"]["violations"] == []
    print("ok: valid_x_post_passes")


def test_300_char_x_post_rejected():
    # Plan verify #5: a 300-char X post is rejected before the connector.
    long_text = "x" * 300
    env = run(channel="x_twitter", text=long_text)
    assert env["success"] is True, "validation ran fine; the CONTENT is what fails"
    assert env["data"]["ok"] is False
    codes = [v["code"] for v in env["data"]["violations"]]
    assert "too_long" in codes, env["data"]["violations"]
    assert env["data"]["length"] == 300
    print("ok: 300_char_x_post_rejected")


def test_telegram_allows_long_text():
    # 300 chars is fine on Telegram (4096 limit) — proves limits are per-channel.
    env = run(channel="telegram", text="x" * 300)
    assert env["data"]["ok"] is True, env["data"]["violations"]
    print("ok: telegram_allows_long_text")


def test_too_many_hashtags():
    tags = " ".join(f"#tag{i}" for i in range(40))
    env = run(channel="x_twitter", text="verse " + tags)
    codes = [v["code"] for v in env["data"]["violations"]]
    # On X, 40 hashtags overflows length too; on IG (cap 30) hashtags specifically trip.
    assert "too_many_hashtags" in codes or "too_long" in codes, env["data"]
    env2 = run(channel="instagram", text="short " + tags)
    assert "too_many_hashtags" in [v["code"] for v in env2["data"]["violations"]], env2["data"]
    print("ok: too_many_hashtags")


def test_banned_term():
    env = run(channel="x_twitter", text="Guaranteed miracle cure, click now!")
    codes = [v["code"] for v in env["data"]["violations"]]
    assert "banned_term" in codes, env["data"]["violations"]
    print("ok: banned_term")


def test_empty_text_fails():
    env = run(channel="x_twitter", text="   ")
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] == "empty_text"
    print("ok: empty_text_fails")


def test_unknown_channel_fails():
    env = run(channel="myspace", text="hello")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "unknown_channel"
    print("ok: unknown_channel_fails")


def test_limits_cover_phase1_channels():
    for ch in ("x_twitter", "telegram"):
        assert ch in LIMITS, f"{ch} must have a policy"
    print("ok: limits_cover_phase1_channels")


if __name__ == "__main__":
    test_envelope_shape()
    test_valid_x_post_passes()
    test_300_char_x_post_rejected()
    test_telegram_allows_long_text()
    test_too_many_hashtags()
    test_banned_term()
    test_empty_text_fails()
    test_unknown_channel_fails()
    test_limits_cover_phase1_channels()
    print("\nALL TESTS PASSED")
