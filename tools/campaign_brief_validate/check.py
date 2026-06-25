"""campaign_brief_validate — gate a campaign brief BEFORE generation runs.

A deterministic decision tree (Rule 0): given a brief dict, decide whether it is
complete and well-formed enough to drive content generation, and return a
normalized copy. Catching a bad brief here avoids wasting LLM + media spend on a
campaign that can't post anywhere.

Known channels are sourced from tools.content_policy_check.LIMITS so there is one
canonical channel list across the toolchain (no drift).

Input contract:  run(brief: dict) -> dict (envelope)
Output (data):   {valid: bool, normalized: dict}
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from tools.content_policy_check.check import LIMITS

KNOWN_CHANNELS = set(LIMITS.keys())
KNOWN_CADENCES = {"once", "daily", "weekly", "twice_daily", "hourly"}
KNOWN_GOALS = {"app_installs", "web_signups", "awareness", "engagement", "traffic"}
REQUIRED = ["name", "goal", "audience", "channels", "cadence"]


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(brief: Any = None) -> Dict[str, Any]:
    metadata = {"received_keys": sorted(brief.keys()) if isinstance(brief, dict) else None}
    errors: List[Dict[str, str]] = []

    if not isinstance(brief, dict):
        return _envelope(False, None, metadata,
                         [{"code": "bad_type", "message": "brief must be a JSON object"}])

    # Required fields present and non-empty.
    for field in REQUIRED:
        val = brief.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append({"code": "missing_field", "message": f"missing required field: {field}"})

    # Channels: list, non-empty, all known.
    channels = brief.get("channels")
    norm_channels: List[str] = []
    if isinstance(channels, list):
        if not channels:
            errors.append({"code": "empty_channels", "message": "channels[] must not be empty"})
        seen = set()
        for c in channels:
            cc = c.strip() if isinstance(c, str) else c
            if cc in seen:
                continue
            seen.add(cc)
            norm_channels.append(cc)
            if cc not in KNOWN_CHANNELS:
                errors.append({"code": "unknown_channel", "message": f"unknown channel: {cc}"})
    elif channels is not None:
        errors.append({"code": "bad_channels", "message": "channels must be a list"})

    # Cadence + goal: known values (only check if present, missing already flagged).
    cadence = brief.get("cadence")
    if cadence is not None and cadence not in KNOWN_CADENCES:
        errors.append({"code": "bad_cadence",
                       "message": f"cadence '{cadence}' not in {sorted(KNOWN_CADENCES)}"})
    goal = brief.get("goal")
    if goal is not None and isinstance(goal, str) and goal.strip() and goal not in KNOWN_GOALS:
        errors.append({"code": "bad_goal",
                       "message": f"goal '{goal}' not in {sorted(KNOWN_GOALS)}"})

    if errors:
        return _envelope(False, None, metadata, errors)

    normalized = {
        "name": brief["name"].strip(),
        "app_slug": (brief.get("app_slug") or "purangpt").strip(),
        "goal": goal,
        "audience": brief["audience"].strip(),
        "channels": norm_channels,
        "cadence": cadence,
    }
    return _envelope(True, {"valid": True, "normalized": normalized}, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    brief: Any = {}
    if "--brief" in argv:
        brief = json.loads(argv[argv.index("--brief") + 1])
    elif "--file" in argv:
        with open(argv[argv.index("--file") + 1]) as f:
            brief = json.load(f)

    env = run(brief=brief)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if env["success"]:
            print(f"OK: brief valid → {env['data']['normalized']}")
        else:
            print("INVALID brief:")
            for e in env["errors"]:
                print(f"  - {e['code']}: {e['message']}")

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
