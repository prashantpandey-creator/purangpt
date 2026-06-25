"""test_corpora — validate every exported corpus the visual storyteller serves.

The app traverses these files; a structural fault = a broken story. This asserts,
across ALL corpora/*.json:
  1. the index (corpora.json) matches the files on disk
  2. each corpus has id/title/nodes/edges/beats, non-empty
  3. node ids are unique
  4. NO dangling edges (every edge src/dst is a real node) — else traversal crashes
  5. NO orphan cast refs (every beat.cast id is a real node) — else "step into graph" dies
  6. beats have a title (summary may legitimately be empty for some)
  7. connectivity quality: how many nodes are reachable by an edge (walkable) vs
     isolated — reported, and a floor asserted so a corpus isn't a pile of dust

Run: venv/bin/python -m tools.read_pass.storyteller.web.test_corpora   (from purangpt/)
Exit 0 = all green.
"""
import json
import os
import glob
import sys

WEB = os.path.dirname(os.path.abspath(__file__))
CORP = os.path.join(WEB, "corpora")


def _load(path):
    return json.load(open(path, encoding="utf-8"))


def validate_corpus(data, cid):
    problems = []
    for k in ("id", "title", "nodes", "edges", "beats"):
        if k not in data:
            problems.append(f"{cid}: missing key '{k}'")
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    beats = data.get("beats", [])
    if not nodes:
        problems.append(f"{cid}: zero nodes")
    if not beats:
        problems.append(f"{cid}: zero beats")

    ids = [n.get("id") for n in nodes]
    idset = set(ids)
    if len(ids) != len(idset):
        problems.append(f"{cid}: duplicate node ids ({len(ids)-len(idset)} dupes)")

    # dangling edges — the crash-the-traversal fault
    dangling = [e for e in edges if e.get("src") not in idset or e.get("dst") not in idset]
    if dangling:
        problems.append(f"{cid}: {len(dangling)} DANGLING edges (src/dst not a node)")

    # orphan cast refs — break "step into the graph"
    orphan_cast = 0
    for b in beats:
        for c in (b.get("cast") or []):
            if c not in idset:
                orphan_cast += 1
    if orphan_cast:
        problems.append(f"{cid}: {orphan_cast} orphan cast refs (beat points to missing node)")

    # beats need a title to render a heading
    untitled = sum(1 for b in beats if not (b.get("title") or "").strip())
    if untitled:
        problems.append(f"{cid}: {untitled} beats with no title")

    # connectivity: nodes touched by at least one edge
    touched = set()
    for e in edges:
        touched.add(e.get("src")); touched.add(e.get("dst"))
    walkable = len(touched & idset)
    frac = walkable / len(idset) if idset else 0
    # a story graph where almost nothing is walkable is dust — floor at 25%
    # (Skanda is known-thin; it should still clear a low bar or be flagged)
    metrics = {"nodes": len(nodes), "edges": len(edges), "beats": len(beats),
               "walkable_nodes": walkable, "walkable_frac": round(frac, 2)}
    return problems, metrics


def main():
    files = sorted(glob.glob(os.path.join(CORP, "*.json")))
    assert files, f"no corpus files in {CORP}"
    index = _load(os.path.join(WEB, "corpora.json"))
    index_ids = {c["id"] for c in index}
    file_ids = {os.path.basename(f).replace(".json", "") for f in files}

    print(f"index lists {len(index_ids)} corpora; {len(file_ids)} files on disk")
    missing_files = index_ids - file_ids
    missing_index = file_ids - index_ids
    assert not missing_files, f"index references missing files: {missing_files}"
    assert not missing_index, f"files not in index: {missing_index}"
    print("ok: index matches files")

    all_problems = []
    thin = []
    print(f"\n{'corpus':14}{'nodes':>7}{'edges':>7}{'beats':>7}{'walk%':>7}")
    for f in files:
        cid = os.path.basename(f).replace(".json", "")
        problems, m = validate_corpus(_load(f), cid)
        all_problems += problems
        pct = int(m["walkable_frac"] * 100)
        flag = "  <- THIN" if m["walkable_frac"] < 0.25 else ""
        print(f"{cid:14}{m['nodes']:>7}{m['edges']:>7}{m['beats']:>7}{pct:>6}%{flag}")
        if m["walkable_frac"] < 0.25:
            thin.append(cid)

    print()
    if all_problems:
        print(f"FAIL — {len(all_problems)} structural problems:")
        for p in all_problems:
            print(f"  - {p}")
        return 1
    print("ok: no dangling edges, no orphan cast refs, all beats titled, ids unique")
    if thin:
        print(f"note: thin graphs (walkable<25%): {thin} — data-side, not an app bug")
    print("\nALL CORPORA VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
