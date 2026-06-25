"""graph_layers — separate the graph's lineages by LAYER (blood vs teaching vs …).

The decoder stores relations with correct types (`father`, `guru_of`), but every
traversal blends them into one mesh, so "the lineage" cannot tell a blood descent
from a teaching descent. For this corpus that blurs the load-bearing fact that
Sharma is Satyacharan's DISCIPLE, not his son — the transmission leaving the
bloodline is exactly what makes the Kriya line a spiritual succession, not a
dynasty.

This does NOT mutate the graph (a pair that is BOTH father and guru — Lahiri →
Tinkori — stays both). It is a LENS: classify each predicate into a layer, then
walk one layer at a time.

Input contract:  run(person="", manifest_path="", depth=10) -> envelope
Output (data):   {person, layers:{kinship_down,kinship_up,transmission_down,
                  transmission_up}, coincide:[pairs that are both kin & teacher]}
"""
from __future__ import annotations

import collections
import json
import os
import sys
from typing import Any, Dict, List

_MANIFEST = os.path.join(os.path.dirname(__file__), "..", "read_pass", "out", "graph_manifest.json")

# The single source of truth for which predicate belongs to which layer.
# Direction convention per layer: stored so we can walk "down" (elder→younger,
# guru→disciple) and "up" (the inverse). Each entry: rel -> (layer, direction)
# where direction "fwd" means src is the SENIOR (parent/guru), "rev" means dst is.
RELATION_LAYERS = {
    # KINSHIP (blood / marriage)
    "father": ("kinship", "fwd"), "mother": ("kinship", "fwd"),
    "son": ("kinship", "rev"), "daughter": ("kinship", "rev"),
    "grandfather": ("kinship", "fwd"), "descendant": ("kinship", "rev"),
    "brother": ("kinship", "lateral"), "sister": ("kinship", "lateral"),
    "husband": ("kinship", "lateral"), "wife": ("kinship", "lateral"),
    "married": ("kinship", "lateral"), "consort": ("kinship", "lateral"),
    # TRANSMISSION (teaching / initiation)
    "guru": ("transmission", "fwd"), "guru_of": ("transmission", "fwd"),
    "teaches": ("transmission", "fwd"), "teacher": ("transmission", "fwd"),
    "taught": ("transmission", "fwd"), "initiated": ("transmission", "fwd"),
    "disciple": ("transmission", "rev"), "student": ("transmission", "rev"),
    "taught_by": ("transmission", "rev"),
    # IDENTITY (the same being under another form)
    "avatar": ("identity", "fwd"), "incarnation": ("identity", "fwd"),
    "alias": ("identity", "lateral"), "is": ("identity", "lateral"),
    "identical_to": ("identity", "lateral"), "form": ("identity", "lateral"),
    "aspect_of": ("identity", "rev"), "source": ("identity", "fwd"),
    # COSMOGONY (emanation, not blood)
    "born_from": ("cosmogony", "rev"), "creates": ("cosmogony", "fwd"),
    "created": ("cosmogony", "rev"),
    # CONFLICT
    "killed": ("conflict", "fwd"), "kills": ("conflict", "fwd"),
    "fights": ("conflict", "lateral"), "attacks": ("conflict", "fwd"),
    "defeated": ("conflict", "fwd"), "defeats": ("conflict", "fwd"),
    # DEVOTION
    "devotee": ("devotion", "fwd"), "worships": ("devotion", "fwd"),
    "worshipped": ("devotion", "rev"),
    # CURSE
    "cursed": ("curse", "fwd"),
}


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def layer_of(rel: str) -> str:
    """The layer a predicate belongs to ('kinship'/'transmission'/…/'other')."""
    return RELATION_LAYERS.get(str(rel).lower(), ("other", "fwd"))[0]


def build_layer_adjacency(edges: List[Dict], include_lateral: bool = True) -> Dict[str, Dict[str, set]]:
    """For each layer, a SENIOR→JUNIOR adjacency (parent→child, guru→disciple),
    normalising direction so a 'down' walk always descends.

    A LINEAGE is strictly vertical: a descent never steps sideways to a sibling or
    spouse. So `include_lateral=False` drops lateral edges (brother/wife/fights) —
    that is the right setting for walking a clean ancestry or teaching line.
    """
    adj: Dict[str, Dict[str, set]] = collections.defaultdict(lambda: collections.defaultdict(set))
    for e in edges:
        rel = str(e.get("rel", "")).lower()
        spec = RELATION_LAYERS.get(rel)
        if not spec:
            continue
        layer, direction = spec
        s, t = e.get("src"), e.get("dst")
        if not s or not t:
            continue
        if direction == "fwd":
            adj[layer][s].add(t)
        elif direction == "rev":
            adj[layer][t].add(s)
        elif include_lateral:  # siblings/spouses — only when explicitly wanted
            adj[layer][s].add(t)
            adj[layer][t].add(s)
    return adj


