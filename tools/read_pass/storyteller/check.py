"""storyteller — the deterministic core of an interruptible oral storyteller.

The product (daddy): "tell me the Ramayana" → it narrates → you stop it anytime
to ask "who is this? why did he do that?" → it answers → "continue" → it resumes.

Puranic context note: there is NO spoiler problem. These stories are 3,000 years
old and the texts summarize their own plots in the prologue ON PURPOSE — the
destination was never the point, the retelling is. So the storyteller answers from
FULL knowledge, like a grandparent who already knows the whole tale. (An earlier
version had a spoiler gate; it solved a problem that doesn't exist here and was
deleted.)

Likewise the Guruji/Sharma decoded meaning is NOT a bolted-on feature here — it is
already baked into the corpus the comprehension engine built, so an answer carries
that understanding implicitly. The storyteller stays a STORYTELLER, not a sermon.

So this module is small — two deterministic things, the only parts that must be
exact (the narration & answers themselves are LLM calls the live app makes, fed by
these):
  1. BOOKMARK — track where narration has reached, so "continue" resumes and
     "where are we" can recap. A bookmark, not a blindfold.
  2. INTENT   — classify an interruption: is it a command (continue / go back /
     recap) or a question (who / why / what) — so the app knows whether to advance
     the bookmark or pause and answer.

Pure deterministic, no LLM, no network. JSON contract (Rule 0, precond B).
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ── the bookmark (session position) ───────────────────────────────────────────
@dataclass
class Bookmark:
    """Where the telling has reached in a corpus. A resume pointer + a recap aid.

    `index` is the position in the ordered segment list (0-based). `told` is how
    many segments have been narrated. `last_recap` is a one-line "previously…" the
    app refreshes as it narrates, so a recap is instant and needs no re-read.
    """
    corpus: str = ""
    index: int = 0
    told: int = 0
    last_recap: str = ""

    def advance(self) -> "Bookmark":
        self.index += 1
        self.told = max(self.told, self.index)
        return self

    def back(self) -> "Bookmark":
        self.index = max(0, self.index - 1)
        return self


# ── intent classification (the interrupt router) ──────────────────────────────
# Order matters: explicit COMMANDS are matched before question-words, so
# "where are we" is a recap (command), not a "who/why" question.
_INTENT_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("recap",    re.compile(r"\b(where are we|recap|remind me|what.s happen|catch me up|so far|been happening)\b", re.I)),
    ("go_back",  re.compile(r"\b(go back|back up|repeat that|say that again|rewind|previous)\b", re.I)),
    ("continue", re.compile(r"\b(continue|go on|keep going|next|carry on|resume|and then|then what|what happens next)\b", re.I)),
    ("who",      re.compile(r"\b(who|whose|what is .* called)\b", re.I)),
    ("why",      re.compile(r"\b(why|how come|what made|for what reason|reason (he|she|they))\b", re.I)),
    ("what",     re.compile(r"\b(what does .* mean|meaning of|what is|what happened to|explain|tell me about)\b", re.I)),
]

# Which intents are STORY COMMANDS (advance/move the bookmark) vs QUESTIONS
# (pause, answer, then the app resumes from the same bookmark).
_COMMANDS = {"continue", "go_back", "recap"}
_QUESTIONS = {"who", "why", "what"}


def classify_intent(text: str) -> Dict[str, str]:
    """Classify an interruption.

    Returns {intent, kind} where kind is 'command' | 'question' | 'other'.
    'command' → the app moves the bookmark (continue/back) or recaps.
    'question' → the app pauses, answers (from the corpus), resumes same bookmark.
    'other' → not a recognized control utterance; app treats as a free question.
    """
    if not text or not text.strip():
        return {"intent": "other", "kind": "other"}
    for name, pat in _INTENT_PATTERNS:
        if pat.search(text):
            kind = ("command" if name in _COMMANDS
                    else "question" if name in _QUESTIONS else "other")
            return {"intent": name, "kind": kind}
    # unrecognized but non-empty: treat as a free-form question to answer
    return {"intent": "other", "kind": "question"}


def next_action(text: str, bookmark: Bookmark) -> Dict[str, Any]:
    """Given an interruption + current bookmark, decide what the app should DO.

    Returns {action, bookmark, ...}:
      - 'narrate'  : tell the segment at bookmark.index (after advancing)
      - 'renarrate': tell the previous segment again (after stepping back)
      - 'recap'    : surface bookmark.last_recap (no position change)
      - 'answer'   : pause and answer the question (no position change)
    The narration/answer text itself is the LLM's job; this only routes + moves
    the bookmark deterministically so resume is exact.
    """
    c = classify_intent(text)
    intent, kind = c["intent"], c["kind"]
    if intent == "continue":
        bookmark.advance()
        return {"action": "narrate", "intent": intent, "kind": kind,
                "bookmark": asdict(bookmark)}
    if intent == "go_back":
        bookmark.back()
        return {"action": "renarrate", "intent": intent, "kind": kind,
                "bookmark": asdict(bookmark)}
    if intent == "recap":
        return {"action": "recap", "intent": intent, "kind": kind,
                "recap": bookmark.last_recap, "bookmark": asdict(bookmark)}
    # any question (who/why/what/other) → pause & answer, position unchanged
    return {"action": "answer", "intent": intent, "kind": kind,
            "question": text, "bookmark": asdict(bookmark)}


# ── JSON contract: route an interruption against a bookmark ───────────────────
def run(text: str = "", bookmark: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Route one storyteller interruption.

    input:  text (the user's utterance), bookmark (optional current position dict)
    data:   { action, intent, kind, bookmark, ... } — see next_action()
    """
    metadata: Dict[str, Any] = {"text": text}
    if text is None:
        return _envelope(False, None, metadata,
                         [{"code": "no_text", "message": "text is required"}])
    bm = Bookmark(**bookmark) if bookmark else Bookmark()
    try:
        data = next_action(text, bm)
    except (TypeError, ValueError) as e:
        return _envelope(False, None, metadata,
                         [{"code": "route_error", "message": str(e)[:200]}])
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    text = ""
    if "--text" in argv:
        text = argv[argv.index("--text") + 1]
    bm = None
    if "--bookmark" in argv:
        bm = json.loads(argv[argv.index("--bookmark") + 1])
    env = run(text, bm)
    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message']}")
        return 2
    else:
        d = env["data"]
        print(f"OK: {d['intent']} ({d['kind']}) → action={d['action']}, "
              f"index={d['bookmark']['index']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
