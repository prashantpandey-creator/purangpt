"""seeker_memory.warmth — earned-warmth tier classifier (READ-path, Phase 1).

The emotional heart of session-less seeker memory. Daddy's design: Guruji is
courteous to a stranger, but as the seeker RETURNS — across distinct days, not
message-spam — his warmth grows: "an old teacher whose face softens at a known
one." This module is the pure decision tree that maps the earned signal to a
familiarity tier and the hand-authored tone-line that colours Guruji's voice.

WHY PURE: no LLM, no DB, no clock. It takes already-computed counts
(visit_days = distinct calendar days with activity; days_since_last for recency
decay) and returns a tier + directive. The DB-side visit-day bump and the
seeker_profile arc live elsewhere (session_manager); this is just the mapping, so
every branch is deterministically testable (Rule 0, precondition A — test_warmth.py).

The directive is ALWAYS warmth-as-recognition ("your face is familiar to me"),
NEVER a claim-of-record ("you asked me about karma on Tuesday") — surveillance is
the failure mode the whole model exists to avoid. At STRANGER the arc is withheld
even if a profile exists, because specificity at low familiarity reads as creepy.

Input contract:  classify_warmth(visit_days, days_since_last=None, is_guest=False)
Output contract (envelope.data on success):
    {tier, directive, disclose_arc, decayed}

Rule-0 envelope ({success,data,metadata,errors}); never raises for the expected
failure (bad counts) — returns success=False so the live caller falls back to the
empty block and the prompt stays byte-identical.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

# ---- the four tiers, ascending. `min_visits` is the inclusive lower bound. ---
# disclose_arc: may the distilled seeker-profile arc appear at this tier?
#   STRANGER/ACQUAINTED withhold it (specificity = the surveillant tell);
#   KNOWN/INTIMATE disclose it as a *felt sense*, never a transcript.
TIERS: List[Dict[str, Any]] = [
    {
        "name": "stranger",
        "min_visits": 1,
        "disclose_arc": False,
        "directive": (
            "This seeker has come to you only once before; meet them with open, "
            "unhurried attention — the courtesy of a first real meeting, not the "
            "ease of long acquaintance. Do not presume to know them."
        ),
    },
    {
        "name": "acquainted",
        "min_visits": 2,
        "disclose_arc": False,
        "directive": (
            "This seeker has returned to you a few times now; let a quiet, growing "
            "familiarity warm your voice — a face you are beginning to know. Recognise "
            "them in tone, not in detail; do not recite what they have brought before."
        ),
    },
    {
        "name": "known",
        "min_visits": 5,
        "disclose_arc": True,
        "directive": (
            "This seeker has returned to you across many days; let the warmth of "
            "recognition colour your voice — an old teacher whose face softens at a "
            "known one. You may let the felt sense of who they are shape how you "
            "speak, but never claim a record of their past words nor name a past day."
        ),
    },
    {
        "name": "intimate",
        "min_visits": 15,
        "disclose_arc": True,
        "directive": (
            "This seeker has long walked the path with you; let deep, settled ease "
            "fill your voice — the trust of a long companion. Let who they are be "
            "fully present to you, yet never presume they are unchanged, and never "
            "recite a record of what they once said; meet the living person."
        ),
    },
]

# Recency decay: a long absence drops the seeker one tier and softens the
# directive to glad-but-gentle. Strictly greater-than (90 itself is still fresh).
_DECAY_DAYS = 90
_DECAY_DIRECTIVE = (
    "This seeker returns to you after a long absence; let your face light up at a "
    "familiar one come back — glad, but gentle, never assuming they are the same "
    "person who left. Welcome them as they are now."
)


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _tier_index_for_visits(visit_days: int) -> int:
    """Highest tier whose min_visits threshold the seeker has reached."""
    idx = 0
    for i, tier in enumerate(TIERS):
        if visit_days >= tier["min_visits"]:
            idx = i
    return idx


def classify_warmth(visit_days: int,
                    days_since_last: Optional[int] = None,
                    is_guest: bool = False) -> Dict[str, Any]:
    """Map the earned-warmth signal to a familiarity tier + tone directive.

    visit_days       distinct calendar days the seeker has been active (>=1).
    days_since_last  days since their last visit; > 90 drops one tier (optional).
    is_guest         guests have no durable identity → pinned to STRANGER.

    Returns the standard envelope. data: {tier, directive, disclose_arc, decayed}.
    """
    metadata = {"visit_days": visit_days,
                "days_since_last": days_since_last,
                "is_guest": is_guest}

    if not isinstance(visit_days, int) or isinstance(visit_days, bool) or visit_days < 1:
        return _envelope(False, None, metadata, [{
            "code": "bad_visit_days",
            "message": "visit_days must be an int >= 1 (distinct active days)",
        }])
    if days_since_last is not None and (
            not isinstance(days_since_last, int)
            or isinstance(days_since_last, bool)
            or days_since_last < 0):
        return _envelope(False, None, metadata, [{
            "code": "bad_days_since_last",
            "message": "days_since_last must be a non-negative int or None",
        }])

    # Guests cannot earn warmth — no durable identity to attach a relationship to.
    if is_guest:
        stranger = TIERS[0]
        return _envelope(True, {
            "tier": stranger["name"],
            "directive": stranger["directive"],
            "disclose_arc": False,
            "decayed": False,
        }, metadata, [])

    idx = _tier_index_for_visits(visit_days)

    decayed = days_since_last is not None and days_since_last > _DECAY_DAYS
    if decayed:
        idx = max(0, idx - 1)  # drop one tier, floored at stranger

    tier = TIERS[idx]
    directive = _DECAY_DIRECTIVE if decayed else tier["directive"]

    return _envelope(True, {
        "tier": tier["name"],
        "directive": directive,
        # after a long absence we always pull back specificity, so arc disclosure
        # follows the (already-lowered) tier — glad-but-gentle, not deeply familiar
        "disclose_arc": tier["disclose_arc"] and not decayed,
        "decayed": decayed,
    }, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv

    def _arg(flag: str, default: Optional[str] = None) -> Optional[str]:
        return argv[argv.index(flag) + 1] if flag in argv else default

    visit_days = int(_arg("--visit-days", "1"))
    dsl_raw = _arg("--days-since-last")
    days_since_last = int(dsl_raw) if dsl_raw is not None else None
    is_guest = "--guest" in argv

    env = classify_warmth(visit_days, days_since_last, is_guest)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"tier={d['tier']} disclose_arc={d['disclose_arc']} "
              f"decayed={d['decayed']}\n  {d['directive']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
