"""connector_envelope — normalize a raw connector API response into the envelope.

A deterministic parse-filter-reshape (Rule 0): each channel's publish API returns
a different JSON shape; this tool maps a raw response to a uniform
{success, data, metadata, errors} with a normalized external_id/external_url, so
the worker logs ge_post_log from `data` and NEVER parses raw provider JSON in its
own context.

Tested against real captured shapes in fixtures.py (X API v2, Telegram Bot API).

Input contract:  run(channel: str, raw: dict, handle: str = "") -> envelope
Output (data):   {external_id, external_url, channel}
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

SUPPORTED = {"x_twitter", "telegram"}


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _norm_x(raw: Dict[str, Any], handle: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    # Success shape: {"data": {"id": "...", ...}}
    data = raw.get("data")
    if isinstance(data, dict) and data.get("id"):
        tid = str(data["id"])
        user = handle or "i"  # x.com/i/status/<id> resolves without a known handle
        url = f"https://x.com/{user}/status/{tid}"
        return _envelope(True, {"external_id": tid, "external_url": url, "channel": "x_twitter"},
                         metadata, [])
    # Error shape: {"title","status","detail"} or {"errors":[...]}
    detail = raw.get("detail") or raw.get("title") or ""
    if not detail and isinstance(raw.get("errors"), list) and raw["errors"]:
        detail = raw["errors"][0].get("message", "")
    if not detail:
        detail = "could not parse X response (no data.id)"
    return _envelope(False, None, metadata,
                     [{"code": "x_error", "message": str(detail)}])


def _norm_telegram(raw: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    if raw.get("ok") is True and isinstance(raw.get("result"), dict):
        result = raw["result"]
        mid = result.get("message_id")
        if mid is None:
            return _envelope(False, None, metadata,
                             [{"code": "telegram_error", "message": "ok but no message_id"}])
        chat = result.get("chat", {})
        username = chat.get("username")
        url = f"https://t.me/{username}/{mid}" if username else ""
        return _envelope(True,
                         {"external_id": str(mid), "external_url": url, "channel": "telegram"},
                         metadata, [])
    # Error shape: {"ok": false, "error_code": N, "description": "..."}
    desc = raw.get("description", "unknown telegram error")
    code = raw.get("error_code", "")
    msg = f"{code}: {desc}" if code else str(desc)
    return _envelope(False, None, metadata,
                     [{"code": "telegram_error", "message": msg}])


def run(channel: str = "", raw: Any = None, handle: str = "") -> Dict[str, Any]:
    metadata = {"channel": channel, "handle": handle}
    if channel not in SUPPORTED:
        return _envelope(False, None, metadata,
                         [{"code": "unknown_channel",
                           "message": f"no envelope mapping for channel '{channel}'"}])
    if not isinstance(raw, dict):
        return _envelope(False, None, metadata,
                         [{"code": "bad_raw", "message": "raw response must be a dict"}])

    if channel == "x_twitter":
        return _norm_x(raw, handle, metadata)
    return _norm_telegram(raw, metadata)


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    channel = argv[argv.index("--channel") + 1] if "--channel" in argv else ""
    raw = json.loads(argv[argv.index("--raw") + 1]) if "--raw" in argv else {}
    handle = argv[argv.index("--handle") + 1] if "--handle" in argv else ""

    env = run(channel=channel, raw=raw, handle=handle)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if env["success"]:
            print(f"OK: {env['data']['external_url'] or env['data']['external_id']}")
        else:
            print(f"FAILED: {env['errors'][0]['message']}")

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
