"""graph_clean_audit — quantify residual relationship-quality noise in the graph.

After the interpretation-layer cleaning in narrative_engine/character.py (kin +
guru directionality, non-being/artifact filtering), this tool answers the
question that 3 hand-picked test entities cannot: *across all ~24k edges, how
much relationship noise remains, and where?* It is a pure decision tree over the
edge list (Rule 0 → a tested script, not a sub-agent), reusing character.py's
shipped predicate sets as the single source of truth so it measures exactly what
the engine enforces.

Violation classes (deterministic invariants):
  - non_being_relation : a kin/guru edge whose endpoint is a non-being (kind in
                         the denylist, e.g. the practice 'Kriya Yoga') or a
                         narratological artifact ('Narrator'). Filtered at DISPLAY
                         by the engine; this counts the underlying edge noise.
  - direction_contradiction : a pair (A,B) where BOTH directions of seniority are
                         asserted (A senior to B AND B senior to A) — a genuine
                         contradiction the positional rule cannot resolve.
  - self_loop : an edge whose src == dst.

Input contract:  run(graph_path=..., ram_path=..., n_samples=5) -> envelope
Output (envelope.data on success): see _OUTPUT_SCHEMA below.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Tuple

# the cleaning logic is the source of truth — import its sets, never re-declare
from narrative_engine.character import (
    _FAMILY_PREDS, _PARENT_AXIS, _GRAND_AXIS, _LINEAGE_AXIS,
    _is_guru_rel, _GURU_SRC_PREDS, _DISCIPLE_SRC_PREDS,
    _NON_BEING_KINDS, _ARTIFACT_NAMES,
)

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_GRAPH = os.path.join(_HERE, "tools/read_pass/out/graph_manifest.json")
_RAM = os.path.join(_HERE, "tools/read_pass/out/guruji_ram.json")

# directed kin axes (src is the senior); spouse/sibling are symmetric → no direction
_DIRECTED_KIN = _PARENT_AXIS | _GRAND_AXIS | _LINEAGE_AXIS

_OUTPUT_SCHEMA = {
    "n_edges": "int", "n_entities": "int",
    "kin": "object", "guru": "object", "retype_candidates": "object",
    "self_loops": "object", "summary": "object",
}


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data,
            "metadata": metadata, "errors": errors}


def _is_non_being(entity: Dict[str, Any]) -> bool:
    """Mirror of character._is_being, inverted, operating on a graph entity dict."""
    if not entity:
        return False  # unknown id → not provably a non-being
    if (entity.get("kind") or "").lower() in _NON_BEING_KINDS:
        return True
    if (entity.get("name") or "").strip().lower() in _ARTIFACT_NAMES:
        return True
    return False


def _guru_is_src(rel: str) -> bool:
    """Which end of a guru edge is the guru? (per-predicate, mirrors _guru_label)."""
    r = (rel or "").lower()
    if (r in _DISCIPLE_SRC_PREDS or "taught_by" in r or "disciple_of" in r
            or "student_of" in r or "receives_teaching" in r
            or "learns_from" in r or "initiated_by" in r):
        return False
    return True


def _audit_contradictions(directed: Dict[Tuple[str, str], set],
                          n_samples: int) -> Dict[str, Any]:
    """Given senior->junior claims keyed by (a,b)->{rels}, find pairs asserted in
    BOTH directions (a senior to b AND b senior to a)."""
    contradictions = []
    seen = set()
    for (a, b) in directed:
        if (a, b) in seen or (b, a) in seen:
            continue
        if a != b and (b, a) in directed:
            seen.add((a, b))
            contradictions.append({
                "a": a, "b": b,
                "a_to_b": sorted(directed[(a, b)]),
                "b_to_a": sorted(directed[(b, a)]),
            })
    return {"count": len(contradictions), "samples": contradictions[:n_samples]}


def run(graph_path: str = _GRAPH, ram_path: str = _RAM,
        n_samples: int = 5, edges: Any = None,
        entities: Any = None) -> Dict[str, Any]:
    """Scan every edge for residual relationship-quality violations.

    `edges`/`entities` may be passed directly (fixture tests); otherwise the
    graph manifest is read from `graph_path`.
    """
    metadata = {"graph_path": graph_path, "n_samples": n_samples}
    if edges is None or entities is None:
        try:
            with open(graph_path, encoding="utf-8") as fh:
                m = json.load(fh)
            edges = m["edges"]
            entities = m["entities"]
        except (OSError, KeyError, json.JSONDecodeError) as e:
            return _envelope(False, None, metadata,
                             [{"code": "load_failed", "message": str(e)}])

    by_id = {e.get("id"): e for e in entities}

    # PRE-PASS: every entity that participates in a KIN edge is a provable BEING
    # (concepts/practices don't have mothers). A non-being KIND on such an entity
    # is therefore a MIS-TYPE (re-type candidate), NOT relation-noise — this is the
    # split that makes the non-being count mean something (Devaki=concept is a
    # mistyped being; Kriya Yoga=practice in a guru edge is genuine noise).
    kin_participants = set()
    for ed in edges:
        if (ed.get("rel") or "").lower() in _FAMILY_PREDS:
            kin_participants.add(ed.get("src"))
            kin_participants.add(ed.get("dst"))

    def _classify_nb(eid):
        """('mistyped'|'genuine'|None) for the non-being endpoint of an edge."""
        ent = by_id.get(eid)
        if not _is_non_being(ent):
            return None
        return "mistyped" if eid in kin_participants else "genuine"

    kin_n = guru_n = 0
    kin_nb = {"mistyped": [], "genuine": []}
    guru_nb = {"mistyped": [], "genuine": []}
    retype: Dict[str, Dict[str, str]] = {}     # entity id -> {name, kind}
    self_loops: List[Dict[str, str]] = []
    kin_dir: Dict[Tuple[str, str], set] = {}
    guru_dir: Dict[Tuple[str, str], set] = {}

    for ed in edges:
        src, dst, rel = ed.get("src"), ed.get("dst"), (ed.get("rel") or "")
        r = rel.lower()
        sn, dn = ed.get("src_name", src), ed.get("dst_name", dst)

        if src == dst:
            self_loops.append({"id": src, "name": sn, "rel": rel})

        is_kin = r in _FAMILY_PREDS
        is_guru = (not is_kin) and _is_guru_rel(rel)
        if not (is_kin or is_guru):
            continue

        bucket = kin_nb if is_kin else guru_nb
        for eid, nm in ((src, sn), (dst, dn)):
            cls = _classify_nb(eid)
            if cls:
                bucket[cls].append({"edge": f"{sn} --{rel}--> {dn}", "non_being": nm})
                if eid in kin_participants:        # provable being, wrong kind
                    retype[eid] = {"id": eid, "name": nm,
                                   "kind": (by_id.get(eid) or {}).get("kind", "")}

        if is_kin:
            kin_n += 1
            if r in _DIRECTED_KIN:                 # src is senior
                kin_dir.setdefault((src, dst), set()).add(rel)
        else:
            guru_n += 1
            senior, junior = (src, dst) if _guru_is_src(rel) else (dst, src)
            guru_dir.setdefault((senior, junior), set()).add(rel)

    def _nb_block(b):
        return {"genuine": len(b["genuine"]), "mistyped": len(b["mistyped"]),
                "samples_genuine": b["genuine"][:n_samples],
                "samples_mistyped": b["mistyped"][:n_samples]}

    kin = {
        "n_edges": kin_n,
        "non_being_relations": _nb_block(kin_nb),
        "direction_contradictions": _audit_contradictions(kin_dir, n_samples),
    }
    guru = {
        "n_edges": guru_n,
        "non_being_relations": _nb_block(guru_nb),
        "direction_contradictions": _audit_contradictions(guru_dir, n_samples),
    }
    total_rel = kin_n + guru_n
    # GENUINE violations only — mis-typed beings are a data-quality worklist, not
    # broken relations, so they don't count against relationship cleanliness.
    violations = (len(kin_nb["genuine"]) + len(guru_nb["genuine"])
                  + kin["direction_contradictions"]["count"]
                  + guru["direction_contradictions"]["count"])
    retype_list = sorted(retype.values(), key=lambda x: x["name"])
    summary = {
        "relationship_edges": total_rel,
        "violations": violations,
        "clean_pct": round(100.0 * (1 - violations / total_rel), 3) if total_rel else 100.0,
        "retype_candidates": len(retype_list),
    }

    data = {
        "n_edges": len(edges), "n_entities": len(entities),
        "kin": kin, "guru": guru,
        "retype_candidates": {"count": len(retype_list),
                              "samples": retype_list[:n_samples]},
        "self_loops": {"count": len(self_loops), "samples": self_loops[:n_samples]},
        "summary": summary,
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    env = run()
    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        s = d["summary"]
        kn, gn = d["kin"]["non_being_relations"], d["guru"]["non_being_relations"]
        print(f"edges={d['n_edges']} entities={d['n_entities']}")
        print(f"relationship edges: kin={d['kin']['n_edges']} guru={d['guru']['n_edges']}")
        print(f"kin   non-being: genuine={kn['genuine']} mistyped={kn['mistyped']}  "
              f"contradictions={d['kin']['direction_contradictions']['count']}")
        print(f"guru  non-being: genuine={gn['genuine']} mistyped={gn['mistyped']}  "
              f"contradictions={d['guru']['direction_contradictions']['count']}")
        print(f"re-type candidates (mistyped beings): {d['retype_candidates']['count']}")
        print(f"self-loops={d['self_loops']['count']}")
        print(f"CLEAN: {s['clean_pct']}% ({s['violations']}/{s['relationship_edges']} "
              f"GENUINE violations; mis-typed beings excluded)")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
