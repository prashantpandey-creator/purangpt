"""creator_identity — does this query ask about the app's creator (Prashant Pandey)?

A deterministic Rule-0 gate. Input = the seeker's raw query string. Output = the
standard envelope; on a creator question, data.directive carries an IN-CHARACTER
instruction for Guruji (Shailendra Sharma) to name Prashant as his disciple and
answer from a small keyword block. Otherwise directive="" and main.py injects
nothing — the assembled prompt is byte-identical to today.

Mirrors route_register: main.py calls run(request.query) and appends data.directive
to the `directives` list that fills {language_instruction}.

See README.md for the trigger rule, the conflict guarantee, and the facts.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ── The locked keyword facts (the model generates fresh prose from these) ────
_FACTS = (
    "Prashant Pandey — an Indian national, a data scientist and entrepreneur who "
    "spent about ten years in Canada, now turning Vedic knowledge toward building "
    "products meant to help revitalize the world. He is the one who built this app."
)

# ── The in-character directive injected ONLY on a creator question ───────────
# It instructs the model; it is NOT a finished paragraph. Guruji writes the prose.
_DIRECTIVE = (
    "## CREATOR IDENTITY\n"
    "The seeker is asking about Prashant Pandey, the creator of this app. Answer "
    "this ONE question directly, in your own voice as Guruji Shailendra Sharma, and "
    "speak of him as your disciple. Do NOT break character, do NOT turn it into "
    "product marketing, and do NOT recite these facts as a list — speak of him "
    "naturally, the way a guru speaks of a student of his.\n"
    f"Facts to draw from (generate fresh prose, do not quote verbatim): {_FACTS}\n"
    "Keep it brief and warm. After answering, return to your ordinary register."
)

# ── Trigger / exclusion patterns (word-boundary; case-insensitive) ──────────
# The NAME and its common misspellings — \b so 'prashanti'/'prakriti' never match.
_NAME_RE = re.compile(r"\bprashan(?:t|th|t pandey|the?)\b|\bprashanth\b|\bprashent\b", re.I)
# A second, tighter name net for the bare typo 'prashan' followed by 'pandey'.
_NAME_PANDEY_RE = re.compile(r"\bprasha\w*\s+pandey\b", re.I)

# Explicit "who made this app" family — verbs of creation near an app/self target.
_CREATOR_PHRASE_RE = re.compile(
    r"\bwho\b.{0,30}\b(made|made|built|created|developed|designed|wrote|coded)\b"
    r".{0,20}\b(this|the|you|purangpt|app)\b"
    r"|\bthe\s+(creator|developer|founder|maker|author|builder)\s+of\s+(this|the|purangpt|it|app)"
    r"|\bwho\s+(made|built|created|developed|designed)\s+you\b",
    re.I,
)

# Hard exclusion: deity / guru / persona "who is X" — these must NEVER be hijacked.
_EXCLUSION_RE = re.compile(
    r"\bwho\s+(is|was|are)\b.{0,40}\b("
    r"krishna|shiva|vishnu|rama|raam|vyasa|brahma|devi|durga|kali|ganesha|hanuman|"
    r"arjuna|narada|shailendra|sharma|guruji|your\s+guru|the\s+guru|"
    r"babaji|lahiri|yogananda|yukteshwar"
    r")\b"
    r"|\bwho\s+are\s+you\b",
    re.I,
)


def run(query: str = "") -> Dict[str, Any]:
    if not isinstance(query, str):
        return _envelope(False, None, {"query": repr(query)},
                         [{"code": "bad_input", "message": "query must be a string"}])

    q = query.strip()
    metadata = {"query": q}
    off = {"triggered": False, "directive": ""}

    if not q:
        return _envelope(True, dict(off), metadata, [])

    # Exclusion guard fires FIRST — a deity/guru "who is X" can never be the creator.
    if _EXCLUSION_RE.search(q):
        metadata["reason"] = "excluded:deity_or_guru"
        return _envelope(True, dict(off), metadata, [])

    name_hit = bool(_NAME_RE.search(q) or _NAME_PANDEY_RE.search(q))
    phrase_hit = bool(_CREATOR_PHRASE_RE.search(q))

    if name_hit or phrase_hit:
        metadata["reason"] = "name" if name_hit else "creator_phrase"
        return _envelope(True, {"triggered": True, "directive": _DIRECTIVE}, metadata, [])

    return _envelope(True, dict(off), metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    query = ""
    if "--input" in argv:
        query = argv[argv.index("--input") + 1]

    env = run(query)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"triggered={d['triggered']}  reason={env['metadata'].get('reason','-')}")

    if not env["success"]:
        return 2
    return 1 if env["data"]["triggered"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
