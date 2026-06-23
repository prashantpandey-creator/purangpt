"""identity — the two-layer identity model (manifest nodes + ground edges).

Inspired by Sharma: "It is the Time Itself that appears as if It is divided...
despite being standstill." The One appears as many. So the graph keeps every
manifestation as a distinct node and connects them with TYPED IDENTITY EDGES —
it never collapses entities by shared alias (which over-merged Buddha→Vishnu→
Brahma into one 648-form blob across the corpus).

Identity edges (the ground layer):
  same_as     — same manifest entity, different spelling/text (Rāma = rama)
  avatar_of   — distinct manifestation of a deeper source (Buddha → Vishnu)
  aspect_of   — named aspect/expansion (Saṅkarṣaṇa → Vishnu)
  epithet_of  — a pure name resolving to a manifest entity

Tiered construction (Rule 0 escalation ladder), cheapest first:
  1. deterministic same_as: exact normalized-name + compatible kind (macron-aware)
  2. deterministic avatar_of: aliases that say "avatar of X" / explicit rels
  3. reasoner adjudication: ONLY high-overlap pairs / mega-clusters (cost-capped)

This module builds tiers 1+2 (free, deterministic) and SELECTS the pairs that
need tier 3. The reasoner call itself is resolve.py.

See IDENTITY_MODEL.md.

JSON contract (Rule 0, precond B):
  run(entities, rels) -> {success, data:{identity_edges, ...}, metadata, errors}
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

# ── normalization (macron-preserving — gender survives, per graph.py) ──────
_MACRON = "̄"


def _norm(s: str) -> str:
    """Macron-preserving key (Kṛṣṇa ≠ Kṛṣṇā). Used for alias-target resolution."""
    if s is None:
        return ""
    nf = unicodedata.normalize("NFKD", str(s))
    kept = "".join(c for c in nf
                   if not unicodedata.combining(c) or c == _MACRON)
    return re.sub(r"\s+", " ", kept.strip().lower())


def _strip_key(s: str) -> str:
    """Fully diacritic-stripped key. Merges Rāma/rama (transliteration variants)."""
    if s is None:
        return ""
    nf = unicodedata.normalize("NFKD", str(s))
    kept = "".join(c for c in nf if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", kept.strip().lower())


def _same_name(a: str, b: str) -> bool:
    """True iff a and b are the same name modulo transliteration, WITHOUT
    collapsing a gendered minimal pair (final long vowel = gender marker).

    Rāma == rama  (transliteration variant, same strip-key)
    Kṛṣṇa != Kṛṣṇā  (differ only by FINAL long vowel → masc vs fem)
    """
    if _strip_key(a) != _strip_key(b):
        return False
    # strip-keys match. Now guard the gendered final-vowel case:
    ka, kb = _norm(a), _norm(b)  # macron-preserving
    if ka == kb:
        return True
    # they differ only in macrons. If the difference is a FINAL long vowel
    # (one ends in a bare vowel, the other in its macron'd form), it's gender.
    if len(ka) == len(kb):
        diffs = [i for i in range(len(ka)) if ka[i] != kb[i]]
        if len(diffs) == 1 and diffs[0] == len(ka) - 1:
            # final-position difference → treat as distinct (gender)
            return False
    # non-final macron differences are transliteration noise → same name
    return True


# ── kind compatibility (same guard as graph.py) ───────────────────────────
_INCOMPATIBLE_KIND_PAIRS = {
    frozenset({"deity", "demon"}), frozenset({"deity", "king"}),
    frozenset({"deity", "human"}), frozenset({"deity", "sage"}),
    frozenset({"demon", "king"}), frozenset({"demon", "sage"}),
    frozenset({"king", "sage"}), frozenset({"warrior", "sage"}),
    frozenset({"deity", "queen"}), frozenset({"king", "queen"}),
}


def _kinds_compatible(a: str, b: str) -> bool:
    a, b = (a or "").lower(), (b or "").lower()
    if not a or not b or a == b:
        return True
    return frozenset({a, b}) not in _INCOMPATIBLE_KIND_PAIRS


# ── relationship-alias patterns → avatar_of / aspect_of edges ──────────────
_AVATAR_ALIAS = re.compile(
    r"\b(?:avatar|avatara|avatār|avatāra|incarnation)\s+of\s+(.+)", re.I)
_ASPECT_ALIAS = re.compile(
    r"\b(?:aspect|expansion|manifestation|form)\s+of\s+(.+)", re.I)

# explicit relationship verbs that are identity assertions
_AVATAR_RELS = {"is_avatar_of", "avatar_of", "avatar", "incarnation_of",
                "is_incarnation_of", "incarnates_as", "incarnation"}
_ASPECT_RELS = {"is_aspect_of", "aspect_of", "is_expansion_of", "expansion_of",
                "is_form_of", "a_form", "is_a_form_of"}
_SAME_RELS = {"same_as", "is_same_as", "identical_to", "is", "also_known_as"}


# ── pure-name detection (an alias that is just a name, no relationship) ─────
def _is_relationship_phrase(alias: str) -> bool:
    return bool(_AVATAR_ALIAS.search(alias) or _ASPECT_ALIAS.search(alias)
                or re.search(r"\b(?:son|daughter|wife|husband|born)\s+of\b",
                             alias, re.I))


def build_identity_edges(entities: List[Dict[str, Any]],
                         rels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tiers 1+2: deterministic same_as + avatar_of/aspect_of edges.

    Returns a list of typed identity edges. NEVER merges entities.
    """
    edges: List[Dict[str, Any]] = []
    seen = set()

    def _add(src, dst, etype, evidence):
        key = (src, dst, etype)
        if key in seen or src == dst:
            return
        seen.add(key)
        edges.append({"src": src, "dst": dst, "type": etype, "evidence": evidence})

    # index entities by normalized canonical name (for resolving alias targets)
    by_norm_name: Dict[str, List[Dict]] = {}
    for e in entities:
        by_norm_name.setdefault(_norm(e["name"]), []).append(e)

    # ── Tier 1: same_as by transliteration-equivalent name + compatible kind ──
    # Group by strip-key (cheap), then within each group confirm with _same_name
    # (which guards the gendered final-vowel minimal pair) + kind compatibility.
    strip_groups: Dict[str, List[Dict]] = {}
    for e in entities:
        strip_groups.setdefault(_strip_key(e["name"]), []).append(e)
    for skey, group in strip_groups.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if (_same_name(group[i]["name"], group[j]["name"])
                        and _kinds_compatible(group[i].get("kind", ""),
                                              group[j].get("kind", ""))):
                    _add(group[i]["id"], group[j]["id"], "same_as",
                         f"name variant: {group[i]['name']} = {group[j]['name']}")

    # ── Tier 2a: avatar_of / aspect_of from alias phrases ──
    for e in entities:
        for alias in (e.get("aliases") or e.get("all_forms") or []):
            m_av = _AVATAR_ALIAS.search(alias)
            m_as = _ASPECT_ALIAS.search(alias)
            target_raw = None
            etype = None
            if m_av:
                target_raw, etype = m_av.group(1), "avatar_of"
            elif m_as:
                target_raw, etype = m_as.group(1), "aspect_of"
            if target_raw and etype:
                tgt = _norm(target_raw.strip(" .,"))
                for cand in by_norm_name.get(tgt, []):
                    _add(e["id"], cand["id"], etype, f"alias: {alias}")

    # ── Tier 2b: avatar_of / aspect_of / same_as from explicit relationships ──
    # resolve rel src/dst to entity ids (caller may pre-fill src_id/dst_id)
    id_by_norm: Dict[str, str] = {}
    for e in entities:
        id_by_norm.setdefault(_norm(e["name"]), e["id"])
        for a in (e.get("all_forms") or []):
            id_by_norm.setdefault(_norm(a), e["id"])

    for rel in rels:
        verb = (rel.get("rel") or "").lower().strip()
        src_id = rel.get("src_id") or id_by_norm.get(_norm(rel.get("src", "")))
        dst_id = rel.get("dst_id") or id_by_norm.get(_norm(rel.get("dst", "")))
        if not (src_id and dst_id):
            continue
        if verb in _AVATAR_RELS:
            _add(src_id, dst_id, "avatar_of", f"rel: {verb}")
        elif verb in _ASPECT_RELS:
            _add(src_id, dst_id, "aspect_of", f"rel: {verb}")
        elif verb in _SAME_RELS:
            # only honor same_as if kinds compatible
            se = next((x for x in entities if x["id"] == src_id), {})
            de = next((x for x in entities if x["id"] == dst_id), {})
            if _kinds_compatible(se.get("kind", ""), de.get("kind", "")):
                _add(src_id, dst_id, "same_as", f"rel: {verb}")

    return edges


