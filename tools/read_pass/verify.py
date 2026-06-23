"""verify — deterministic cite-later grounding of comprehension records.

Daddy's "cite later": the read-pass generates freely; THIS pass checks each
node's cited verse markers against the actual source window text, with ZERO LLM
calls. A citation is grounded iff its canonical `bhp_xx.yy.zzz`-style marker
literally appears in the window text the node claims it came from. Ungrounded
nodes are flagged (and optionally pruned) — that's how a hallucinated edge dies.

This is a pure Rule-0 decision tree: parse markers, set-membership, branch.
JSON contract (precondition B). The expensive LLM read already happened; trust
is restored cheaply, here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

# Canonical verse markers embedded in the GRETIL text, e.g. bhp_01.03.040,
# bg_01.15, mbh_..., etc. Match <letters>_<dot-separated-numbers>.
_MARKER_RE = re.compile(r'\b[a-z]{2,5}_\d+(?:\.\d+)+\b')

_NODE_FIELDS = ("entities", "relationships", "teachings")


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def extract_markers(text: str) -> List[str]:
    """All canonical verse markers literally present in a window's text."""
    return sorted(set(_MARKER_RE.findall(text or "")))


def _normalize_cite(c: str) -> str:
    """A cited verse_range may be a bare marker or carry noise; keep the marker."""
    m = _MARKER_RE.search(str(c))
    return m.group(0) if m else str(c).strip()


def check_node(node: Dict[str, Any], present: Set[str]) -> Dict[str, Any]:
    """Is this node grounded? grounded == at least one cite is in `present`.

    Reports the specific ungrounded cites so a later pass can scrub bad markers
    without nuking a node that also has good ones.
    """
    cites = [_normalize_cite(c) for c in (node.get("verse_ranges") or [])]
    if not cites:
        return {"grounded": False, "ungrounded_cites": [], "reason": "no_cites"}
    ungrounded = [c for c in cites if c not in present]
    grounded = len(ungrounded) < len(cites)  # at least one good cite
    return {"grounded": grounded, "ungrounded_cites": ungrounded}


def verify_record(record: Dict[str, Any], window_text: str) -> Dict[str, Any]:
    """Score one record against its source window. Returns the envelope."""
    present = set(extract_markers(window_text))
    md = {"chapter_label": record.get("_provenance", {}).get("chapter_label"),
          "markers_in_window": len(present)}

    total = grounded = 0
    flagged: List[Dict[str, Any]] = []
    for field in _NODE_FIELDS:
        for i, node in enumerate(record.get(field, []) or []):
            total += 1
            res = check_node(node, present)
            if res["grounded"]:
                grounded += 1
            else:
                flagged.append({
                    "field": field, "index": i,
                    "label": node.get("name") or node.get("teaching")
                             or f"{node.get('src')}->{node.get('dst')}",
                    "cites": node.get("verse_ranges", []),
                    "reason": res.get("reason", "all_cites_ungrounded"),
                })

    rate = (grounded / total) if total else 0.0
    data = {"total_nodes": total, "grounded_nodes": grounded,
            "grounded_rate": round(rate, 3), "flagged": flagged}
    return _envelope(True, data, md, [])


def prune(record: Dict[str, Any], window_text: str) -> Dict[str, Any]:
    """Return a copy of the record with ungrounded nodes removed."""
    present = set(extract_markers(window_text))
    out = dict(record)
    for field in _NODE_FIELDS:
        out[field] = [n for n in (record.get(field, []) or [])
                      if check_node(n, present)["grounded"]]
    return out


# ── batch entry: verify a whole records.jsonl against its source ───────────
def run(records_path: str, input_path: str) -> Dict[str, Any]:
    import json
    import os
    from tools.read_pass import group

    md = {"records": records_path, "input": input_path}
    if not os.path.isfile(records_path):
        return _envelope(False, None, md,
                         [{"code": "no_records", "message": records_path}])

    g = group.run(input_path)
    if not g["success"]:
        return _envelope(False, None, md, g["errors"])
    # index windows by seq_start for O(1) lookup against each record's provenance
    by_seq = {w["seq_start"]: w for w in g["data"]["windows"]}

    recs = []
    with open(records_path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))

    tot = gnd = 0
    per_chapter = []
    missing_window = 0
    for r in recs:
        seq = r.get("_provenance", {}).get("seq_start")
        w = by_seq.get(seq)
        if w is None:
            missing_window += 1
            continue
        v = verify_record(r, w["text"])["data"]
        tot += v["total_nodes"]
        gnd += v["grounded_nodes"]
        per_chapter.append({
            "chapter": r.get("_provenance", {}).get("chapter_label"),
            "grounded_rate": v["grounded_rate"],
            "flagged": len(v["flagged"]),
        })

    data = {"records": len(recs), "total_nodes": tot, "grounded_nodes": gnd,
            "grounded_rate": round(gnd / tot, 3) if tot else 0.0,
            "missing_window": missing_window, "per_chapter": per_chapter}
    return _envelope(True, data, md, [])


def main(argv: List[str]) -> int:
    import json
    import os

    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    records = arg("--records",
                  "tools/read_pass/out/bhagavata_proof.records.jsonl")
    input_path = arg("--input", "data/chunks/bhagavata.jsonl")
    env = run(records, input_path)

    if "--json" in argv:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message']}")
        return 2
    else:
        d = env["data"]
        print(f"OK: {d['grounded_nodes']}/{d['total_nodes']} nodes grounded "
              f"({d['grounded_rate']:.0%}) across {d['records']} chapters")
        worst = sorted(d["per_chapter"], key=lambda c: c["grounded_rate"])[:3]
        for c in worst:
            print(f"    weakest: {c['chapter']} {c['grounded_rate']:.0%} "
                  f"({c['flagged']} flagged)")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
