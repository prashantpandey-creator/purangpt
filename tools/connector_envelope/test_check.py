"""Tests for connector_envelope — written FIRST (Rule 0 precondition A).

Run: venv/bin/python -m tools.connector_envelope.test_check  (from purangpt/)

This is a FILTER tool, so it is tested against REAL captured API response shapes
(fixtures.py): X API v2 POST /2/tweets and Telegram sendMessage success+error
bodies. Asserts real-response-in -> {success,data,metadata,errors}-out with a
normalized external_id/external_url so the worker never parses raw API JSON.
"""
from tools.connector_envelope.check import run
from tools.connector_envelope import fixtures as F

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}


def test_x_success_normalized():
    env = run(channel="x_twitter", raw=F.X_TWEET_SUCCESS, handle="purangpt")
    assert set(env.keys()) == ENVELOPE_KEYS
    assert env["success"] is True, env["errors"]
    d = env["data"]
    assert d["external_id"] == "1572360002101411840"
    assert d["external_url"] == "https://x.com/purangpt/status/1572360002101411840"
    print("ok: x_success_normalized")


def test_x_duplicate_error():
    env = run(channel="x_twitter", raw=F.X_TWEET_DUPLICATE_ERROR)
    assert env["success"] is False
    e = env["errors"][0]
    assert e["code"] == "x_error"
    assert "duplicate" in e["message"].lower()
    print("ok: x_duplicate_error")


def test_x_auth_error():
    env = run(channel="x_twitter", raw=F.X_TWEET_AUTH_ERROR)
    assert env["success"] is False
    assert env["errors"][0]["code"] == "x_error"
    print("ok: x_auth_error")


def test_telegram_success_normalized():
    env = run(channel="telegram", raw=F.TELEGRAM_SEND_SUCCESS)
    assert env["success"] is True, env["errors"]
    d = env["data"]
    assert d["external_id"] == "1487"
    # public channel with username → t.me/<username>/<message_id>
    assert d["external_url"] == "https://t.me/purangpt/1487"
    print("ok: telegram_success_normalized")


def test_telegram_bad_token_error():
    env = run(channel="telegram", raw=F.TELEGRAM_BAD_TOKEN_ERROR)
    assert env["success"] is False
    e = env["errors"][0]
    assert e["code"] == "telegram_error"
    assert "401" in e["message"] or "Unauthorized" in e["message"]
    print("ok: telegram_bad_token_error")


def test_telegram_chat_not_found():
    env = run(channel="telegram", raw=F.TELEGRAM_CHAT_NOT_FOUND_ERROR)
    assert env["success"] is False
    assert "chat not found" in env["errors"][0]["message"].lower()
    print("ok: telegram_chat_not_found")


def test_unknown_channel():
    env = run(channel="myspace", raw={"id": "1"})
    assert env["success"] is False
    assert env["errors"][0]["code"] == "unknown_channel"
    print("ok: unknown_channel")


def test_malformed_raw():
    # X success shape but missing data.id → can't normalize.
    env = run(channel="x_twitter", raw={"data": {}})
    assert env["success"] is False
    assert env["errors"][0]["code"] == "x_error"
    print("ok: malformed_raw")


def test_telegram_private_chat_no_username():
    # chat without username → no public URL, but still a success with external_id.
    raw = {"ok": True, "result": {"message_id": 99, "chat": {"id": 555, "type": "private"}}}
    env = run(channel="telegram", raw=raw)
    assert env["success"] is True
    assert env["data"]["external_id"] == "99"
    assert env["data"]["external_url"] == ""  # no public link
    print("ok: telegram_private_chat_no_username")


if __name__ == "__main__":
    test_x_success_normalized()
    test_x_duplicate_error()
    test_x_auth_error()
    test_telegram_success_normalized()
    test_telegram_bad_token_error()
    test_telegram_chat_not_found()
    test_unknown_channel()
    test_malformed_raw()
    test_telegram_private_chat_no_username()
    print("\nALL TESTS PASSED")
