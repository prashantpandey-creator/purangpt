"""graph_health — audit the decoded graph memory for scale, quality, and contamination.

Loads the consolidated graph_manifest.json + per-text *.records.jsonl and returns
a JSON envelope with: entity/edge counts, kind distribution, top entities by
degree, isolated-node count, relationship-type histogram, per-text provenance/
provider breakdown, salvage and lens-applied rates, teaching/story fill, and
citation contamination (bhp_ markers bleeding into non-Bhagavata texts, bare-
number non-canonical cites).

Input contract:  run(manifest_path, records_dir) -> envelope
Output contract: envelope.data = {manifest, per_text, citation_health}
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List

_MARKER_RE = re.compile(r'\b[A-Za-z]{1,6}_\d+(?:[.\-]\d+)*\b')
_BARE_NUMBER_RE = re.compile(r'^\d+(?:[.\-]\d+)*$')

_DEFAULT_MANIFEST = os.path.join(
    os.path.dirname(__file__), "..", "read_pass", "out", "graph_manifest.json"
)
_DEFAULT_RECORDS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "read_pass", "out"
)


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def analyze_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    entities = manifest.get("entities", [])
    edges = manifest.get("edges", [])

    degree = Counter()
    for e in edges:
        degree[e["src"]] += 1
        degree[e["dst"]] += 1

    entity_ids = {ent["id"] for ent in entities}
    isolated = [ent["id"] for ent in entities if degree.get(ent["id"], 0) == 0]

    kind_dist = Counter(ent.get("kind", "unknown") for ent in entities)

    rel_types = Counter(e["rel"] for e in edges)

    top = sorted(
        [{"id": eid, "degree": deg} for eid, deg in degree.items()],
        key=lambda x: -x["degree"],
    )[:20]

    chapter_set = set()
    for ent in entities:
        for ch in ent.get("chapters", []):
            chapter_set.add(ch)

    return {
        "n_entities": len(entities),
        "n_edges": len(edges),
        "n_isolated": len(isolated),
        "n_chapters_covered": len(chapter_set),
        "kind_distribution": dict(kind_dist.most_common()),
        "relationship_types": dict(rel_types.most_common(30)),
        "top_entities_by_degree": top,
    }


def _extract_all_cites(records):
    cites = []
    for rec in records:
        for field in ("entities", "relationships", "teachings"):
            for node in rec.get(field) or []:
                for vr in node.get("verse_ranges") or []:
                    cites.append(str(vr))
    return cites


def cite_contamination(records: List[Dict], text_key: str) -> Dict[str, Any]:
    all_cites = _extract_all_cites(records)
    is_bhagavata = "bhagavata" in text_key.lower() or "bhp" in text_key.lower()

    bhp_count = 0
    bare_count = 0
    canonical_count = 0

    for c in all_cites:
        if _MARKER_RE.search(c):
            canonical_count += 1
            if c.startswith("bhp_") and not is_bhagavata:
                bhp_count += 1
        elif _BARE_NUMBER_RE.match(c.strip()):
            bare_count += 1

    total = len(all_cites)
    return {
        "total_cites": total,
        "canonical_cites": canonical_count,
        "bhp_on_non_bhagavata": bhp_count,
        "bare_number_cites": bare_count,
        "contamination_pct": round(bhp_count / total * 100, 1) if total else 0,
        "bare_number_pct": round(bare_count / total * 100, 1) if total else 0,
    }


def analyze_records(records: List[Dict]) -> Dict[str, Any]:
    n = len(records)
    if n == 0:
        return {"n_records": 0}

    total_ents = sum(len(r.get("entities") or []) for r in records)
    total_rels = sum(len(r.get("relationships") or []) for r in records)
    total_teachings = sum(len(r.get("teachings") or []) for r in records)
    has_story = sum(1 for r in records if r.get("story"))
    has_teaching = sum(1 for r in records if r.get("teachings"))

    provider_mix = Counter()
    salvaged = 0
    lens_applied = 0
    for r in records:
        prov = r.get("_provenance") or {}
        provider_mix[prov.get("provider", "unknown")] += 1
        if prov.get("salvaged"):
            salvaged += 1
        if prov.get("lens_applied"):
            lens_applied += 1

    return {
        "n_records": n,
        "n_entities": total_ents,
        "n_relationships": total_rels,
        "n_teachings": total_teachings,
        "teaching_fill_pct": round(has_teaching / n * 100, 1),
        "story_fill_pct": round(has_story / n * 100, 1),
        "provider_mix": dict(provider_mix.most_common()),
        "salvage_rate": round(salvaged / n * 100, 1),
        "lens_applied_rate": round(lens_applied / n * 100, 1),
    }


def run(manifest_path: str = "", records_dir: str = "") -> Dict[str, Any]:
    manifest_path = manifest_path or os.path.abspath(_DEFAULT_MANIFEST)
    records_dir = records_dir or os.path.abspath(_DEFAULT_RECORDS_DIR)
    metadata = {"manifest_path": manifest_path, "records_dir": records_dir}

    if not os.path.exists(manifest_path):
        return _envelope(False, None, metadata,
                         [{"code": "missing_manifest", "message": f"not found: {manifest_path}"}])

    with open(manifest_path) as f:
        manifest = json.load(f)

    manifest_analysis = analyze_manifest(manifest)

    per_text = {}
    citation_health = {}
    for fname in sorted(os.listdir(records_dir)):
        if not fname.endswith(".records.jsonl"):
            continue
        text_key = fname.replace(".records.jsonl", "")
        fpath = os.path.join(records_dir, fname)
        records = []
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        per_text[text_key] = analyze_records(records)
        citation_health[text_key] = cite_contamination(records, text_key)

    total_records = sum(v.get("n_records", 0) for v in per_text.values())
    total_contaminated = sum(v.get("bhp_on_non_bhagavata", 0) for v in citation_health.values())
    total_cites = sum(v.get("total_cites", 0) for v in citation_health.values())
    total_bare = sum(v.get("bare_number_cites", 0) for v in citation_health.values())

    data = {
        "manifest": manifest_analysis,
        "per_text": per_text,
        "citation_health": citation_health,
        "totals": {
            "n_texts": len(per_text),
            "n_records": total_records,
            "n_cites": total_cites,
            "bhp_contamination_total": total_contaminated,
            "bhp_contamination_pct": round(total_contaminated / total_cites * 100, 1) if total_cites else 0,
            "bare_number_total": total_bare,
            "bare_number_pct": round(total_bare / total_cites * 100, 1) if total_cites else 0,
        },
    }

    return _envelope(True, data, metadata, [])


def _human_summary(env):
    d = env["data"]
    m = d["manifest"]
    t = d["totals"]

    print(f"=== GRAPH MEMORY HEALTH ===\n")
    print(f"Entities: {m['n_entities']:,}  |  Edges: {m['n_edges']:,}  |  Isolated: {m['n_isolated']:,}")
    print(f"Chapters covered: {m['n_chapters_covered']:,}")
    print(f"Texts decoded: {t['n_texts']}  |  Total records: {t['n_records']:,}")
    print()

    print("Entity kinds:")
    for k, v in m["kind_distribution"].items():
        print(f"  {k}: {v:,}")
    print()

    print("Top 10 entities by degree:")
    for e in m["top_entities_by_degree"][:10]:
        print(f"  {e['id']}: {e['degree']}")
    print()

    print("Top relationship types:")
    for k, v in list(m["relationship_types"].items())[:10]:
        print(f"  {k}: {v:,}")
    print()

    print(f"=== CITATION HEALTH ===")
    print(f"Total cites: {t['n_cites']:,}")
    print(f"bhp_ contamination (non-Bhagavata texts): {t['bhp_contamination_total']:,} ({t['bhp_contamination_pct']}%)")
    print(f"Bare-number (non-canonical) cites: {t['bare_number_total']:,} ({t['bare_number_pct']}%)")
    print()

    print("Per-text breakdown:")
    for text_key in sorted(d["per_text"].keys()):
        pt = d["per_text"][text_key]
        ch = d["citation_health"][text_key]
        prov = ", ".join(f"{k}:{v}" for k, v in pt.get("provider_mix", {}).items())
        print(f"  {text_key}: {pt['n_records']} recs | {pt['n_entities']} ents | "
              f"salvage={pt['salvage_rate']}% | lens={pt['lens_applied_rate']}% | "
              f"teach={pt['teaching_fill_pct']}% | story={pt['story_fill_pct']}% | "
              f"bhp_contam={ch['bhp_on_non_bhagavata']} bare={ch['bare_number_cites']} | "
              f"provider={prov}")


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    manifest_path = ""
    records_dir = ""
    if "--manifest" in argv:
        manifest_path = argv[argv.index("--manifest") + 1]
    if "--records-dir" in argv:
        records_dir = argv[argv.index("--records-dir") + 1]

    env = run(manifest_path, records_dir)

    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        _human_summary(env)

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
