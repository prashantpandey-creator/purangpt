"""post_scheduler — decide which (campaign, channel) slots are due to post now.

A deterministic decision tree (Rule 0): given a campaign's cadence, each
channel's last-posted timestamp, and `now`, return the channels whose interval
has elapsed, each with a STABLE dedup_key. Replaying the same tick yields the
same keys, so the ge_post_queue UNIQUE(dedup_key) constraint prevents
double-posting (plan verify #8). No clock read (now is an input) → deterministic
and testable; no DB.

Input contract:  run(campaign: dict, last_posted: dict, now: str) -> envelope
Output (data):   {due: [{campaign_id, channel, dedup_key, scheduled_for}], now}
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

# Interval between posts per cadence, in seconds.
CADENCE_SECONDS: Dict[str, int] = {
    "hourly": 3600,
    "twice_daily": 12 * 3600,
    "daily": 24 * 3600,
    "weekly": 7 * 24 * 3600,
    "once": 0,  # special-cased: due only if never posted
}


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _parse(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp; raise ValueError on bad input."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _dedup_key(campaign_id: str, channel: str, cadence: str, now_dt: datetime) -> str:
    """Stable key for the slot: same campaign+channel+cadence-bucket → same key.

    Bucketing `now` to the cadence interval means every tick within the same
    interval maps to the same key, so a replay can't create a second queue row.
    """
    interval = CADENCE_SECONDS.get(cadence, 0)
    if interval > 0:
        bucket = int(now_dt.timestamp()) // interval
    else:
        bucket = 0  # 'once' → a single fixed bucket
    return f"{campaign_id}:{channel}:{cadence}:{bucket}"


def run(campaign: Any = None, last_posted: Any = None, now: str = "") -> Dict[str, Any]:
    metadata = {"now": now}
    if not isinstance(campaign, dict):
        return _envelope(False, None, metadata,
                         [{"code": "bad_campaign", "message": "campaign must be a dict"}])

    cadence = campaign.get("cadence")
    if cadence not in CADENCE_SECONDS:
        return _envelope(False, None, metadata,
                         [{"code": "bad_cadence", "message": f"unknown cadence: {cadence}"}])

    try:
        now_dt = _parse(now)
    except (ValueError, TypeError):
        return _envelope(False, None, metadata,
                         [{"code": "bad_now", "message": f"bad `now` timestamp: {now!r}"}])

    last_posted = last_posted or {}
    interval = CADENCE_SECONDS[cadence]
    due: List[Dict[str, str]] = []

    for channel in campaign.get("channels", []):
        last = last_posted.get(channel)
        if last is None:
            is_due = True
        else:
            try:
                last_dt = _parse(last)
            except (ValueError, TypeError):
                return _envelope(False, None, metadata,
                                 [{"code": "bad_timestamp",
                                   "message": f"bad last_posted for {channel}: {last!r}"}])
            if cadence == "once":
                is_due = False  # 'once' + already posted → never again
            else:
                is_due = (now_dt - last_dt).total_seconds() >= interval

        if is_due:
            due.append({
                "campaign_id": campaign.get("campaign_id", ""),
                "channel": channel,
                "dedup_key": _dedup_key(campaign.get("campaign_id", ""), channel, cadence, now_dt),
                "scheduled_for": now_dt.isoformat(),
            })

    return _envelope(True, {"due": due, "now": now_dt.isoformat()}, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    campaign = json.loads(argv[argv.index("--campaign") + 1]) if "--campaign" in argv else {}
    last_posted = json.loads(argv[argv.index("--last-posted") + 1]) if "--last-posted" in argv else {}
    now = argv[argv.index("--now") + 1] if "--now" in argv else ""

    env = run(campaign=campaign, last_posted=last_posted, now=now)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        due = env["data"]["due"]
        print(f"{len(due)} slot(s) due: " + ", ".join(d["channel"] for d in due))

    if not env["success"]:
        return 2
    return 1 if env["data"]["due"] else 0  # exit 1 = "there is work" (finding)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
