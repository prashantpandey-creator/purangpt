"""graph_rebuild — rebuild graph_manifest.json from only the real (non-quarantined) records.

Loads per-text .records.jsonl from the out/ dir, scrubs hallucinated citations,
runs graph.build(manifest_mode=True), applies identity edge merges (same_as only —
avatar_of/aspect_of stay as typed edges), prunes isolated nodes (degree 0), and
writes the new manifest.

Input contract:  run(dry_run=False) -> envelope
Output contract: envelope.data = {n_entities_before, n_entities_after, n_edges_before,
                                   n_edges_after, merges_applied, isolates_pruned,
                                   cites_scrubbed}
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple


_BASE = os.path.join(os.path.dirname(__file__), "..", "read_pass")
_RECORDS_DIR = os.path.join(_BASE, "out")
_IDENTITY_PATH = os.path.join(_RECORDS_DIR, "identity_edges.json")
_CURATED_PATH = os.path.join(_RECORDS_DIR, "curated_facts.json")
_MANIFEST_PATH = os.path.join(_RECORDS_DIR, "graph_manifest.json")
_CHUNKS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chunks", "all_chunks.jsonl")
_RAW_TEXTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw_texts")

_MARKER_RE = re.compile(r'\b[A-Za-z]{1,6}_\d+(?:[.\-]\d+)*\b')

_CHUNKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chunks")

_SUPPLEMENTARY_MARKER_SOURCES = {
    "mahabharata": os.path.join(_RAW_TEXTS_DIR, "mahabharata_bori", "mahabharata_marked.txt"),
    "skanda purana": os.path.join(_RAW_TEXTS_DIR, "skanda_gretil", "skandapurana_leiden_marked.txt"),
    # Guruji's biography decodes into the same graph; its awk_ markers live in a
    # separate chunk file, not all_chunks.jsonl, so register it explicitly.
    "the awakener": os.path.join(_CHUNKS_DIR, "awakener_chunks.jsonl"),
}
_NODE_FIELDS = ("entities", "relationships", "teachings")


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _detect_marker_prefixes(chunks_path: str) -> Dict[str, set]:
    """Scan source chunks to find which texts have canonical verse markers.

    Returns {text_key_lower: set_of_marker_prefixes}. A text with no markers
    gets an empty set — its records' verse_ranges are hallucinated.
    """
    text_prefixes: Dict[str, set] = {}
    if not os.path.exists(chunks_path):
        return text_prefixes
    with open(chunks_path) as f:
        for line in f:
            ch = json.loads(line)
            text = (ch.get("purana") or "").lower()
            if not text:
                cid = (ch.get("id") or "").lower()
                for t in cid.split("-"):
                    if t and not t.isdigit():
                        text = t
                        break
            if not text:
                continue
            markers = _MARKER_RE.findall(ch.get("text", ""))
            prefixes = {m.split("_")[0].lower() for m in markers if "_" in m}
            text_prefixes.setdefault(text, set()).update(prefixes)

    for text_key, marked_path in _SUPPLEMENTARY_MARKER_SOURCES.items():
        if not os.path.exists(marked_path):
            continue
        with open(marked_path) as f:
            content = f.read()
        markers = _MARKER_RE.findall(content)
        prefixes = {m.split("_")[0].lower() for m in markers if "_" in m}
        if prefixes:
            text_prefixes.setdefault(text_key, set()).update(prefixes)

    return text_prefixes


def scrub_hallucinated_cites(
    records: List[Dict], text_key: str, source_prefixes: Dict[str, set]
) -> Tuple[List[Dict], Dict[str, int]]:
    """Strip hallucinated verse_ranges from records.

    Two scrub rules:
    1. If the source text has NO markers at all, blank ALL verse_ranges.
    2. If the source text has markers, strip any cite whose prefix doesn't
       match the source's own prefix set (e.g. bhp_ on a Brahma Purana record
       that should only have BrP_ markers).
    """
    # strip version (_v1/_v2/_proof) AND corpus-source (_bori/_gretil/_leiden/
    # _inhouse/_critical) suffixes so the decode tag maps to the prefix-map key
    text_lower = text_key.lower()
    for suffix in ("_v1", "_v2", "_proof", "_inhouse", "_bori", "_gretil",
                   "_leiden", "_critical", "_chunks"):
        text_lower = text_lower.replace(suffix, "")
    text_lower = text_lower.strip("_ ")
    own_prefixes = source_prefixes.get(text_lower, set())
    if not own_prefixes:
        # bidirectional fuzzy match: 'mahabharata' is a substring of the key, OR
        # the key is a substring of the cleaned tag
        for key, prefixes in source_prefixes.items():
            if text_lower in key or key in text_lower or key.startswith(text_lower):
                own_prefixes = prefixes
                break
    is_bhagavata = "bhagavata" in text_lower

    stats = {"blanked_records": 0, "stripped_cites": 0, "total_cites": 0}
    scrubbed = []
    for rec in records:
        rec = json.loads(json.dumps(rec))
        for field in _NODE_FIELDS:
            for node in rec.get(field) or []:
                vr = node.get("verse_ranges") or []
                stats["total_cites"] += len(vr)
                if not own_prefixes:
                    if vr:
                        stats["stripped_cites"] += len(vr)
                        stats["blanked_records"] += 1
                    node["verse_ranges"] = []
                else:
                    clean = []
                    for cite in vr:
                        m = _MARKER_RE.search(str(cite))
                        if m:
                            prefix = m.group(0).split("_")[0].lower()
                            if prefix in own_prefixes or is_bhagavata:
                                clean.append(cite)
                            else:
                                stats["stripped_cites"] += 1
                        else:
                            stats["stripped_cites"] += 1
                    node["verse_ranges"] = clean
        scrubbed.append(rec)
    return scrubbed, stats


def _load_all_records(records_dir: str) -> Tuple[List[Dict], Dict[str, int], Dict[str, List[Dict]]]:
    all_records = []
    per_text = {}
    by_text: Dict[str, List[Dict]] = {}
    for fname in sorted(os.listdir(records_dir)):
        if not fname.endswith(".records.jsonl"):
            continue
        text_key = fname.replace(".records.jsonl", "")
        fpath = os.path.join(records_dir, fname)
        text_recs = []
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if line:
                    text_recs.append(json.loads(line))
        per_text[text_key] = len(text_recs)
        by_text[text_key] = text_recs
        all_records.extend(text_recs)
    return all_records, per_text, by_text


def apply_identity_merges(
    entities: List[Dict], edges: List[Dict], identity_edges: List[Dict]
) -> Tuple[List[Dict], List[Dict], Dict[str, Any]]:
    # CRITICAL: only NAME-VARIANT same_as edges are real entity identity
    # (Krsna = Kṛṣṇa). The 'rel: is' edges are theological identifications pulled
    # from "X is Y" statements in the text ("Shiva is Vishnu", "Krishna is the
    # Supreme Brahman") — devotional non-dualism, NOT entity equality. Merging
    # those transitively welds the entire pantheon into one Vishnu blob (2,458
    # aliases) and destroys retrieval. They belong as aspect_of EDGES (traversable
    # unity), never as merges.
    same_as = [ie for ie in identity_edges
               if ie.get("type") == "same_as"
               and str(ie.get("evidence", "")).startswith("name variant")]

    id_to_entity = {e["id"]: e for e in entities}
    merge_map: Dict[str, str] = {}

    def find(x):
        while merge_map.get(x, x) != x:
            x = merge_map[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        if ra not in id_to_entity or rb not in id_to_entity:
            return False
        ea, eb = id_to_entity[ra], id_to_entity[rb]
        if len(ea.get("all_forms", [])) >= len(eb.get("all_forms", [])):
            winner, loser = ra, rb
        else:
            winner, loser = rb, ra
        merge_map[loser] = winner
        return True

    merges_applied = 0
    for ie in same_as:
        src, dst = ie["src"], ie["dst"]
        if src in id_to_entity and dst in id_to_entity:
            if union(src, dst):
                merges_applied += 1

    groups: Dict[str, List[str]] = {}
    for eid in id_to_entity:
        root = find(eid)
        groups.setdefault(root, []).append(eid)

    new_entities = []
    for root, members in groups.items():
        base = dict(id_to_entity[root])
        all_forms = set(base.get("all_forms", []))
        chapters = set(base.get("chapters", []))
        verse_ranges = list(base.get("verse_ranges", []))
        for m in members:
            if m == root:
                continue
            other = id_to_entity[m]
            all_forms.update(other.get("all_forms", []))
            chapters.update(other.get("chapters", []))
            verse_ranges.extend(other.get("verse_ranges", []))
        base["all_forms"] = sorted(all_forms)
        base["chapters"] = sorted(chapters)
        base["verse_ranges"] = sorted(set(verse_ranges))
        new_entities.append(base)

    resolved = {eid: find(eid) for eid in id_to_entity}
    new_edges = []
    seen_edges = set()
    for e in edges:
        src = resolved.get(e["src"], e["src"])
        dst = resolved.get(e["dst"], e["dst"])
        if src == dst:
            continue
        dedup_key = (src, e["rel"], dst)
        if dedup_key in seen_edges:
            continue
        seen_edges.add(dedup_key)
        new_e = dict(e)
        new_e["src"] = src
        new_e["dst"] = dst
        src_ent = id_to_entity.get(src)
        dst_ent = id_to_entity.get(dst)
        if src_ent:
            new_e["src_name"] = src_ent["name"]
        if dst_ent:
            new_e["dst_name"] = dst_ent["name"]
        new_edges.append(new_e)

    stats = {"merges_applied": merges_applied, "groups": len(groups)}
    return new_entities, new_edges, stats


def apply_curated_facts(
    entities: List[Dict], edges: List[Dict], curated: Dict[str, Any]
) -> Tuple[List[Dict], List[Dict], Dict[str, Any]]:
    """Apply human-verified ground-truth AFTER decode/merge, BEFORE isolate-prune.

    The decode under-extracts some critical facts (Guruji's real Lahiri-family
    lineage) and over-extracts wrong ones (the popular Yogananda chain, backwards
    guru/disciple edges). This overlay is the corrective: it ADDS missing entities
    + edges, and REMOVES decode edges matching a removal pattern. Curated facts win
    over the LLM — that's the whole point.

    curated = {entities:[...], lineage_edges:[...], remove_edges:[{src_contains,
               rel, dst_contains, reason}]}
    """
    stats = {"entities_added": 0, "edges_added": 0, "edges_removed": 0}
    by_id = {e["id"]: e for e in entities}

    # 1. Remove decode edges matching any removal pattern (wrong/backwards edges)
    removals = curated.get("remove_edges", []) or []
    kept_edges = []
    for e in edges:
        src = str(e.get("src", "")).lower()
        dst = str(e.get("dst", "")).lower()
        rel = str(e.get("rel", "")).lower()
        drop = False
        for rm in removals:
            sc = str(rm.get("src_contains", "")).lower()
            dc = str(rm.get("dst_contains", "")).lower()
            rr = str(rm.get("rel", "")).lower()
            if (not sc or sc in src) and (not dc or dc in dst) and (not rr or rr in rel):
                drop = True
                break
        if drop:
            stats["edges_removed"] += 1
        else:
            kept_edges.append(e)

    # 2. Add curated entities (override if id already exists — curated wins)
    for ce in curated.get("entities", []) or []:
        cid = ce["id"]
        if cid in by_id:
            ent = by_id[cid]
            forms = set(ent.get("all_forms", [])) | set(ce.get("all_forms", []))
            ent["all_forms"] = sorted(forms)
            if ce.get("kind"):
                ent["kind"] = ce["kind"]
        else:
            new_ent = {
                "id": cid, "name": ce["name"], "kind": ce.get("kind", "sage"),
                "all_forms": ce.get("all_forms", [ce["name"]]),
                "chapters": [], "verse_ranges": [],
            }
            by_id[cid] = new_ent
            entities.append(new_ent)
            stats["entities_added"] += 1

    # 3. Add curated lineage edges (dedup against existing)
    seen = {(str(e.get("src", "")).lower(), str(e.get("rel", "")).lower(),
             str(e.get("dst", "")).lower()) for e in kept_edges}
    for le in curated.get("lineage_edges", []) or []:
        key = (str(le["src"]).lower(), str(le["rel"]).lower(), str(le["dst"]).lower())
        if key in seen:
            continue
        seen.add(key)
        kept_edges.append(dict(le))
        stats["edges_added"] += 1

    # 4. split_forms: move epithets off a conflated host onto their rightful node.
    # The graph.py bare-name guard severs "Balarama" from Rama, but distinct EPITHETS
    # (Halayudha, Jamadagnyamahadarpadalana) arrive one level deeper and slip through.
    # This is the human-verified override for that residue.
    for sp in curated.get("split_forms", []) or []:
        host = by_id.get(sp.get("from_id"))
        dest = by_id.get(sp.get("to_id"))
        if not host:
            continue
        move = set(sp.get("forms", []))
        host_forms = set(host.get("all_forms", []))
        moved = move & host_forms
        if not moved:
            continue
        host["all_forms"] = sorted(host_forms - moved)
        if dest is not None:
            dest["all_forms"] = sorted(set(dest.get("all_forms", [])) | moved)
        stats["forms_moved"] = stats.get("forms_moved", 0) + len(moved)

    return entities, kept_edges, stats


def prune_isolates(
    entities: List[Dict], edges: List[Dict]
) -> Tuple[List[Dict], int]:
    connected = set()
    for e in edges:
        connected.add(e["src"])
        connected.add(e["dst"])
    pruned = [e for e in entities if e["id"] in connected]
    return pruned, len(entities) - len(pruned)


def run(dry_run: bool = False, records_dir: str = "",
        identity_path: str = "", manifest_path: str = "",
        chunks_path: str = "", curated_path: str = "") -> Dict[str, Any]:
    records_dir = records_dir or os.path.abspath(_RECORDS_DIR)
    identity_path = identity_path or os.path.abspath(_IDENTITY_PATH)
    manifest_path = manifest_path or os.path.abspath(_MANIFEST_PATH)
    chunks_path = chunks_path or os.path.abspath(_CHUNKS_PATH)
    curated_path = curated_path or os.path.abspath(_CURATED_PATH)
    metadata = {
        "records_dir": records_dir,
        "identity_path": identity_path,
        "manifest_path": manifest_path,
        "dry_run": dry_run,
    }

    if not os.path.isdir(records_dir):
        return _envelope(False, None, metadata,
                         [{"code": "missing_dir", "message": f"not found: {records_dir}"}])

    _, per_text, by_text = _load_all_records(records_dir)
    if not by_text:
        return _envelope(False, None, metadata,
                         [{"code": "no_records", "message": "no .records.jsonl in dir"}])

    source_prefixes = _detect_marker_prefixes(chunks_path)

    all_records = []
    total_scrub_stats = {"blanked_records": 0, "stripped_cites": 0, "total_cites": 0}
    per_text_scrub = {}
    for text_key, recs in sorted(by_text.items()):
        scrubbed, stats = scrub_hallucinated_cites(recs, text_key, source_prefixes)
        all_records.extend(scrubbed)
        per_text_scrub[text_key] = stats
        for k in total_scrub_stats:
            total_scrub_stats[k] += stats[k]

    from tools.read_pass.graph import build
    g = build(all_records, manifest_mode=True)

    n_entities_before = len(g.entities)
    n_edges_before = len(g.edges)

    identity_edges = []
    if os.path.exists(identity_path):
        with open(identity_path) as f:
            ie_data = json.load(f)
        identity_edges = ie_data.get("data", {}).get("identity_edges", [])

    entities, edges, merge_stats = apply_identity_merges(
        g.entities, g.edges, identity_edges
    )

    # curated ground-truth overlay (verified facts override decode errors) —
    # applied BEFORE prune so curated entities connected by curated edges survive
    curated_stats = {"entities_added": 0, "edges_added": 0, "edges_removed": 0}
    if os.path.exists(curated_path):
        with open(curated_path) as f:
            curated = json.load(f)
        entities, edges, curated_stats = apply_curated_facts(entities, edges, curated)

    entities, n_pruned = prune_isolates(entities, edges)

    manifest = {
        "entities": entities,
        "edges": edges,
        "n_entities": len(entities),
        "n_edges": len(edges),
    }

    if not dry_run:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, ensure_ascii=False)

    data = {
        "n_entities_before": n_entities_before,
        "n_entities_after": len(entities),
        "n_edges_before": n_edges_before,
        "n_edges_after": len(edges),
        "merges_applied": merge_stats["merges_applied"],
        "curated": curated_stats,
        "isolates_pruned": n_pruned,
        "cites_scrubbed": total_scrub_stats,
        "per_text_scrub": per_text_scrub,
        "per_text_records": per_text,
        "dry_run": dry_run,
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    dry_run = "--dry-run" in argv

    env = run(dry_run=dry_run)

    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        mode = "DRY RUN" if dry_run else "REBUILT"
        print(f"=== GRAPH {mode} ===")
        print(f"Entities: {d['n_entities_before']:,} → {d['n_entities_after']:,}")
        print(f"Edges:    {d['n_edges_before']:,} → {d['n_edges_after']:,}")
        print(f"Identity merges applied: {d['merges_applied']}")
        print(f"Isolates pruned: {d['isolates_pruned']}")
        cs = d.get("cites_scrubbed", {})
        if cs.get("stripped_cites"):
            print(f"\nCitation scrub: {cs['stripped_cites']:,} hallucinated cites "
                  f"stripped of {cs['total_cites']:,} total")
            for text, stats in sorted(d.get("per_text_scrub", {}).items()):
                if stats.get("stripped_cites"):
                    print(f"  {text}: {stats['stripped_cites']:,} stripped "
                          f"({stats['total_cites']:,} total)")
        print(f"\nPer-text record counts:")
        for text, count in sorted(d["per_text_records"].items()):
            print(f"  {text}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
