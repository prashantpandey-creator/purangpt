"""merge_records — additively fold decoded records into the graph manifest.

Generalization of merge_awakener: matches each record's entities to existing graph
entities by normalized name/alias (folding verse_ranges in) or adds them as new
nodes, and adds the relationships as edges (deduped by src,rel,dst). For SCRIPTURE
(keep_lineage=True) all predicates are kept; for the Awakener biography
(keep_lineage=False) the lineage/kinship/identity layer is skipped (it re-asserts
the corrected-out Yogananda edge — see merge_awakener).

Deterministic, idempotent. Writes a NEW file; caller promotes it after verifying.
Run: venv/bin/python -m tools.read_pass.merge_records <tag1> <tag2> ... [--write]
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from typing import Any, Dict, List

OUT = "tools/read_pass/out"
MANIFEST = f"{OUT}/graph_manifest.json"
RESULT = f"{OUT}/graph_manifest.merged.json"

_IAST = str.maketrans("āĀīĪūŪṛṚṝḷṃṄṅñṭṬḍḌṇṆśŚṣṢḥḤ", "aaiiuurrrlmnnnttddnnsssshh")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").translate(_IAST).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _is_lineage_pred(p: str) -> bool:
    p = re.sub(r"[^a-z]+", "_", (p or "").lower()).strip("_")
    return any(k in p for k in ("guru", "disciple", "successor", "teacher", "taught",
                                "father", "mother", "son", "daughter", "brother", "sister",
                                "parent", "foster", "wife", "husband", "spouse",
                                "same", "alias", "avatar", "aspect", "incarnation",
                                "form_of", "is_form", "also_called", "epithet"))


def _slug(name: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", _norm(name)).strip("_") or "entity"
    sid, i = base, 1
    while sid in taken:
        i += 1
        sid = f"{base}_{i}"
    taken.add(sid)
    return sid


def run(tags: List[str], keep_lineage: bool = True, write: bool = False) -> Dict[str, Any]:
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    entities: List[Dict[str, Any]] = manifest["entities"]
    edges: List[Dict[str, Any]] = manifest["edges"]
    before_e, before_x = len(entities), len(edges)

    name_to_id: Dict[str, str] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    taken = set()
    for e in entities:
        by_id[e["id"]] = e
        taken.add(e["id"])
        for n in [e.get("name", "")] + (e.get("all_forms") or []):
            if _norm(n):
                name_to_id.setdefault(_norm(n), e["id"])
    edge_keys = {(e["src"], e["rel"], e["dst"]) for e in edges}

    added_e = matched_e = added_x = skipped_lin = 0

    def resolve(name, kind, aliases, vranges):
        nonlocal added_e, matched_e
        forms = [name] + (aliases or [])
        for f in forms:
            hit = name_to_id.get(_norm(f))
            if hit:
                ent = by_id[hit]
                ent["verse_ranges"] = sorted(set(ent.get("verse_ranges") or []) | set(vranges or []))
                ent["all_forms"] = list(dict.fromkeys((ent.get("all_forms") or []) + forms))
                for nf in forms:
                    name_to_id.setdefault(_norm(nf), hit)
                matched_e += 1
                return hit
        nid = _slug(name, taken)
        ch = sorted({(v.split(".")[0] if "." in v else v) for v in (vranges or [])}) or ["decoded"]
        by_id[nid] = {"id": nid, "name": name, "kind": kind or "entity",
                      "all_forms": list(dict.fromkeys(forms)), "chapters": ch,
                      "verse_ranges": sorted(set(vranges or []))}
        entities.append(by_id[nid])
        for nf in forms:
            name_to_id.setdefault(_norm(nf), nid)
        added_e += 1
        return nid

    for tag in tags:
        path = f"{OUT}/{tag}.records.jsonl"
        recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        local: Dict[str, str] = {}
        for r in recs:
            for ent in r.get("entities", []) or []:
                nm = ent.get("name")
                if nm:
                    local[_norm(nm)] = resolve(nm, ent.get("kind", ""), ent.get("aliases") or [],
                                               ent.get("verse_ranges") or [])
        for r in recs:
            clabel = "Decoded: " + tag
            for rel in r.get("relationships", []) or []:
                s_nm = rel.get("src") or rel.get("source"); d_nm = rel.get("dst") or rel.get("target")
                pred = (rel.get("rel") or rel.get("predicate") or "").strip()
                if not s_nm or not d_nm or not pred:
                    continue
                if not keep_lineage and _is_lineage_pred(pred):
                    skipped_lin += 1
                    continue
                sid = local.get(_norm(s_nm)) or name_to_id.get(_norm(s_nm))
                did = local.get(_norm(d_nm)) or name_to_id.get(_norm(d_nm))
                if not sid or not did or sid == did:
                    continue
                if (sid, pred, did) in edge_keys:
                    continue
                edge_keys.add((sid, pred, did))
                edges.append({"src": sid, "rel": pred, "dst": did,
                              "src_name": s_nm, "dst_name": d_nm, "chapters": [clabel]})
                added_x += 1

    manifest["entities"] = entities
    manifest["edges"] = edges
    manifest["n_entities"] = len(entities)
    manifest["n_edges"] = len(edges)
    data = {"tags": tags, "keep_lineage": keep_lineage,
            "entities_before": before_e, "entities_after": len(entities), "entities_added": added_e,
            "entities_matched": matched_e, "edges_before": before_x, "edges_after": len(edges),
            "edges_added": added_x, "lineage_skipped": skipped_lin,
            "result_file": RESULT if write else "(dry-run)"}
    if write:
        json.dump(manifest, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False)
    return {"success": True, "data": data, "metadata": {}, "errors": []}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    env = run(args, keep_lineage=("--skip-lineage" not in sys.argv), write=("--write" in sys.argv))
    print(json.dumps(env, indent=2, ensure_ascii=False))