def select_pairs_for_reasoner(entities: List[Dict[str, Any]],
                              min_shared: int = 5,
                              max_pairs: int = 400) -> List[Dict[str, Any]]:
    """Tier 3 selection: find entity pairs sharing >= min_shared name-forms.

    These are the AMBIGUOUS pairs worth paying the reasoner for. Pure-name
    forms only (relationship phrases excluded). Capped at max_pairs for cost.
    """
    # build form → entity-ids index (pure names only)
    form_to_ids: Dict[str, set] = {}
    for e in entities:
        for f in (e.get("all_forms") or []):
            if _is_relationship_phrase(f):
                continue
            nf = _norm(f)
            if nf:
                form_to_ids.setdefault(nf, set()).add(e["id"])

    # count shared forms per pair
    pair_shared: Dict[frozenset, int] = {}
    for nf, ids in form_to_ids.items():
        if len(ids) < 2:
            continue
        ids_l = sorted(ids)
        for i in range(len(ids_l)):
            for j in range(i + 1, len(ids_l)):
                key = frozenset({ids_l[i], ids_l[j]})
                pair_shared[key] = pair_shared.get(key, 0) + 1

    selected = [{"pair": tuple(sorted(k)), "n_shared": v}
                for k, v in pair_shared.items() if v >= min_shared]
    selected.sort(key=lambda x: -x["n_shared"])
    return selected[:max_pairs]


