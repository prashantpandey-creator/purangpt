"""app — the standalone storyteller you can PLAY in a terminal.

Run it:
    cd purangpt
    venv/bin/python -m tools.read_pass.storyteller.app --corpus ramayana

Then talk to it:
    [enter]          → tell the next beat
    continue         → next beat
    back             → previous beat
    where are we     → recap
    who is Hanuman?  → pause & answer (via recall), then you resume
    why ... ?        → pause & answer
    quit             → leave

This is the STANDALONE app: it reuses the storyteller library (check.py router +
narrate.py beats) and the read_pass records/recall — but hosts nothing, needs no
DB. Answers use recall() if the graph files are present; otherwise it degrades to
"here's what I can see in this beat" so the app is playable with no API key and no
extra setup. Eventually point RECORDS_DIR/graph at the app's own copy → fully cut
the cord.
"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from tools.read_pass.storyteller.check import Bookmark, next_action
from tools.read_pass.storyteller.narrate import load_beats, beat_at, beat_as_text

# recall is optional — the app must run without it (no graph / no key)
try:
    from tools.read_pass.recall import Memory as _Memory, recall as _recall, render_context as _render
except Exception:  # noqa
    _Memory = _recall = _render = None

_GRAPH = "tools/read_pass/out/graph_manifest.json"
_RAM = "tools/read_pass/out/guruji_ram.json"


def _load_memory():
    """Best-effort load of recall's memory; None if unavailable (app still runs)."""
    if _Memory is None or not (os.path.isfile(_GRAPH) and os.path.isfile(_RAM)):
        return None
    try:
        return _Memory.load(_GRAPH, _RAM)
    except Exception:  # noqa
        return None


def answer_question(question: str, beat: Optional[Dict[str, Any]], memory) -> str:
    """Answer an interruption. Uses recall() if we have memory; else falls back to
    what's visible in the current beat (so the app is playable bare)."""
    # Path 1: real associative recall over the graph
    if memory is not None and _recall is not None:
        env = _recall(question, memory)
        if env.get("success") and env["data"].get("entities"):
            ctx = _render(env["data"]) if _render else ""
            if ctx.strip():
                return ctx
    # Path 2 (fallback): answer from the current beat's own cast/summary
    if beat:
        cast = beat.get("characters", [])
        # crude name match against this beat's cast
        q = question.lower()
        hits = [c for c in cast if c.lower().split()[0] in q]
        if hits:
            return (f"In what you've heard so far, {', '.join(hits)} "
                    f"appear{'s' if len(hits)==1 else ''} here:\n  {beat.get('summary','')[:240]}")
        if cast:
            return (f"(no deeper memory loaded) — the figures in this part are: "
                    f"{', '.join(cast[:8])}.")
    return "(I don't have more on that yet — try 'continue' to hear what comes next.)"


def run_session(corpus: str) -> int:
    env = load_beats(corpus)
    if not env["success"]:
        print(f"Cannot start: {env['errors'][0]['message']}")
        return 2
    beats: List[Dict[str, Any]] = env["data"]["beats"]
    memory = _load_memory()

    print(f"\n  ✦ The Storyteller ✦   ({corpus} — {len(beats)} beats)")
    print(f"  memory: {'graph loaded (rich answers)' if memory else 'no graph (beat-only answers)'}")
    print("  commands: [enter]=next · back · where are we · who/why...? · quit\n")
    print("  Shall I begin?\n")

    bm = Bookmark(corpus=corpus, index=-1, told=0)  # -1 so first 'continue' lands on beat 0

    # tell the first beat immediately
    bm.index = 0
    bm.told = 1
    b0 = beat_at(beats, 0)
    if b0:
        print(b0.text())
        bm.last_recap = f"We've begun: {b0.title or b0.chapter_label}."
    print()

    while True:
        try:
            utter = input("  you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  (the teller falls silent)\n")
            return 0
        if utter.lower() in ("quit", "exit", "q"):
            print("\n  (the teller bows)\n")
            return 0

        # empty input = "continue"
        text = utter or "continue"
        act = next_action(text, bm)
        action = act["action"]

        if action in ("narrate", "renarrate"):
            idx = act["bookmark"]["index"]
            b = beat_at(beats, idx)
            if b is None:
                if idx >= len(beats):
                    print("\n  〜 And so the tale is told. 〜\n")
                    bm.index = len(beats) - 1  # clamp so we don't run off the end
                else:
                    print("\n  (we are at the very beginning)\n")
                continue
            print("\n" + b.text() + "\n")
            bm.last_recap = f"We are at: {b.title or b.chapter_label}."

        elif action == "recap":
            print(f"\n  〜 where we are 〜\n  {act.get('recap') or '(just beginning)'}")
            cur = beat_at(beats, bm.index)
            if cur:
                print(f"  current part: {cur.title or cur.chapter_label} "
                      f"(beat {bm.index + 1} of {len(beats)})\n")
            else:
                print()

        elif action == "answer":
            cur = beat_at(beats, bm.index)
            cur_d = asdict(cur) if cur else None
            print("\n  〜 (the teller pauses) 〜")
            print("  " + answer_question(act["question"], cur_d, memory).replace("\n", "\n  "))
            print("  〜 (and continues where we left off — say 'continue') 〜\n")


def main(argv: List[str]) -> int:
    corpus = "ramayana"
    if "--corpus" in argv:
        corpus = argv[argv.index("--corpus") + 1]
    return run_session(corpus)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
