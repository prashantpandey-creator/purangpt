"""merge_awakener — additively fold the decoded Awakener records into the existing
graph manifest WITHOUT re-running the expensive/risky full identity-resolution pass.

Why additive (not a full rebuild): the canonical manifest (8,755 entities) is the
product of graph.build → identity → resolve.py (an LLM reasoning pass that collapses
cross-text duplicates, ~$0.02/pair). A naive rebuild without that pass UNDER-merges
(17,736 entities) — a regression of the moat. But the Awakener's missing entities are
biography-specific (Allahabad, Banamali Lahiri, Ganapati Muni …) with no Puranic
duplicate, so they need NO LLM adjudication — only deterministic name matching against
what's already there. Entities that already exist (Babaji, Arjuna, Adi Shankara …) are
matched by normalized name/alias and have the Awakener's verse_ranges folded in; the
rest are added as new nodes. Relationships are added as edges, deduped by (src,rel,dst).

Pure, deterministic, idempotent. Writes a NEW file (caller decides to promote it).
Run: venv/bin/python -m tools.read_pass.merge_awakener [--write]
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
AWAKENER = f"{OUT}/awakener.records.jsonl"
RESULT = f"{OUT}/graph_manifest.awakener.json"

_IAST = str.maketrans("āĀīĪūŪṛṚṝḷṃṄṅñṭṬḍḌṇṆśŚṣṢḥḤ", "aaiiuurrrlmnnnttddnnsssshh")

# Lineage / kinship / transmission / identity predicates are the CORRECTED layer of
# the graph (curated_facts remove_edges + the guru/disciple directionality fixes).
# The raw Awakener decode re-asserts some of them WRONGLY — e.g. it places Yogananda
# in the Sharma succession ("Shailendra is_successor_of Yogananda"), the exact edge
# the corrections removed. So we NEVER import these from the raw decode; the graph's
# corrected versions stand. Only biography ENRICHMENT edges (visits, devotee_of,
# cares for, located_in …) are merged.
def _is_lineage_pred(p: str) -> bool:
    p = re.sub(r"[^a-z]+", "_", (p or "").lower()).strip("_")
    if any(k in p for k in ("guru", "disciple", "successor", "teacher", "taught",
                            "father", "mother", "son", "daughter", "brother", "sister",
                            "parent", "foster", "wife", "husband", "spouse",
                            "same", "alias", "avatar", "aspect", "incarnation",
                            "form_of", "is_form", "also_called", "epithet")):
        return True
    return p in {"is", "son", "father", "mother", "brother", "sister"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").translate(_IAST).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _slug(name: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", _norm(name)).strip("_") or "entity"
    sid, i = base, 1
    while sid in taken:
        i += 1
        sid = f"{base}_{i}"
    taken.add(sid)
    return sid


def run(write: bool = False) -> Dict[str, Any]:
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    entities: List[Dict[str, Any]] = manifest["entities"]
    edges: List[Dict[str, Any]] = manifest["edges"]
    before_e, before_x = len(entities), len(edges)

    # index existing entities by normalized name AND every all_form
    name_to_id: Dict[str, str] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    taken_ids = set()
    for e in entities:
        by_id[e["id"]] = e
        taken_ids.add(e["id"])
        for n in [e.get("name", "")] + (e.get("all_forms") or []):
            k = _norm(n)
            if k:
                name_to_id.setdefault(k, e["id"])

    edge_keys = {(e["src"], e["rel"], e["dst"]) for e in edges}
    recs = [json.loads(l) for l in open(AWAKENER, encoding="utf-8") if l.strip()]

    aw_name_to_id: Dict[str, str] = {}   # awakener entity name -> graph id (existing or new)
    added_e = matched_e = added_x = 0

    def resolve_entity(name: str, kind: str, aliases: List[str], vranges: List[str]) -> str:
        nonlocal added_e, matched_e
        forms = [name] + (aliases or [])
        # match against existing graph by any normalized form
        for f in forms:
            hit = name_to_id.get(_norm(f))
            if hit:
                ent = by_id[hit]
                # fold provenance: merge verse_ranges + forms (dedup)
                vr = set(ent.get("verse_ranges") or []) | set(vranges or [])
                ent["verse_ranges"] = sorted(vr)
                af = list(dict.fromkeys((ent.get("all_forms") or []) + forms))
                ent["all_forms"] = af
                for nf in forms:
                    name_to_id.setdefault(_norm(nf), hit)
                matched_e += 1
                return hit
        # new biography-specific entity
        nid = _slug(name, taken_ids)
        chapters = sorted({"Awakener: " + (v.split(".")[0] if "." in v else v) for v in (vranges or [])}) or ["Awakener"]
        ent = {"id": nid, "name": name, "kind": kind or "entity",
               "all_forms": list(dict.fromkeys(forms)), "chapters": chapters,
               "verse_ranges": sorted(set(vranges or []))}
        entities.append(ent)
        by_id[nid] = ent
        for nf in forms:
            name_to_id.setdefault(_norm(nf), nid)
        added_e += 1
        return nid

    # pass 1: entities
    for r in recs:
        for ent in r.get("entities", []) or []:
            nm = ent.get("name")
            if not nm:
                continue
            gid = resolve_entity(nm, ent.get("kind", ""), ent.get("aliases") or [],
                                 ent.get("verse_ranges") or [])
            aw_name_to_id[_norm(nm)] = gid

    # pass 2: relationships -> edges
    for r in recs:
        clabel = "Awakener: " + str((r.get("_provenance") or {}).get("source_text", "awakener"))
        for rel in r.get("relationships", []) or []:
            s_nm = rel.get("src") or rel.get("source") or rel.get("from")
            d_nm = rel.get("dst") or rel.get("target") or rel.get("to")
            pred = (rel.get("rel") or rel.get("predicate") or rel.get("type") or "").strip()
            if not s_nm or not d_nm or not pred:
                continue
            if _is_lineage_pred(pred):
                continue  # corrected layer — never re-import from raw decode
            sid = aw_name_to_id.get(_norm(s_nm)) or name_to_id.get(_norm(s_nm))
            did = aw_name_to_id.get(_norm(d_nm)) or name_to_id.get(_norm(d_nm))
            if not sid or not did or sid == did:
                continue
            key = (sid, pred, did)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append({"src": sid, "rel": pred, "dst": did,
                          "src_name": s_nm, "dst_name": d_nm, "chapters": [clabel]})
            added_x += 1

    manifest["entities"] = entities
    manifest["edges"] = edges
    manifest["n_entities"] = len(entities)
    manifest["n_edges"] = len(edges)

    data = {
        "entities_before": before_e, "entities_after": len(entities),
        "entities_added": added_e, "entities_matched_existing": matched_e,
        "edges_before": before_x, "edges_after": len(edges), "edges_added": added_x,
        "result_file": RESULT if write else "(dry-run, not written)",
    }
    if write:
        json.dump(manifest, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False)
    return {"success": True, "data": data, "metadata": {}, "errors": []}


if __name__ == "__main__":
    env = run(write="--write" in sys.argv)
    print(json.dumps(env, indent=2, ensure_ascii=False))