# ── JSON contract ──────────────────────────────────────────────────────────
def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(entities: List[Dict[str, Any]],
        rels: List[Dict[str, Any]],
        min_shared: int = 5) -> Dict[str, Any]:
    edges = build_identity_edges(entities, rels)
    reasoner_pairs = select_pairs_for_reasoner(entities, min_shared=min_shared)

    type_counts: Dict[str, int] = {}
    for e in edges:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1

    data = {
        "identity_edges": edges,
        "edge_type_counts": type_counts,
        "n_identity_edges": len(edges),
        "n_entities": len(entities),
        "reasoner_pairs": reasoner_pairs,
        "n_reasoner_pairs": len(reasoner_pairs),
    }
    return _envelope(True, data, {"min_shared": min_shared}, [])


if __name__ == "__main__":
    import sys, glob, os
    from tools.read_pass import graph as G

    # Load all completed records, build the manifest layer WITHOUT alias-merge
    # by giving every (entity, source_text) a distinct id, then layer identity.
    all_records = []
    for f in sorted(glob.glob("tools/read_pass/out/*.records.jsonl")):
        tag = os.path.basename(f).replace(".records.jsonl", "")
        if "proof" in tag or "broken_lens" in tag:
            continue
        recs = [json.loads(l) for l in open(f) if l.strip()]
        for r in recs:
            r.setdefault("_provenance", {})["source_text"] = tag
        all_records.extend(recs)

    g = G.build(all_records)
    # feed graph entities (already merged) — identity edges connect the survivors
    rels_flat = []
    for r in all_records:
        for rel in r.get("relationships", []) or []:
            rels_flat.append(rel)

    env = run(g.entities, rels_flat)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        d = env["data"]
        print(f"Identity edges: {d['n_identity_edges']:,}  ({d['edge_type_counts']})")
        print(f"Pairs needing reasoner (≥5 shared forms): {d['n_reasoner_pairs']}")
        print(f"\nEstimated reasoner cost: ~${d['n_reasoner_pairs'] * 0.02:.2f} "
              f"(at ~$0.02/pair with trimmed prompt)")