def walk(adj: Dict[str, set], start: str, depth: int = 10) -> List[str]:
    """Single-layer linear walk from start (first-child each step), cycle-guarded."""
    chain = [start]
    cur, seen = start, {start}
    for _ in range(depth):
        nxt = sorted(c for c in adj.get(cur, ()) if c not in seen)
        if not nxt:
            break
        cur = nxt[0]
        chain.append(cur)
        seen.add(cur)
    return chain


def separated_lineage(manifest: Dict, person: str, depth: int = 10) -> Dict[str, Any]:
    ents = {e["id"]: e for e in manifest["entities"]}
    name = {e["id"]: e.get("name", e["id"]) for e in manifest["entities"]}
    # a lineage is strictly vertical — no sibling/spouse hops
    down = build_layer_adjacency(manifest["edges"], include_lateral=False)
    # inverse adjacency for "up" walks (juniors→seniors)
    up = collections.defaultdict(lambda: collections.defaultdict(set))
    for layer, m in down.items():
        for s, ts in m.items():
            for t in ts:
                up[layer][t].add(s)

    def names(chain):
        return [name.get(x, x) for x in chain]

    # coincidences: pairs that are BOTH kinship and transmission (father-as-guru)
    pair = collections.defaultdict(set)
    for e in manifest["edges"]:
        pair[(e["src"], e["dst"])].add(layer_of(e.get("rel", "")))
    coincide = []
    for (s, t), layers in pair.items():
        if "kinship" in layers and "transmission" in layers:
            coincide.append(f"{name.get(s, s)} → {name.get(t, t)}")

    return {
        "person": name.get(person, person),
        "resolved_id": person if person in ents else None,
        "layers": {
            "kinship_down": names(walk(down["kinship"], person, depth)),
            "kinship_up": names(walk(up["kinship"], person, depth)),
            "transmission_down": names(walk(down["transmission"], person, depth)),
            "transmission_up": names(walk(up["transmission"], person, depth)),
        },
        "coincide_count": len(coincide),
        "coincide_sample": coincide[:12],
    }


def run(person: str = "", manifest_path: str = "", depth: int = 10) -> Dict[str, Any]:
    manifest_path = manifest_path or os.path.abspath(_MANIFEST)
    metadata = {"manifest_path": manifest_path, "person": person, "depth": depth}
    if not os.path.isfile(manifest_path):
        return _envelope(False, None, metadata,
                         [{"code": "missing_manifest", "message": f"not found: {manifest_path}"}])
    with open(manifest_path) as f:
        manifest = json.load(f)
    if not person:
        return _envelope(False, None, metadata,
                         [{"code": "no_person", "message": "pass --person <id> (lowercased entity id)"}])
    ids = {e["id"] for e in manifest["entities"]}
    if person not in ids:
        return _envelope(False, None, metadata,
                         [{"code": "unknown_person", "message": f"'{person}' not an entity id"}])
    data = separated_lineage(manifest, person, depth)
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    person = ""
    depth = 10
    if "--person" in argv:
        person = argv[argv.index("--person") + 1]
    if "--depth" in argv:
        depth = int(argv[argv.index("--depth") + 1])
    env = run(person=person, depth=depth)
    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        L = d["layers"]
        print(f"=== LINEAGE LAYERS for {d['person']} ===")
        print(f"  BLOOD ↓:        {' → '.join(L['kinship_down']) or '(none)'}")
        print(f"  BLOOD ↑:        {' → '.join(L['kinship_up']) or '(none)'}")
        print(f"  TEACHING ↓:     {' → '.join(L['transmission_down']) or '(none)'}")
        print(f"  TEACHING ↑:     {' → '.join(L['transmission_up']) or '(none)'}")
        print(f"  father-as-guru coincidences in graph: {d['coincide_count']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
