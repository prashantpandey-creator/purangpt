"""content_policy_check — per-channel post validation before it reaches a connector.

A deterministic decision tree (Rule 0): given a channel + post text, decide
whether it satisfies that channel's hard limits (length, hashtag count, banned
promo terms). The worker consumes only `data.ok` / `data.violations` and never
lets a non-compliant post reach the live API. No network, no LLM.

Input contract:  run(channel: str, text: str) -> dict (envelope)
Output (data):   {ok, channel, violations[], length, hashtag_count}
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List

# ── Real platform limits (the "fixtures" for this pure tool) ──────────────────
# max_chars: hard post/caption ceiling. max_hashtags: platform-recommended/hard cap.
LIMITS: Dict[str, Dict[str, int]] = {
    "x_twitter": {"max_chars": 280, "max_hashtags": 10},
    "telegram":  {"max_chars": 4096, "max_hashtags": 20},
    "instagram": {"max_chars": 2200, "max_hashtags": 30},
    "facebook":  {"max_chars": 63206, "max_hashtags": 30},
    "linkedin":  {"max_chars": 3000, "max_hashtags": 20},
    "youtube":   {"max_chars": 5000, "max_hashtags": 15},  # description
    "pinterest": {"max_chars": 500, "max_hashtags": 20},
    "threads":   {"max_chars": 500, "max_hashtags": 20},
    "reddit":    {"max_chars": 40000, "max_hashtags": 0},  # hashtags are noise on reddit
    "seo_blog":  {"max_chars": 1000000, "max_hashtags": 0},
}

# Promo/spam terms that read as inauthentic and trigger platform spam filters.
BANNED_TERMS = [
    "guaranteed", "miracle cure", "click now", "act now", "limited time",
    "100% free", "buy now", "make money fast", "risk-free", "winner",
]

_HASHTAG_RE = re.compile(r"#\w+")


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(channel: str = "", text: str = "") -> Dict[str, Any]:
    metadata = {"channel": channel, "raw_length": len(text or "")}

    if channel not in LIMITS:
        return _envelope(False, None, metadata,
                         [{"code": "unknown_channel",
                           "message": f"no policy for channel '{channel}'"}])
    if not text or not text.strip():
        return _envelope(False, None, metadata,
                         [{"code": "empty_text", "message": "post text is empty"}])

    limit = LIMITS[channel]
    length = len(text)
    hashtags = _HASHTAG_RE.findall(text)
    hashtag_count = len(hashtags)
    violations: List[Dict[str, str]] = []

    if length > limit["max_chars"]:
        violations.append({
            "code": "too_long",
            "message": f"{length} chars exceeds {channel} limit of {limit['max_chars']}",
        })
    if hashtag_count > limit["max_hashtags"]:
        violations.append({
            "code": "too_many_hashtags",
            "message": f"{hashtag_count} hashtags exceeds {channel} limit of {limit['max_hashtags']}",
        })
    low = text.lower()
    for term in BANNED_TERMS:
        if term in low:
            violations.append({
                "code": "banned_term",
                "message": f"contains spam-flagged term: '{term}'",
            })

    data = {
        "ok": len(violations) == 0,
        "channel": channel,
        "violations": violations,
        "length": length,
        "hashtag_count": hashtag_count,
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    channel = argv[argv.index("--channel") + 1] if "--channel" in argv else ""
    text = argv[argv.index("--text") + 1] if "--text" in argv else ""

    env = run(channel=channel, text=text)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        if d["ok"]:
            print(f"OK: {channel} post valid ({d['length']} chars, {d['hashtag_count']} hashtags)")
        else:
            print(f"REJECTED ({channel}):")
            for v in d["violations"]:
                print(f"  - {v['code']}: {v['message']}")

    if not env["success"]:
        return 2
    # exit 1 = finding (post is non-compliant); exit 0 = compliant.
    return 0 if env["data"]["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
