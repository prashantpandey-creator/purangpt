"""Tests for codex.py — the canonical weapon-truth (graph + rules + inner meaning).

Run: venv/bin/python -m narrative_engine.test_codex
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_pass.recall import Memory
from narrative_engine import codex

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
    print(f"Loaded {len(mem.entities)} entities\n")

    print("--- codex.weapon_entry (Gandiva — the test case with all 3 layers) ---")
    r = codex.weapon_entry("Gandiva", mem)
    _check("envelope success", r["success"])
    d = r["data"]
    _check("Gandiva in graph", d["in_graph"])
    # layer 3: Sharma's inner meaning — Gandiva = the spine / prana channel
    _check("Gandiva has inner meaning", bool(d["inner_meaning"]),
           f"got '{d['inner_meaning']}'")
    _check("Gandiva inner meaning is the spine/prana",
           "spine" in d["inner_meaning"].lower() or "prana" in d["inner_meaning"].lower(),
           d["inner_meaning"])
    # truth level + honesty
    _check("Gandiva has truth_level", d["truth_level"] in ("full", "strong", "partial", "ungrounded"))
    _check("Gandiva has gaps list", isinstance(d["gaps"], list))
    _check("Gandiva has animation_hints", "animation_hints" in d)
    _check("animation appearance flagged NEEDS-INGESTION",
           "NEEDS-INGESTION" in d["animation_hints"]["appearance"])

    print("\n--- weapon_entry (Brahmastra — curated rules layer) ---")
    rb = codex.weapon_entry("Brahmastra", mem)
    db = rb["data"]
    _check("Brahmastra has curated rules", db["rules"] is not None)
    _check("Brahmastra rules have countered_by",
           "countered_by" in (db["rules"] or {}))
    _check("Brahmastra animation behaviors from rules",
           isinstance(db["animation_hints"]["behaviors"], list))

    print("\n--- weapon_entry (made-up weapon — must be honest, not fabricate) ---")
    rf = codex.weapon_entry("Plasmacannon", mem)
    dfa = rf["data"]
    _check("fake weapon not in graph", not dfa["in_graph"])
    _check("fake weapon truth_level ungrounded", dfa["truth_level"] == "ungrounded",
           dfa["truth_level"])
    _check("fake weapon lists its gaps", len(dfa["gaps"]) >= 3)
    _check("fake weapon has no inner meaning", dfa["inner_meaning"] == "")

    print("\n--- codex_index (the browsable weapon list) ---")
    ri = codex.codex_index(mem)
    _check("index envelope", ri["success"])
    _check("index found weapons", ri["metadata"]["total"] > 5,
           f"got {ri['metadata']['total']}")
    _check("index entries have truth signal",
           all("has_inner_meaning" in w for w in ri["data"]["weapons"]))
    # at least one weapon carries an inner meaning (Gandiva/Vajra do)
    _check("index has >=1 weapon with inner meaning",
           any(w["has_inner_meaning"] for w in ri["data"]["weapons"]))

    print("\n--- truth_level scoring ---")
    _check("3 layers = full", codex._truth_level(True, {"x": 1}, "meaning") == "full")
    _check("0 layers = ungrounded", codex._truth_level(False, None, "") == "ungrounded")
    _check("graph only = partial", codex._truth_level(True, None, "") == "partial")

    print(f"\n{'='*40}\n  {_passed} passed, {_failed} failed\n{'='*40}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
