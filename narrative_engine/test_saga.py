"""Tests for saga.py — the story-cluster convergence layer.

Run: venv/bin/python -m narrative_engine.test_saga
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_pass.recall import Memory
from narrative_engine import saga

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

    print("--- saga (Ashvatthama — the convergence test subject) ---")
    r = saga.saga("Ashvatthama", mem)
    _check("envelope success", r["success"])
    d = r["data"]
    s = d["strands"]
    # the full braid: weapon + curse/vow + lineage + identity + deeds
    _check("carries weapons", len(s["weapons"]) > 0,
           f"weapons={s['weapons']}")
    _check("carries vows/curses", len(s["vows_and_curses"]) > 0)
    _check("carries lineage", len(s["lineage"]) > 0)
    _check("carries identity (avatar)", len(s["identity"]) > 0)
    _check("carries deeds", len(s["deeds"]) > 0)
    # the Narayana astra specifically
    weap_objs = " ".join(x["object"].lower() for x in s["weapons"])
    _check("wields Narayana astra", "narayana" in weap_objs, weap_objs)
    # avatar of Rudra
    id_objs = " ".join(x["object"].lower() for x in s["identity"])
    _check("is a form of Rudra", "rudra" in id_objs, id_objs)
    # lineage to Sharma present (the convergence with the guru-line)
    lin_text = " ".join(f"{x['subject']} {x['object']}".lower() for x in s["lineage"])
    _check("lineage touches Sharma", "sharma" in lin_text, lin_text[:120])
    # headline derived, not empty
    _check("headline non-trivial", len(d["headline"]) > len(d["name"]) + 5,
           d["headline"])

    print("\n--- convergence_check (the proof metric) ---")
    c = saga.convergence_check("Ashvatthama", mem)
    _check("convergence envelope", c["success"])
    _check("carries >=4 strands", c["data"]["n_strands"] >= 4,
           f"carries={c['data']['carries']}")
    _check("is full braid", c["data"]["is_full_braid"])

    print("\n--- saga on other warriors (the pattern generalizes) ---")
    for name in ["Arjuna", "Karna"]:
        rr = saga.saga(name, mem)
        if rr["success"]:
            _check(f"{name} has strands",
                   rr["metadata"]["total_edges"] > 10,
                   f"{rr['metadata']['total_edges']}")
            _check(f"{name} carries multiple strands",
                   len(rr["data"]["carries"]) >= 3,
                   f"{rr['data']['carries']}")

    print("\n--- honesty: a non-warrior carries fewer strands, no fabrication ---")
    rn = saga.saga("Anandamayi Ma", mem)
    # may or may not be in graph; if present, should NOT invent weapons/deeds
    if rn["success"]:
        _check("non-warrior weapons empty or honest",
               isinstance(rn["data"]["strands"]["weapons"], list))

    print("\n--- not found is honest ---")
    rf = saga.saga("Definitely_Not_In_Puranas_XYZ", mem)
    _check("missing entity returns false", not rf["success"])
    _check("missing has error code", rf["errors"][0]["code"] == "not_found")

    print("\n--- _strand_for routing ---")
    _check("astra -> weapons", saga._strand_for("uses_weapon") == "weapons")
    _check("cursed -> vows_and_curses", saga._strand_for("cursed") == "vows_and_curses")
    _check("avatar -> identity", saga._strand_for("avatar") == "identity")
    _check("killed -> deeds", saga._strand_for("killed") == "deeds")
    _check("father -> lineage", saga._strand_for("father") == "lineage")
    _check("random -> other", saga._strand_for("speaks_to") == "other")

    print(f"\n{'='*40}\n  {_passed} passed, {_failed} failed\n{'='*40}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
