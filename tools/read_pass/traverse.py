"""traverse — the deterministic multi-hop path finder over the graph.

STEP 3 / axis C of CONSCIOUSNESS_ROADMAP.md. The consciousness bar (memory
consciousness-over-rag): the query daddy wants — "which weapons were god-given, by
whom?" — is a TWO-HOP pattern, (deity) --[gives]--> (weapon) --[wielded_by]-->
(hero), not a passage that exists to retrieve. recall.py reaches exactly ONE hop
(_expand_one_hop): it can surface a seed's neighbours but never the PATH that ties
giver→gift→wielder. traverse() walks the real graph edges and returns whole paths.

It is the first axis where the engine still falls short of "the mind, not the
librarian" — recall clusters; traverse REASONS across hops.

DESIGN (pinned by test_traverse.py against the real 8755-entity / 24474-edge graph):
  - Resolve symbol → one entity via the SAME normalizer factsheet/recall share
    (factsheet._resolve) — one source of truth for identity resolution.
  - Bounded BFS over an out-adjacency index of memory.edges.
  - NEVER revisit a node within a path (the graph is full of cycles like
    Krishna --killed--> Putana --attempted_to_kill--> Krishna).
  - Identity edges (alias / is / identical_to / same_as / aka) are axis B, NOT a
    journey — they are skipped as hops. A path of aliases is one node in disguise.
  - Each hop carries ONLY grounded cites (factsheet._grounded_cites → verify
    grammar). Consciousness = VERIFIABLE facts; a path you can't cite is a liar.
  - rel_filter constrains which relations a walk may follow (the "only giving
    edges" query). max_hops bounds depth; max_paths bounds fan-out on hubs.

Pure Rule-0: zero LLM, zero network, JSON in / JSON out (precond B). It composes
ADDITIVELY under decode/recall the way factsheet does — it never replaces the
one-hop path, it extends reach when a caller asks for it.

  venv/bin/python -m tools.read_pass.traverse --symbol "Krishna" --hops 2 --json

See traverse_README.md for the descriptor, failure table, and example.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from tools.read_pass.recall import Memory
from tools.read_pass import factsheet


# Identity relations are cross-text IDENTITY (axis B), never a meaning-hop.
# Keep this in sync with the merge logic in graph.py (rel:is → aspect_of, alias
# folding). A path may not be built out of these.
_IDENTITY_RELS = {"alias", "is", "identical_to", "same_as", "aka"}


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _out_adjacency(memory: Memory) -> Dict[str, List[Dict[str, Any]]]:
    """Index edges by src id once, so each BFS step is O(neighbours) not O(E).
    Directed: we walk src → dst (the way the relation reads)."""
    adj: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ed in memory.edges:
        s = ed.get("src")
        if s:
            adj[s].append(ed)
    return adj


def _hop(ed: Dict[str, Any]) -> Dict[str, Any]:
    """Render one edge as a path hop: ids for chaining + names for reading +
    grounded cites (verify-gated, the same hygiene factsheet enforces)."""
    return {
        "src": ed.get("src"),
        "rel": ed.get("rel"),
        "dst": ed.get("dst"),
        "src_name": ed.get("src_name") or ed.get("src"),
        "dst_name": ed.get("dst_name") or ed.get("dst"),
        "cites": factsheet._grounded_cites(ed.get("verse_ranges")),
    }


def _walkable(ed: Dict[str, Any], rel_filter: Optional[Set[str]]) -> bool:
    """May a walk follow this edge as a hop?
    No — if it's an identity edge (axis B, not a journey).
    No — if a rel_filter is set and this relation isn't in it.
    Otherwise yes."""
    rel = (ed.get("rel") or "").lower()
    if rel in _IDENTITY_RELS:
        return False
    if rel_filter is not None and ed.get("rel") not in rel_filter:
        return False
    return True


def _is_grounded(hops: List[Dict[str, Any]]) -> bool:
    """A path is grounded iff EVERY hop carries at least one (verify-gated) cite.
    Half the real graph fails this — so the flag is load-bearing, not decoration:
    it lets a caller separate a verse-defensible chain from a plausible-looking
    one with no floor under it."""
    return bool(hops) and all(h.get("cites") for h in hops)


def traverse(symbol: str, memory: Memory, max_hops: int = 2,
             max_paths: int = 50,
             rel_filter: Optional[Set[str]] = None,
             grounded_only: bool = False) -> Dict[str, Any]:
    """Find bounded, acyclic, verifiable multi-hop paths starting at `symbol`.

    Returns the standard envelope; data = {found, start, paths}, where each path
    is {hops: [<hop>...], length, grounded}. A hop is
    {src,rel,dst,src_name,dst_name,cites}. `grounded` is True iff every hop is
    verse-cited (only ~46% of real paths are — see the honesty discipline).
    grounded_only=True returns ONLY fully-grounded paths ("what can I defend with
    a verse?"). metadata.n_grounded / n_paths report the result's solidity.
    Unknown symbol → success:true, found:false, paths:[] (a clean answer, not an
    error). Empty symbol → success:false (a misuse, not a fact about the graph).
    """
    md = {"max_hops": max_hops, "max_paths": max_paths,
          "rel_filter": sorted(rel_filter) if rel_filter else None,
          "grounded_only": grounded_only,
          "start": None, "n_paths": 0, "n_grounded": 0}

    if not symbol or not symbol.strip():
        return _envelope(False, None, md, [{"code": "empty", "message": "no symbol"}])

    start = factsheet._resolve(symbol, memory)
    if not start:
        md["start"] = None
        return _envelope(True, {"found": False, "start": None, "paths": []}, md, [])

    start_id = start.get("id")
    md["start"] = start.get("name") or start_id

    adj = _out_adjacency(memory)

    # DEPTH-FIRST frontier of partial paths. Each item: (node, hops, visited).
    # DFS (LIFO), not BFS, ON PURPOSE: traverse exists to surface the DEEP chains
    # recall's one-hop expansion cannot — a hub's hundreds of immediate neighbours
    # are recall's job, and under a bounded result set a breadth-first order lets
    # them flood the budget before a single multi-hop chain completes (Krishna:
    # 539 one-hops would fill max_paths=50 with zero 2-hops). Going deep first
    # spends the budget on the paths that are the whole point.
    #
    # And we only RECORD a path when it can't usefully go deeper — it has reached
    # max_hops, or its end node has no walkable, unvisited neighbour (a dead end).
    # So asking for max_hops=2 yields 2-hop reasoning, not a list of neighbours;
    # max_hops=1 still yields the single-hop paths (the "what did X kill?" query).
    paths: List[Dict[str, Any]] = []
    frontier: List[Tuple[str, List[Dict[str, Any]], Set[str]]] = [
        (start_id, [], {start_id})
    ]

    while frontier and len(paths) < max_paths:
        node, hops, visited = frontier.pop()  # LIFO → depth-first
        extended = False
        if len(hops) < max_hops:
            for ed in adj.get(node, []):
                dst = ed.get("dst")
                if not dst or dst in visited:        # no revisits → no cycles
                    continue
                if not _walkable(ed, rel_filter):    # skip identity / filtered edges
                    continue
                extended = True
                frontier.append((dst, hops + [_hop(ed)], visited | {dst}))
        # record a path only when it's terminal: full depth, or a dead end.
        # (the seed itself — zero hops, never extended — is not a path.)
        if hops and (len(hops) >= max_hops or not extended):
            grounded = _is_grounded(hops)
            if grounded_only and not grounded:
                continue  # caller wants only verse-defensible chains
            paths.append({"hops": hops, "length": len(hops),
                          "grounded": grounded})

    paths = paths[:max_paths]
    md["n_paths"] = len(paths)
    md["n_grounded"] = sum(1 for p in paths if p["grounded"])
    return _envelope(True,
                     {"found": True, "start": md["start"], "paths": paths},
                     md, [])


# ── CLI (--json contract) ────────────────────────────────────────────────────
def main(argv: List[str]) -> int:
    symbol = ""
    max_hops = 2
    max_paths = 50
    rel_filter: Optional[Set[str]] = None
    grounded_only = "--grounded-only" in argv
    graph = "tools/read_pass/out/graph_manifest.json"
    ram = "tools/read_pass/out/guruji_ram.json"

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--symbol" and i + 1 < len(argv):
            symbol = argv[i + 1]; i += 1
        elif a == "--hops" and i + 1 < len(argv):
            max_hops = int(argv[i + 1]); i += 1
        elif a == "--max-paths" and i + 1 < len(argv):
            max_paths = int(argv[i + 1]); i += 1
        elif a == "--rel" and i + 1 < len(argv):
            rel_filter = set((rel_filter or set())) | {argv[i + 1]}; i += 1
        elif a == "--graph" and i + 1 < len(argv):
            graph = argv[i + 1]; i += 1
        elif a == "--ram" and i + 1 < len(argv):
            ram = argv[i + 1]; i += 1
        i += 1

    mem = Memory.load(graph, ram)
    env = traverse(symbol, mem, max_hops=max_hops, max_paths=max_paths,
                   rel_filter=rel_filter, grounded_only=grounded_only)

    if "--json" in argv:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR [{env['errors'][0]['code']}]: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        if not d["found"]:
            print(f"no entity matched '{symbol}'")
        else:
            g = env["metadata"]["n_grounded"]
            print(f"{len(d['paths'])} path(s) from {d['start']} "
                  f"(≤{max_hops} hops; {g} verse-grounded):")
            for p in d["paths"][:20]:
                chain = p["hops"][0]["src_name"]
                for h in p["hops"]:
                    chain += f" --[{h['rel']}]--> {h['dst_name']}"
                mark = "✓" if p["grounded"] else " "
                print(f"  {mark} {chain}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
