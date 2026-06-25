"""build_corpora — export every serviceable read_pass text into per-corpus JSON
the visual storyteller can serve.

Each corpus's graph is built from its OWN records' entities + relationships — NOT
the global graph_manifest. Two reasons:
  1. It's self-contained per text (a story carries its own cast & links).
  2. It sidesteps the global graph's bad merges (e.g. Rama==Parashurama alias),
     because per-story relationships are local to that text.

Output (served over http on the preview, so fetch() works):
  web/corpora/<id>.json   — {id, title, nodes, edges, beats}
  web/corpora.json        — index: [{id, title, n_beats}] for the picker

Skips superseded/empty sets (e.g. bhagavata_proof). Deterministic, no LLM.
"""
from __future__ import annotations

import json
import os
import re
import glob

OUT = "tools/read_pass/out"
WEB = "tools/read_pass/storyteller/web"

# files to exclude from the picker (superseded duplicates / proof sets)
_SKIP = {"bhagavata_proof"}

# clean display names for the record-file stems
_TITLE = {
    "agni_v2": "Agni Purāṇa", "bhagavata_v2": "Bhāgavata Purāṇa",
    "bhavishya_v2": "Bhaviṣya Purāṇa", "brahma_v1": "Brahma Purāṇa",
    "brahmanda_v2": "Brahmāṇḍa Purāṇa", "garuda_v2": "Garuḍa Purāṇa",
    "gita_v2": "Bhagavad Gītā", "gheranda_inhouse": "Gheraṇḍa Saṃhitā",
    "kurma_v2": "Kūrma Purāṇa", "linga_v2": "Liṅga Purāṇa",
    "mahabharata_bori": "Mahābhārata", "markandeya_v2": "Mārkaṇḍeya Purāṇa",
    "matsya_v2": "Matsya Purāṇa", "narada_v2": "Nārada Purāṇa",
    "padma_v1": "Padma Purāṇa", "ramayana_v1": "Rāmāyaṇa",
    "skanda_v1": "Skanda Purāṇa", "vamana_v2": "Vāmana Purāṇa",
    "varaha_v2": "Varāha Purāṇa", "vishnu_v2": "Viṣṇu Purāṇa",
    "awakener": "The Awakener (Guruji)",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _slug(stem: str) -> str:
    """corpus id the app uses — drop the version suffix."""
    return re.sub(r"_v\d+|_inhouse|_bori|_proof", "", stem)


def _min_seq(rec):
    cids = (rec.get("_provenance", {}) or {}).get("chunk_ids", []) or []
    seqs = [int(c.rsplit("-", 1)[-1]) for c in cids if c.rsplit("-", 1)[-1].isdigit()]
    return min(seqs) if seqs else (rec.get("_provenance", {}) or {}).get("seq_start", 10**9)


def build_one(path: str):
    stem = os.path.basename(path).replace(".records.jsonl", "")
    if stem in _SKIP:
        return None
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if not recs:
        return None
    recs.sort(key=_min_seq)

    nodes = {}   # id -> node
    edges = []
    seen_edge = set()

    def node(name, kind=""):
        nid = _norm(name)
        if not nid:
            return None
        if nid not in nodes:
            nodes[nid] = {"id": nid, "name": name, "kind": kind, "forms": []}
        elif kind and not nodes[nid]["kind"]:
            nodes[nid]["kind"] = kind
        return nid

    beats = []
    for i, r in enumerate(recs):
        s = r.get("story", {}) or {}
        cast = []
        for e in r.get("entities", []) or []:
            nid = node(e.get("name", ""), e.get("kind", ""))
            if nid:
                cast.append(nid)
                for f in (e.get("aliases") or [])[:5]:
                    if f and f not in nodes[nid]["forms"]:
                        nodes[nid]["forms"].append(f)
        for rel in r.get("relationships", []) or []:
            s_id = node(rel.get("src", ""))
            d_id = node(rel.get("dst", ""))
            if s_id and d_id and (s_id, rel.get("rel"), d_id) not in seen_edge:
                seen_edge.add((s_id, rel.get("rel"), d_id))
                edges.append({"src": s_id, "dst": d_id, "rel": rel.get("rel", "linked"),
                              "src_name": rel.get("src"), "dst_name": rel.get("dst")})
        beats.append({
            "i": i,
            "title": s.get("title", "") or (r.get("_provenance", {}) or {}).get("chapter_label", "") or f"Part {i+1}",
            "summary": (r.get("chapter_summary") or "").strip(),
            "cast": cast[:12],
        })

    return {
        "id": _slug(stem),
        "title": _TITLE.get(stem, stem.replace("_", " ").title()),
        "nodes": list(nodes.values()),
        "edges": edges,
        "beats": beats,
    }


def main():
    os.makedirs(os.path.join(WEB, "corpora"), exist_ok=True)
    index = []
    for path in sorted(glob.glob(os.path.join(OUT, "*.records.jsonl"))):
        data = build_one(path)
        if not data:
            continue
        out_path = os.path.join(WEB, "corpora", f"{data['id']}.json")
        json.dump(data, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
        index.append({"id": data["id"], "title": data["title"],
                      "n_beats": len(data["beats"]), "n_nodes": len(data["nodes"])})
    # sort index: richest stories first, Ramayana pinned for the default
    index.sort(key=lambda x: (x["id"] != "ramayana", -x["n_beats"]))
    json.dump(index, open(os.path.join(WEB, "corpora.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"exported {len(index)} corpora")
    for c in index:
        print(f"  {c['id']:16} {c['n_beats']:>4} beats  {c['n_nodes']:>4} nodes  — {c['title']}")


if __name__ == "__main__":
    main()
