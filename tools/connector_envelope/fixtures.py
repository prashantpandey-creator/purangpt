"""Real captured API response shapes — the fixtures connector_envelope is tested
against (Rule 0 precondition A: test the real-output-in -> envelope-out path, not
a pristine made-up shape).

These match the documented, real response bodies of:
  - X (Twitter) API v2  POST /2/tweets        -> docs.x.com/x-api/posts/creation-of-a-post
  - Telegram Bot API    POST /sendMessage      -> core.telegram.org/bots/api#sendmessage
                        POST /sendPhoto
Captured as constants so the test suite is deterministic and needs no network.
"""

# ── X / Twitter API v2 ────────────────────────────────────────────────────────
# Success: 201 Created, tweet id under data.id (a numeric string).
X_TWEET_SUCCESS = {
    "data": {
        "id": "1572360002101411840",
        "edit_history_tweet_ids": ["1572360002101411840"],
        "text": "Act, but renounce the fruit of action. #BhagavadGita",
    }
}
# Error: duplicate content → 403 with an errors[]/detail body.
X_TWEET_DUPLICATE_ERROR = {
    "title": "Forbidden",
    "status": 403,
    "detail": "You are not allowed to create a Tweet with duplicate content.",
    "type": "about:blank",
}
# Error: bad/expired auth → 401 with a different shape.
X_TWEET_AUTH_ERROR = {
    "title": "Unauthorized",
    "type": "about:blank",
    "status": 401,
    "detail": "Unauthorized",
}

# ── Telegram Bot API ─────────────────────────────────────────────────────────
# Success: {"ok": true, "result": {message_id, chat:{...}, ...}}
TELEGRAM_SEND_SUCCESS = {
    "ok": True,
    "result": {
        "message_id": 1487,
        "sender_chat": {"id": -1001234567890, "title": "PuranGPT", "type": "channel"},
        "chat": {"id": -1001234567890, "title": "PuranGPT", "type": "channel",
                 "username": "purangpt"},
        "date": 1750579200,
        "text": "Act, but renounce the fruit of action.",
    },
}
# Error: {"ok": false, "error_code": N, "description": "..."}
TELEGRAM_BAD_TOKEN_ERROR = {
    "ok": False,
    "error_code": 401,
    "description": "Unauthorized",
}
TELEGRAM_CHAT_NOT_FOUND_ERROR = {
    "ok": False,
    "error_code": 400,
    "description": "Bad Request: chat not found",
}
