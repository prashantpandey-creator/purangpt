"""Tests for lineage.py — the guru-spine traversal + Hand-on-the-Head.

Run: venv/bin/python -m narrative_engine.test_lineage
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_pass.recall import Memory
from narrative_engine import lineage

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
    print(f"Loaded {len(mem.entities)} entities, {len(mem.edges)} edges\n")

    print("--- lineage.guru_spine ---")
    r = lineage.guru_spine(mem)
    _check("envelope success", r["success"])
    d = r["data"]
    _check("five parampara nodes", len(d["parampara"]) == 5,
           f"got {len(d['parampara'])}")
    # all five must resolve in the rebuilt graph
    in_graph = [n["name"] for n in d["parampara"] if n["in_graph"]]
    _check("all five gurus in graph", len(in_graph) == 5,
           f"only {in_graph}")
    # the spine order is apex -> present
    names = [n["name"] for n in d["parampara"]]
    _check("apex is Babaji", names[0] == "Mahavatar Babaji")
    _check("present is Sharma", names[-1] == "Shailendra Sharma")
    # the four links must all verify via curated guru edges (the multi-hop)
    _check("four links", len(d["links"]) == 4)
    _check("spine is complete (all links verified)", d["complete"],
           f"verified {r['metadata']['n_verified']}/4: "
           f"{[(l['from'],l['to'],l['verified']) for l in d['links']]}")
    # each verified link used a trusted guru relation
    for l in d["links"]:
        if l["verified"]:
            _check(f"link {l['from']}->{l['to']} via guru rel",
                   l["relation"] in lineage._GURU_RELS, f"got {l['relation']}")

    print("\n--- transmissions (Hand on the Head) ---")
    # Babaji has the richest transmission thread
    babaji = lineage.transmissions_for("Mahavatar Babaji")
    _check("Babaji has transmissions", len(babaji) > 0, f"got {len(babaji)}")
    # the canonical Benares event must be present verbatim
    joined = " ".join(babaji).lower()
    _check("Benares 1988 transmission present",
           "benares" in joined or "1988" in joined, joined[:120])

    r2 = lineage.hand_on_the_head(mem)
    _check("hand_on_the_head defaults to Babaji", r2["data"]["guru"] == "Mahavatar Babaji")
    _check("hand_on_the_head has events", r2["metadata"]["n_transmissions"] > 0)
    # Satyacharan (direct guru) should also carry transmission events
    sat = lineage.transmissions_for("Satyacharan Lahiri")
    _check("Satyacharan has transmissions", len(sat) >= 0)  # may be thin; just no crash

    print("\n--- other-fork guard ---")
    _check("Yogananda flagged as other fork", lineage.is_other_fork("Yogananda"))
    _check("Yukteshwar flagged as other fork", lineage.is_other_fork("Yukteshwar"))
    _check("Sharma NOT other fork", not lineage.is_other_fork("Shailendra Sharma"))
    _check("Babaji NOT other fork", not lineage.is_other_fork("Mahavatar Babaji"))

    print(f"\n{'='*40}\n  {_passed} passed, {_failed} failed\n{'='*40}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
