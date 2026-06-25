"""graph — merge flat chapter records into ONE interconnected knowledge graph.

The graph is GENERAL: it does NOT hardcode a relationship vocabulary. Every verb
the read-pass produced (580+ distinct, 343 once-only) is kept as a first-class
predicate. Normalization is purely mechanical (see predicate.py): syntactic
cleanup + inverse detection, no semantic categories baked in. Semantic grouping
("teaches"~"instructs") is a query-time concern (views/), not a build-time schema.

Daddy's example asks (lineages, curses, who-did-whom) are just QUERIES over the
general graph — edges_of_kind(pred) / descendants_via(preds) — not special-cased
schema. They drive downstream views (comics, trivia), never the graph itself.

Zero LLM calls. Pure deterministic merge of the read-pass records.

JSON contract (Rule 0, precond B):
  run(records) -> {success, data:{n_entities, n_edges, ...}, metadata, errors}
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from tools.read_pass import predicate

# ── name normalization ─────────────────────────────────────────────────────
# COMBINING MACRON (U+0304) encodes vowel length, which marks gender in
# Sanskrit (Kṛṣṇa=masc vs Kṛṣṇā=fem). Stripping it merges distinct people.
_MACRON = "̄"

def _norm(s: str) -> str:
    """Strip diacritics EXCEPT macrons + lowercase + collapse whitespace."""
    if s is None:
        return ""
    nf = unicodedata.normalize("NFKD", str(s))
    no_diacritics = "".join(c for c in nf
                            if not unicodedata.combining(c) or c == _MACRON)
    return re.sub(r"\s+", " ", no_diacritics.strip().lower())


def _strip_key(s: str) -> str:
    """Fully diacritic-stripped key — Krsna == Kṛṣṇa (transliteration variants)."""
    if s is None:
        return ""
    nf = unicodedata.normalize("NFKD", str(s))
    kept = "".join(c for c in nf if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", kept.strip().lower())


def _same_strip(a: str, b: str) -> bool:
    """Same name modulo transliteration noise (Krishna/Krsna/Kṛṣṇa all equal).

    Reduces each name to a consonant skeleton: drop ALL vowels and the 'h' that
    only marks aspiration/digraphs (sh, kh, th...). 'krishna'→'krsn', 'krsna'→
    'krsn', 'kṛṣṇa'→'krsn' all collapse — but Buddha('bdh')≠Vishnu('vsn') never do.
    """
    def skel(x):
        k = _strip_key(x)
        k = re.sub(r"[aeiou]", "", k)      # drop vowels (transliteration padding)
        k = re.sub(r"h", "", k)            # drop aspiration/digraph 'h'
        return re.sub(r"\s+", "", k)
    return skel(a) == skel(b)


# ── relationship normalization ─────────────────────────────────────────────
# NO hardcoded vocabulary. Direction + syntactic cleanup only, via predicate.py.
# Every distinct verb survives as its own predicate.
def _normalize_predicate(raw: str) -> Tuple[str, bool]:
    """Return (canonical_predicate, reverse). Mechanical — see predicate.py."""
    return predicate.canonical(raw)


# ── entity merge (union-find via alias closure) ────────────────────────────
class _UF:
    def __init__(self):
        self.parent: Dict[str, str] = {}

    def add(self, x: str):
        if x not in self.parent:
            self.parent[x] = x

    def find(self, x: str) -> str:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


# ── the graph ──────────────────────────────────────────────────────────────
class Graph:
    def __init__(self):
        self.entities: List[Dict[str, Any]] = []   # merged nodes
        self.edges: List[Dict[str, Any]] = []      # normalized + deduped
        self._by_norm: Dict[str, str] = {}         # norm name -> entity id
        self._overlaps: Dict[Tuple[str, str], set] = {}

    def find_entity(self, name: str) -> Optional[Dict[str, Any]]:
        eid = self._by_norm.get(_norm(name))
        if eid is None:
            return None
        return next((e for e in self.entities if e["id"] == eid), None)

    def alias_overlaps(self) -> Dict[Tuple[str, str], set]:
        """Pairs of distinct entities that share at least one alias."""
        return self._overlaps

    def predicates(self) -> Dict[str, int]:
        """The discovered predicate vocabulary + counts (no hardcoding)."""
        out: Dict[str, int] = {}
        for e in self.edges:
            out[e["rel"]] = out.get(e["rel"], 0) + 1
        return out

    def edges_of_kind(self, *preds: str) -> List[Dict[str, Any]]:
        """Edges whose canonical predicate is any of `preds`. General: the
        caller decides which predicate(s) constitute 'lineage' or 'curse' —
        the graph does not bless any predicate as special."""
        want = set(preds)
        return [e for e in self.edges if e["rel"] in want]

    def traverse(self, name: str, preds) -> List[Dict[str, Any]]:
        """Transitive closure over the given predicate set from `name`.
        Used by lineage views (preds={'father','mother',...}) but generic."""
        want = set(preds) if not isinstance(preds, str) else {preds}
        start = self.find_entity(name)
        if start is None:
            return []
        out, seen, stack = [], {start["id"]}, [start["id"]]
        while stack:
            cur = stack.pop()
            for e in self.edges:
                if e["rel"] in want and e["src"] == cur and e["dst"] not in seen:
                    seen.add(e["dst"])
                    node = next((x for x in self.entities if x["id"] == e["dst"]), None)
                    if node:
                        out.append(node)
                        stack.append(e["dst"])
        return out

    # convenience aliases for the common downstream views — these name a
    # predicate SET, they do not hardcode it into the graph build.
    LINEAGE_PREDS = {"father", "mother", "parent", "grandfather", "grandmother",
                     "son", "daughter", "child"}
    CURSE_PREDS = {"cursed", "curses", "curse"}

    def descendants_of(self, name: str) -> List[Dict[str, Any]]:
        return self.traverse(name, self.LINEAGE_PREDS)

    def curses(self) -> List[Dict[str, Any]]:
        out = []
        for e in self.edges_of_kind(*self.CURSE_PREDS):
            out.append({"src_name": e["src_name"], "dst_name": e["dst_name"],
                        "chapters": e["chapters"], "verse_ranges": e["verse_ranges"]})
        return out


# Supreme-deity epithets shared DELIBERATELY across MULTIPLE distinct high gods.
# In manifest mode, a shared epithet between two deities must NOT drive a union
# (that chains Buddha→Vishnu→Hari→Krishna→Brahma into one blob) — it becomes an
# identity EDGE (typed later by identity.py).
#
# CRITICAL: this set contains ONLY cross-identity TITLES (the abstract supreme
# names many deities legitimately bear), NEVER a deity's own proper name. Putting
# "Krishna"/"Govinda" here would sever real spelling-variant merges (Krsna=Kṛṣṇa),
# because those proper names also appear as aliases of themselves. Titles only.
_SUPREME_EPITHETS = {
    _norm(x) for x in (
        "Hari", "Narayana", "Nārāyaṇa", "Ishwar", "Ishvara", "Iśvara",
        "Bhagavan", "Bhagwan", "Bhagavān", "Parameshwar", "Parameśvara",
        "Parabrahma", "Paramatma", "Paramātmā", "Purushottama", "Puruṣottama",
        "Jagannatha", "Jagannāth", "Prabhu", "Bhagavanta", "Adideva", "Ādideva",
        "Maheshwar", "Maheśvara", "Adipurusha", "Ādipuruṣa", "Achyuta", "Acyuta",
    )
}


def build(records: List[Dict[str, Any]], manifest_mode: bool = False) -> Graph:
    """The whole merge: records → Graph.

    manifest_mode=True applies the deity-epithet guard: two DEITY canonicals are
    not unioned just because one lists a shared *supreme epithet* as an alias.
    This severs the Buddha-blob chain; the link is preserved as an overlap for
    identity.py to type as a ground-layer edge. Pure spelling variants and all
    non-deity merges behave exactly as in the default mode.
    """
    g = Graph()

    # Pass 1: collect all entity mentions and seed union-find with name-aliases
    uf = _UF()
    mentions: List[Tuple[str, Dict[str, Any], str]] = []  # (norm_name, raw_mention, chapter)
    name_to_aliases_chain: Dict[str, set] = {}
    # track the predominant 'kind' for each canonical name
    name_to_kinds: Dict[str, Dict[str, int]] = {}

    # Aliases that describe a RELATIONSHIP (not a name) must not drive merges.
    # "avatar of Vishnu", "incarnation of the Lord" → these belong as edges.
    _REL_ALIAS_PATTERNS = re.compile(
        r"\b(?:avatar|avatara|avatār|avatāra|incarnation|manifestation|"
        r"expansion|form\s+of|aspect\s+of|born\s+from|son\s+of|"
        r"daughter\s+of|wife\s+of|husband\s+of)\b", re.I)

    for r in records:
        ch = r.get("_provenance", {}).get("chapter_label", "?")
        for e in r.get("entities", []) or []:
            name_raw = e.get("name", "")
            nname = _norm(name_raw)
            if not nname:
                continue
            uf.add(nname)
            mentions.append((nname, e, ch))
            # filter out relationship-descriptive aliases before merging
            aliases = {_norm(a) for a in (e.get("aliases") or [])
                       if a and not _REL_ALIAS_PATTERNS.search(a)}
            name_to_aliases_chain.setdefault(nname, set()).update(aliases)
            kind = (e.get("kind") or "").lower().strip()
            if kind:
                name_to_kinds.setdefault(nname, {})
                name_to_kinds[nname][kind] = name_to_kinds[nname].get(kind, 0) + 1

    def _dominant_kind(nname: str) -> str:
        kinds = name_to_kinds.get(nname, {})
        return max(kinds, key=kinds.get) if kinds else ""

    # Kinds that must never be merged with each other
    _INCOMPATIBLE_KIND_PAIRS = {
        frozenset({"deity", "demon"}),
        frozenset({"deity", "king"}),
        frozenset({"deity", "human"}),
        frozenset({"deity", "sage"}),  # sages can be divine but deities ≠ sages
        frozenset({"demon", "king"}),
        frozenset({"demon", "sage"}),
        frozenset({"king", "sage"}),
        frozenset({"warrior", "sage"}),
    }

    def _kinds_compatible(a: str, b: str) -> bool:
        if not a or not b or a == b:
            return True
        return frozenset({a, b}) not in _INCOMPATIBLE_KIND_PAIRS

    # Decide which aliases are *shared* between canonicals — those become overlaps,
    # NOT merges (Krishna/Vishnu/Hari problem: both claim Hari, both are real).
    canonicals = set(name_to_aliases_chain.keys())
    alias_to_canonicals: Dict[str, set] = {}
    for canon, als in name_to_aliases_chain.items():
        for a in als:
            alias_to_canonicals.setdefault(a, set()).add(canon)
            if a in canonicals:
                alias_to_canonicals[a].add(a)  # the alias is ITSELF a canonical

    # Union an alias into its canonical ONLY if:
    # (a) no other canonical claims that alias AND
    # (b) the alias's kind is compatible with the canonical's kind AND
    # (c) [manifest mode] the alias is not a supreme-deity epithet linking two
    #     deities — that link belongs as a typed identity EDGE, not a merge.
    for a, canons in alias_to_canonicals.items():
        canons_minus_self = canons - {a}
        if len(canons_minus_self) == 1:
            canon = next(iter(canons_minus_self))
            canon_kind = _dominant_kind(canon)
            alias_kind = _dominant_kind(a)
            # Manifest mode: two DISTINCT deity canonicals must not auto-merge
            # via a shared alias — that is exactly the Buddha→Vishnu→Hari→Krishna
            # chaining that builds the blob. Such a link (avatar/aspect/epithet)
            # belongs as a TYPED identity edge (identity.py), not a node merge.
            # Guard fires only when BOTH are deities AND they are genuinely
            # different names (Krsna==Kṛṣṇa spelling variants are NOT severed).
            both_deity = canon_kind == "deity" and alias_kind == "deity"
            distinct_names = not _same_strip(canon, a)
            blob_link = a in _SUPREME_EPITHETS or a in canonicals
            if manifest_mode and both_deity and distinct_names and blob_link:
                continue  # sever the blob chain; recorded as overlap in Pass 3
            # PEER-NAME CONFUSION GUARD: the decoder sometimes lists a DISTINCT,
            # independently-substantial being as an alias because they share a
            # name-fragment (Rama←Balarama/Parashurama, Indra←Shahindra). If the
            # alias is ITSELF a canonical that stands on its own (own records →
            # its own aliases or kind), a single stray cross-mention must NOT
            # absorb it. Keep both; record the link as an overlap in Pass 3.
            # (Pure spelling variants are exempt: _same_strip catches Krsna=Kṛṣṇa,
            # and a canonical with NO independent footprint isn't "substantial".)
            alias_is_substantial = (
                a in canonicals
                and distinct_names
                and (bool(name_to_aliases_chain.get(a)) or bool(name_to_kinds.get(a)))
            )
            if manifest_mode and alias_is_substantial:
                continue  # peer-name confusion; severed, recorded as overlap
            if _kinds_compatible(canon_kind, alias_kind):
                uf.union(canon, a)
        # else: shared alias → leave separate, record overlap below

    # Pass 2: realize merged entity nodes
    cluster_to_node: Dict[str, Dict[str, Any]] = {}
    for nname, e, ch in mentions:
        root = uf.find(nname)
        node = cluster_to_node.get(root)
        if node is None:
            node = {"id": root, "name": e.get("name", root),
                    "kind": e.get("kind", ""),
                    "all_forms": set(), "chapters": set(), "verse_ranges": []}
            cluster_to_node[root] = node
            g.entities.append(node)
            g._by_norm[nname] = root
        node["all_forms"].add(e.get("name", root))
        for a in (e.get("aliases") or []):
            # Don't absorb an alias that is itself a DISTINCT canonical resolving
            # to a different node — that is the peer-name leak (Rama's record lists
            # "Balarama"; severing the union isn't enough, the bare name must also
            # be kept out of Rama's forms). It belongs to its own node.
            na = _norm(a)
            if na in canonicals and uf.find(na) != root:
                continue
            node["all_forms"].add(a)
        node["chapters"].add(ch)
        node["verse_ranges"].extend(e.get("verse_ranges", []) or [])
        # remember the norm→id mapping for every alias too, so find_entity works
        for a in (e.get("aliases") or []):
            na = _norm(a)
            if na in canonicals and uf.find(na) != root:
                continue  # peer canonical owns its own norm→id mapping
            g._by_norm.setdefault(na, root)

    # Convert sets→sorted lists for JSON serializability
    for node in g.entities:
        node["all_forms"] = sorted(node["all_forms"])
        node["chapters"] = sorted(node["chapters"])

    # Pass 3: record alias overlaps between *distinct* entities
    for a, canons in alias_to_canonicals.items():
        # resolve each canonical to its merged root
        roots = {uf.find(c) for c in canons}
        if len(roots) >= 2:
            roots_l = sorted(roots)
            for i in range(len(roots_l)):
                for j in range(i + 1, len(roots_l)):
                    key = (roots_l[i], roots_l[j])
                    g._overlaps.setdefault(key, set()).add(a)

    # Pass 4: normalize + dedupe edges
    edge_key_to_idx: Dict[Tuple[str, str, str], int] = {}
    for r in records:
        ch = r.get("_provenance", {}).get("chapter_label", "?")
        for rel in r.get("relationships", []) or []:
            src_raw, dst_raw = rel.get("src"), rel.get("dst")
            if not (src_raw and dst_raw):
                continue
            src_norm = _norm(src_raw)
            dst_norm = _norm(dst_raw)
            uf.add(src_norm); uf.add(dst_norm)
            src_id = uf.find(src_norm)
            dst_id = uf.find(dst_norm)
            # ensure phantom entities (mentioned only in rels) get a node
            for raw, nid, nname in [(src_raw, src_id, src_norm),
                                    (dst_raw, dst_id, dst_norm)]:
                if not any(e["id"] == nid for e in g.entities):
                    n = {"id": nid, "name": raw, "kind": "",
                         "all_forms": [raw], "chapters": [ch], "verse_ranges": []}
                    g.entities.append(n)
                    g._by_norm[nname] = nid
            pred, reverse = _normalize_predicate(rel.get("rel", ""))
            if reverse:
                src_id, dst_id = dst_id, src_id
            key = (src_id, pred, dst_id)
            if key in edge_key_to_idx:
                e = g.edges[edge_key_to_idx[key]]
                e["chapters"].append(ch)
                e["verse_ranges"].extend(rel.get("verse_ranges", []) or [])
                e["chapters"] = sorted(set(e["chapters"]))
            else:
                edge = {"src": src_id, "rel": pred, "dst": dst_id,
                        "src_name": next((x["name"] for x in g.entities
                                          if x["id"] == src_id), src_id),
                        "dst_name": next((x["name"] for x in g.entities
                                          if x["id"] == dst_id), dst_id),
                        "chapters": [ch],
                        "verse_ranges": list(rel.get("verse_ranges", []) or [])}
                edge_key_to_idx[key] = len(g.edges)
                g.edges.append(edge)

    return g


# ── JSON contract ──────────────────────────────────────────────────────────
def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(records_or_path, manifest_mode: bool = True) -> Dict[str, Any]:
    md = {"manifest_mode": manifest_mode}
    if isinstance(records_or_path, str):
        md["path"] = records_or_path
        try:
            records = [json.loads(l) for l in open(records_or_path) if l.strip()]
        except OSError as e:
            return _envelope(False, None, md,
                             [{"code": "read_error", "message": str(e)}])
    else:
        records = records_or_path

    if not records:
        return _envelope(False, None, md,
                         [{"code": "empty", "message": "no records"}])

    g = build(records, manifest_mode=manifest_mode)
    # predicate distribution
    pred_counts: Dict[str, int] = {}
    for e in g.edges:
        pred_counts[e["rel"]] = pred_counts.get(e["rel"], 0) + 1

    data = {
        "n_records": len(records),
        "n_entities": len(g.entities),
        "n_edges": len(g.edges),
        "n_alias_overlaps": len(g._overlaps),
        "predicate_distribution": pred_counts,
        "top_entities_by_chapters": [
            {"name": e["name"], "chapters": len(e["chapters"]),
             "n_forms": len(e["all_forms"])}
            for e in sorted(g.entities, key=lambda x: -len(x["chapters"]))[:15]
        ],
        "n_distinct_predicates": len(pred_counts),
        "lineage_edges": sum(pred_counts.get(p, 0) for p in Graph.LINEAGE_PREDS),
        "curse_edges": sum(pred_counts.get(p, 0) for p in Graph.CURSE_PREDS),
        "avatar_edges": pred_counts.get("avatar", 0) + pred_counts.get("incarnation", 0),
    }
    return _envelope(True, data, md, [])


def main(argv: List[str]) -> int:
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    path = arg("--records",
               "tools/read_pass/out/bhagavata_full.records.jsonl")
    env = run(path)
    if "--json" in argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message']}")
        return 2
    else:
        d = env["data"]
        print(f"OK: {d['n_records']} chapters → "
              f"{d['n_entities']} merged entities, {d['n_edges']} unique edges, "
              f"{d['n_distinct_predicates']} distinct predicates (discovered, not hardcoded)")
        print(f"    lineage: {d['lineage_edges']}, curses: {d['curse_edges']}, "
              f"avatars: {d['avatar_edges']}, alias-overlaps: {d['n_alias_overlaps']}")
        print(f"    top entities by chapter-presence:")
        for e in d["top_entities_by_chapters"][:8]:
            print(f"      {e['name']} ({e['n_forms']} forms, "
                  f"{e['chapters']} chapters)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
