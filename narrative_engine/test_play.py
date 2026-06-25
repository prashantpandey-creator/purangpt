"""Test for play.py — the Phase-A1 client harness drives the engine end to end.

Run: venv/bin/python -m narrative_engine.test_play
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_pass.recall import Memory
from narrative_engine import play

_GRAPH = "tools/read_pass/out/graph_manifest.json"
_RAM = "tools/read_pass/out/guruji_ram.json"

_passed = 0
_failed = 0


def _check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  OK  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}: {detail}")


def main():
    if not os.path.exists(_GRAPH):
        print(f"SKIP: {_GRAPH} not found")
        return 0
    mem = Memory.load(_GRAPH, _RAM)

    print("--- play.demo (the full vertical slice, non-interactive) ---")
    out = play.demo(mem)
    _check("scene rendered", out["scene_ok"])
    _check("saga rendered", out["saga_ok"])
    _check("saga carried the full braid (>=4 strands)", out["saga_strands"] >= 4,
           f"strands={out['saga_strands']}")
    _check("weapon truth surfaced", out["weapon_truth"] in ("full", "strong", "partial"))
    _check("fight resolved", out["fight_outcome"] == "neutralized",
           f"outcome={out['fight_outcome']}")
    _check("fight canon verdict present", isinstance(out["fight_is_canon"], bool))

    print("\n--- Game harness object ---")
    g = play.Game(mem)
    _check("seeker initialized", g.seeker.name == "Disciple")
    _check("game starts running", g.running is True)
    # render methods return engine envelopes
    r = g.render_scene(location="Ayodhya")
    _check("render_scene returns envelope", "success" in r)
    rs = g.render_saga("Arjuna")
    _check("render_saga returns envelope", rs["success"])
    rw = g.render_weapon("Brahmastra")
    _check("render_weapon returns envelope", rw["success"])

    print(f"\n{'='*40}\n  {_passed} passed, {_failed} failed\n{'='*40}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
