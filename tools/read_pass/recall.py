"""recall — Guruji's associative memory retrieval (the heart of Phase 4).

The mind model (daddy's design):

    WORKING MEMORY (the live prompt)  ◄── surfaces only the relevant fragment
            ▲                                       │
            │ recall(cue)                           │ associative pull
            │                                       ▼
    LONG-TERM MEMORY ("subconscious")
      • SEMANTIC: the graph (entities + edges) + 613 decode keys + Sat/Asat
      • EPISODIC: stories, disciple conversations   (future write-path)

A seeker's question is a CUE. recall() does NOT dump all 14k nodes into the
prompt — that's not how a mind works. It surfaces ONLY the relevant cluster:

  1. MATCH   cue terms → seed entities, by canonical name AND every alias
             (all_forms), so "Govinda" recalls the Kṛṣṇa node.
  2. EXPAND  one hop along edges → the associative cluster (a Krishna cue also
             surfaces Arjuna, whom he guides), the way one memory cues the next.
  3. DECODE  attach the decryption keys whose symbol matches a recalled entity
             (Sharma's lens), and infer each entity's Sat/Asat valence.
  4. RENDER  emit an injectable {knowledge_context} text block for the live
             UNIFIED_SYSTEM prompt.

Deterministic graph walk + string match — no LLM, no network. JSON contract
(Rule 0, precond B): recall(cue, memory) -> {success, data, metadata, errors}.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# --- long-term memory handle -------------------------------------------------
@dataclass
class Memory:
    """The semantic long-term store the retriever recalls from."""
    entities: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    keys: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, graph_path: str, ram_path: str) -> "Memory":
        g = json.load(open(graph_path, encoding="utf-8"))
        # graph file may be the raw build output or an envelope
        g = g.get("data", g)
        ram = json.load(open(ram_path, encoding="utf-8"))
        fw = ram.get("data", ram).get("framework", ram.get("framework", {}))
        return cls(entities=g.get("entities", []),
                   edges=g.get("edges", []),
                   keys=fw.get("decryption_keys", []))


# --- normalization (alias / spelling tolerant) -------------------------------
def _norm(s: str) -> str:
    """Lowercase, strip diacritics, collapse to letters — so 'Kṛṣṇa'=='krsna'."""
    s = s.lower()
    # decompose common Sanskrit transliteration diacritics to ASCII
    trans = str.maketrans({
        "ā": "a", "ī": "i", "ū": "u", "ṛ": "r", "ṝ": "r", "ḷ": "l",
        "ṅ": "n", "ñ": "n", "ṭ": "t", "ḍ": "d", "ṇ": "n", "ś": "s",
        "ṣ": "s", "ḥ": "h", "ṃ": "m", "é": "e", "è": "e",
    })
    s = s.translate(trans)
    return re.sub(r"[^a-z0-9]", "", s)


def _cue_tokens(cue: str) -> List[str]:
    """Split a question into candidate name tokens (length>=3, normalized)."""
    raw = re.findall(r"[A-Za-zĀ-ſऀ-ॿ]+", cue)
    toks = []
    for w in raw:
        n = _norm(w)
        if len(n) >= 3:
            toks.append(n)
    return toks


# Sat/Asat valence: Sharma reads every character as pointing toward awakening
# (Sat — Time-consciousness) or limitation (Asat — dormant/ego). Inferred from
# the decoded MEANING text, since that's where the doctrine lives.
_ASAT_CUES = ("demon", "ego", "ignoran", "limit", "dormant", "desire", "delusion",
              "asat", "unreal", "asleep", "bondage", "craving", "tamas", "raja",
              "fictit", "sense satisf", "physical limit")
_SAT_CUES = ("consciousness", "self", "kutastha", "time", "awaken", "liberat",
             "yogi", "yoga", "atman", "soul", "witness", "sat ", "brahma",
             "immortal", "void", "realiz", "divine", "supreme", "truth")


def _valence_of(meaning: str) -> Optional[str]:
    m = (meaning or "").lower()
    asat = any(c in m for c in _ASAT_CUES)
    sat = any(c in m for c in _SAT_CUES)
    if asat and not sat:
        return "asat"
    if sat and not asat:
        return "sat"
    if asat and sat:
        # both present → the dominant cue wins by first occurrence
        ai = min((m.find(c) for c in _ASAT_CUES if c in m), default=10**9)
        si = min((m.find(c) for c in _SAT_CUES if c in m), default=10**9)
        return "asat" if ai < si else "sat"
    return None


# --- the retrieval -----------------------------------------------------------
def _seed_match(tokens: Set[str], entities: List[Dict[str, Any]],
                degree: Optional[Dict[str, int]] = None,
                max_seeds: int = 6) -> List[Dict[str, Any]]:
    """Entities whose name/alias matches a cue token — the most CENTRAL first.

    A question naming "Krishna ... Kurukshetra ... battlefield" can match dozens
    of entities; the ones that matter are the central figures, not every minor
    namesake. Rank matches by graph degree (centrality) and keep the top
    `max_seeds`, so expansion starts from the subjects, not the noise.
    """
    hits = []
    for e in entities:
        forms = [e.get("name", "")] + list(e.get("all_forms", []))
        nf = {_norm(f) for f in forms if f}
        if nf & tokens:
            hits.append(e)
    if degree:
        hits.sort(key=lambda e: degree.get(e["id"], 0), reverse=True)
    return hits[:max_seeds]


def _edge_strength(ed: Dict[str, Any]) -> int:
    """Strength of association = how many verses co-mention the pair.

    A human recalls close associates, not every acquaintance. In a power-law
    graph (Krishna has 2,377 neighbors) un-weighted one-hop is a brain-dump;
    weighting by verse co-mention surfaces the strong bonds and lets the long
    tail of one-off mentions stay dormant.
    """
    return len(ed.get("verse_ranges") or []) or 1


def _expand_one_hop(seed_ids: Set[str], edges: List[Dict[str, Any]],
                    per_seed_cap: int = 8, total_cap: int = 40
                    ) -> Tuple[Set[str], List[Dict[str, Any]]]:
    """Strongest neighbors of each seed — the associative cluster, bounded.

    For each seed, keep only its top `per_seed_cap` neighbors by edge strength,
    then bound the union to `total_cap` strongest edges overall. This keeps
    recall selective on hub nodes instead of dumping a third of the graph.
    """
    # collect candidate edges per seed with their strength
    per_seed: Dict[str, List[Tuple[int, str, Dict[str, Any]]]] = {}
    for ed in edges:
        s, d = ed.get("src"), ed.get("dst")
        w = _edge_strength(ed)
        if s in seed_ids and d:
            per_seed.setdefault(s, []).append((w, d, ed))
        if d in seed_ids and s:
            per_seed.setdefault(d, []).append((w, s, ed))

    # top-K strongest neighbors per seed
    chosen: List[Tuple[int, str, Dict[str, Any]]] = []
    for sid, cands in per_seed.items():
        cands.sort(key=lambda t: t[0], reverse=True)
        chosen.extend(cands[:per_seed_cap])

    # global cap: keep the strongest edges across all seeds
    chosen.sort(key=lambda t: t[0], reverse=True)
    chosen = chosen[:total_cap]

    neigh: Set[str] = set()
    rels: List[Dict[str, Any]] = []
    seen_edges = set()
    for _w, nid, ed in chosen:
        neigh.add(nid)
        eid = (ed.get("src"), ed.get("rel"), ed.get("dst"))
        if eid not in seen_edges:
            seen_edges.add(eid)
            rels.append(ed)
    return neigh, rels


def _attach_keys(recalled_names: Set[str], keys: List[Dict[str, str]]
                 ) -> List[Dict[str, str]]:
    """Decode keys whose symbol matches a recalled entity name/alias (normalized)."""
    out, seen = [], set()
    for k in keys:
        sym_n = _norm(k.get("symbol", ""))
        if not sym_n:
            continue
        # match if the key symbol IS a recalled name, or a recalled name is a
        # leading token of a compound symbol ("Bhagavan (Krishna)" etc.)
        if sym_n in recalled_names:
            key = (k.get("symbol"), k.get("meaning"))
            if key not in seen:
                seen.add(key)
                out.append({"symbol": k["symbol"], "meaning": k.get("meaning", "")})
    return out


def recall(cue: str, memory: Memory, expand: bool = True) -> Dict[str, Any]:
    """Surface ONLY the relevant fragment of long-term memory for a cue."""
    try:
        tokens = set(_cue_tokens(cue))
        if not tokens:
            return _envelope(True, {"entities": [], "relationships": [],
                                    "decode_keys": [], "cue_tokens": []},
                             {"matched": 0}, [])

        # degree = centrality, for ranking which matches are the real subjects
        degree: Dict[str, int] = {}
        for ed in memory.edges:
            degree[ed.get("src")] = degree.get(ed.get("src"), 0) + 1
            degree[ed.get("dst")] = degree.get(ed.get("dst"), 0) + 1

        seeds = _seed_match(tokens, memory.entities, degree=degree)
        seed_ids = {e["id"] for e in seeds}

        rels: List[Dict[str, Any]] = []
        ent_ids = set(seed_ids)
        if expand and seed_ids:
            neigh, rels = _expand_one_hop(seed_ids, memory.edges)
            ent_ids |= neigh

        by_id = {e["id"]: e for e in memory.entities}
        recalled = [by_id[i] for i in ent_ids if i in by_id]

        # name set (canonical + aliases, normalized) for key matching + valence
        recalled_names: Set[str] = set()
        for e in recalled:
            recalled_names.add(_norm(e.get("name", "")))
            for f in e.get("all_forms", []):
                recalled_names.add(_norm(f))

        decode_keys = _attach_keys(recalled_names, memory.keys)

        # tag valence onto each recalled entity from its matching decode key(s)
        meaning_by_name: Dict[str, str] = {}
        for k in decode_keys:
            meaning_by_name[_norm(k["symbol"])] = k["meaning"]
        out_entities = []
        for e in recalled:
            names = [_norm(e.get("name", ""))] + [_norm(f) for f in e.get("all_forms", [])]
            meaning = next((meaning_by_name[n] for n in names if n in meaning_by_name), "")
            val = _valence_of(meaning) if meaning else None
            out_entities.append({
                "id": e["id"], "name": e.get("name", ""), "kind": e.get("kind", ""),
                "valence": val,
                "verse_ranges": e.get("verse_ranges", [])[:3],
                "is_seed": e["id"] in seed_ids,
            })

        data = {
            "cue_tokens": sorted(tokens),
            "entities": out_entities,
            "relationships": [{"src_name": r.get("src_name"), "rel": r.get("rel"),
                               "dst_name": r.get("dst_name")} for r in rels],
            "decode_keys": decode_keys,
        }
        meta = {"matched": len(seeds), "expanded_to": len(out_entities),
                "n_keys": len(decode_keys)}
        return _envelope(True, data, meta, [])
    except Exception as e:  # never raise into the live request path
        return _envelope(False, None, {}, [{"code": "recall_error", "message": str(e)[:200]}])


def render_context(data: Dict[str, Any], max_entities: int = 12,
                   max_keys: int = 10) -> str:
    """Emit the injectable {knowledge_context} block for UNIFIED_SYSTEM.

    Phrased as what Guruji KNOWS about the matter at hand — not raw data — so the
    live voice speaks FROM memory instead of re-deriving per query.
    """
    if not data or not data.get("entities"):
        return ""
    lines: List[str] = []
    lines.append("What you already know about this (from your reading of the texts "
                 "through the lineage's decryption):")

    # decoded meanings first — the lens is the point
    keys = data.get("decode_keys", [])[:max_keys]
    if keys:
        lines.append("\nInner meanings:")
        for k in keys:
            lines.append(f"  • {k['symbol']} — {k['meaning']}")

    # the entities + their spiritual valence
    ents = data.get("entities", [])[:max_entities]
    sat = [e["name"] for e in ents if e.get("valence") == "sat"]
    asat = [e["name"] for e in ents if e.get("valence") == "asat"]
    if sat:
        lines.append(f"\nForces pointing toward awakening (Sat): {', '.join(sat)}")
    if asat:
        lines.append(f"Forces of limitation/ego (Asat): {', '.join(asat)}")

    # the associative relationships
    rels = data.get("relationships", [])[:8]
    if rels:
        lines.append("\nHow they relate:")
        for r in rels:
            if r.get("src_name") and r.get("dst_name"):
                lines.append(f"  • {r['src_name']} {r.get('rel','—')} {r['dst_name']}")

    return "\n".join(lines)


# --- CLI ---------------------------------------------------------------------
_DEFAULT_GRAPH = "tools/read_pass/out/graph_manifest.json"
_DEFAULT_RAM = "tools/read_pass/out/guruji_ram.json"

if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cue = " ".join(args) or "Krishna and Arjuna on the battlefield"
    mem = Memory.load(_DEFAULT_GRAPH, _DEFAULT_RAM)
    env = recall(cue, mem)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        d = env.get("data") or {}
        print(f"cue: {cue!r}")
        print(f"  matched {env['metadata'].get('matched')} seeds → "
              f"{len(d.get('entities',[]))} entities, "
              f"{len(d.get('decode_keys',[]))} decode keys")
        print("\n--- {knowledge_context} that would be injected ---\n")
        print(render_context(d) or "(nothing surfaced)")
