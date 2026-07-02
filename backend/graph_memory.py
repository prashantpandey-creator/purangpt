"""Graph memory — the WISDOM layer of the chat prompt (facts stay with RAG).

The corpus RAG retrieves verses — the facts, which it cannot hallucinate. This
module adds what RAG structurally cannot reach: the **relational truth** of the
graph — who relates to whom, the multi-hop chains, the cross-text identities
(Krishna's brother; the Babaji→Lahiri→Sharma Kriya spine). Proven graph_only
**4/5 vs the RAG floor's 0/5** by `tools/rag_vs_graph_bench`.

Architecture (LOCKED — `tools/read_pass/MEMORY_ARCHITECTURE.md`): **facts = RAG,
wisdom = graph, never mixed.** This is the wisdom side. The block it returns is
fed into the SAME `{context}` slot the RAG passages use (no new template slot, so
no KeyError-500 risk) — verses and relational truth, side by side.

**Safety contract — this NEVER breaks a chat turn:**
  - Flag-gated OFF by default (`GRAPH_MEMORY_ENABLED=1` to enable). Ships dark;
    flipped on deliberately, never half-wired into the live path.
  - Fail-graceful: flag-off / blank query / missing graph file / empty recall /
    ANY exception → returns `""`, and the chat behaves byte-identical to today.
  - The 8.8MB graph loads ONCE (a module singleton, ~83ms) and is reused; a failed
    load is remembered so we don't retry it every request.

The recall engine itself lives in `tools/read_pass/recall.py` (the moat). It is
imported lazily INSIDE the functions so a missing/broken moat can never stop
`backend` from importing.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from typing import Optional

logger = logging.getLogger("graph_memory")

# Overridable via env so the deploy can point at the image's copy of the graph.
_GRAPH_PATH = os.getenv("GRAPH_MEMORY_PATH", "tools/read_pass/out/graph_manifest.json")
_RAM_PATH = os.getenv("GRAPH_RAM_PATH", "tools/read_pass/out/guruji_ram.json")

_memory = None          # lazy singleton (recall.Memory) — load once, reuse
_load_failed = False    # remember a broken load; don't retry it every request
_clusters = None        # lazy singleton — Louvain communities (Vyasa Pancha Lakshana)
_cluster_entity_map = {} # entity → cluster_id lookup
_cluster_regex = None  # pre-compiled for O(n) source text matching


def _load_clusters():
    """Load Louvain community clusters. Lazy singleton — loaded once, reused."""
    global _clusters, _cluster_entity_map
    if _clusters is not None and len(_clusters) > 0:
        return _clusters
    if _clusters is not None and len(_clusters) == 0:
        _clusters = None  # force reload — cached empty from failed path
    try:
        import json as _json
        # Try multiple paths: env var → Docker volume → local tools dir
        _cp = os.getenv("GRAPH_CLUSTERS_PATH", "")
        if not _cp or not os.path.exists(_cp):
            _cp = "/app/data/graph_clusters.json"
        if not os.path.exists(_cp):
            _cp = os.path.join(os.path.dirname(_GRAPH_PATH), "graph_clusters.json")
        if not os.path.exists(_cp):
            _cp = os.path.join(os.path.dirname(__file__), "..", "tools", "read_pass", "out", "graph_clusters.json")
        if not os.path.exists(_cp):
            logger.warning("No cluster file at %s — run cluster_graph.py first", _cp)
            return None
        with open(_cp) as _f:
            _data = _json.load(_f)
        _clusters = _data.get("clusters", {})
        _cluster_entity_map = _data.get("entity_cluster", {})
        logger.info("Vyasa clusters loaded: %d communities, %d entities mapped",
                    len(_clusters), len(_cluster_entity_map))
        # Pre-compile word-boundary regex for O(n) entity matching in source text.
        # Only include entities with len>3 to avoid false positives (e.g. "rama" in "paramatma").
        global _cluster_regex
        _names = sorted([re.escape(e) for e in _cluster_entity_map if len(e) > 3], key=len, reverse=True)
        if _names:
            _pattern = r'\b(' + '|'.join(_names) + r')\b'
            _cluster_regex = re.compile(_pattern)
        return _clusters
    except Exception as _e:
        logger.warning("Cluster load failed: %s", _e)
        return None

def _enabled(override: Optional[bool]) -> bool:
    """Flag gate. Explicit `enabled=` wins (for tests); else the env, default OFF."""
    if override is not None:
        return override
    return os.getenv("GRAPH_MEMORY_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def _get_memory():
    """Load the graph once into a module singleton. Returns None (never raises) if
    the moat/graph isn't present — caller degrades to ""."""
    global _memory, _load_failed
    if _memory is not None or _load_failed:
        return _memory
    try:
        from tools.read_pass import recall  # lazy: a missing moat must not break import
        _memory = recall.Memory.load(_GRAPH_PATH, _RAM_PATH)
        logger.info("graph_memory loaded: %d entities, %d edges, %d keys",
                    len(_memory.entities), len(_memory.edges), len(_memory.keys))
    except Exception as e:  # noqa — fail-graceful: no graph → no graph context, ever silent
        _load_failed = True
        _memory = None
        logger.warning("graph_memory load failed (%s) — graph context disabled this run",
                       type(e).__name__)
    return _memory


# The clean, directional transmission edge: src is the guru, dst the disciple.
# (The fuzzier `guru`/`disciple` rels carry known direction bugs — see
# GRAPH_CORRECTIONS.md — so the spine walk uses ONLY guru_of.)
_GURU_REL = "guru_of"


def _norm_name(s: str) -> str:
    return (s or "").strip().lower()


def _norm_form(s: str) -> str:
    """Strip IAST diacritics → ASCII lowercase for fuzzy name matching."""
    trans = str.maketrans({
        "ā": "a", "ī": "i", "ū": "u", "ṛ": "r", "ṝ": "r", "ḷ": "l",
        "ṅ": "n", "ñ": "n", "ṭ": "t", "ḍ": "d", "ṇ": "n", "ś": "s",
        "ṣ": "s", "ḥ": "h", "ṃ": "m",
    })
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().translate(trans))


# Lazy index built once: normalized_form → list of entity dicts.
_forms_index: dict | None = None


def _get_forms_index() -> dict:
    global _forms_index
    if _forms_index is not None:
        return _forms_index
    mem = _get_memory()
    if not mem:
        _forms_index = {}
        return _forms_index
    idx: dict[str, list] = {}
    for e in (mem.entities or []):
        forms = [e.get("name", "")] + list(e.get("all_forms") or [])
        for f in forms:
            k = _norm_form(f)
            if len(k) >= 3:
                idx.setdefault(k, []).append(e)
    _forms_index = idx
    logger.debug("graph forms index built: %d normalised keys", len(idx))
    return idx


def get_graph_ilike_patterns(
    canonical: str | None,
    synonyms: list[str] | None,
) -> tuple[list[str], list[str]]:
    """Return (gretil_patterns, name_patterns) for graph-guided ILIKE injection.

    gretil_patterns: '%bhp_10.50.054%' patterns from entity verse_ranges.
      Texts that embed GRETIL IDs verbatim in content (Bhagavata, Narada, Garuda,
      Kurma, Matsya, Agni, Manusmriti, Gita, …) — ultra-precise citation match.
    name_patterns: '%Sudharmā%' patterns from entity all_forms.
      Fallback for Mahabharata, Ramayana, Padma which don't embed GRETIL IDs.
    Never raises.
    """
    try:
        idx = _get_forms_index()
        if not idx:
            return [], []
        terms = [canonical] + list(synonyms or [])
        terms = [t for t in terms if t]
        if not terms:
            return [], []

        seen_eids: set = set()
        matched: list = []
        for t in terms[:4]:
            k = _norm_form(t)
            if len(k) < 3:
                continue
            for e in idx.get(k, [])[:3]:
                eid = e.get("id") or e.get("name")
                if eid not in seen_eids:
                    seen_eids.add(eid)
                    matched.append(e)

        if not matched:
            return [], []

        gretil_pats: list[str] = []
        name_pats: list[str] = []
        seen: set = set()

        for e in matched[:4]:
            for vr in (e.get("verse_ranges") or [])[:5]:
                pat = "%" + unicodedata.normalize("NFC", vr) + "%"
                if pat not in seen:
                    seen.add(pat)
                    gretil_pats.append(pat)
            for f in ([e.get("name", "")] + list(e.get("all_forms") or []))[:3]:
                if f and len(f) >= 4:
                    pat = "%" + unicodedata.normalize("NFC", f) + "%"
                    if pat not in seen:
                        seen.add(pat)
                        name_pats.append(pat)

        return gretil_pats[:10], name_pats[:6]
    except Exception as exc:
        logger.warning("get_graph_ilike_patterns failed (%s)", exc)
        return [], []


def _lineage_chain(mem, seed_names, max_len: int = 8):
    """Assemble the guru→disciple transmission SPINE through any seed.

    THE FIX: recall is one-hop, and a high-degree node (Babaji) crowds the
    relationship cap, so the multi-hop lineage drifts to Yogananda instead of the
    real Sharma spine. This walks the clean `guru_of` edges to root-then-leaf and
    returns the ordered chain, e.g. ['Babaji', 'Lahiri Mahasaya', 'Tinkori Lahiri',
    'Satyacharan Lahiri', 'Shailendra Sharma'] — or [] if no seed sits on a chain.
    Never raises (fail-graceful)."""
    try:
        fwd, rev = {}, {}
        for e in getattr(mem, "edges", []) or []:
            if (e.get("rel") or "").strip().lower() != _GURU_REL:
                continue
            s, d = e.get("src_name"), e.get("dst_name")
            if not s or not d or s == d:
                continue
            fwd.setdefault(s, set()).add(d)
            rev.setdefault(d, set()).add(s)
        if not fwd:
            return []
        members = set(fwd) | set(rev)
        seeds_n = [_norm_name(s) for s in seed_names if _norm_name(s)]
        matched = [m for m in members
                   if any(sn in _norm_name(m) or _norm_name(m) in sn for sn in seeds_n)]
        if not matched:
            return []
        best = []
        for m in matched:
            root, seen = m, set()
            while rev.get(root) and root not in seen:  # climb to the root guru
                seen.add(root)
                root = sorted(rev[root])[0]
            chain, seen, cur = [root], {root}, root
            while fwd.get(cur):                          # descend through disciples
                nxt = sorted(fwd[cur] - seen)
                if not nxt:
                    break
                cur = nxt[0]
                chain.append(cur)
                seen.add(cur)
                if len(chain) >= max_len:
                    break
            if len(chain) > len(best):
                best = chain
        return best if len(best) >= 2 else []
    except Exception:  # noqa — never break a chat turn over the lineage walk
        return []


def build_graph_context(query: str, *, enabled: Optional[bool] = None) -> str:
    """The injectable graph block for the chat `{context}` slot, or "".

    NEVER raises into the request path. "" means "behave exactly like today".
    """
    if not _enabled(enabled):
        return ""
    if not query or not query.strip():
        return ""
    try:
        from tools.read_pass import recall
        mem = _get_memory()
        if mem is None:
            return ""
        env = recall.recall(query, mem)
        if not env.get("success"):
            return ""
        block = recall.render_context(env.get("data") or {})
        # ── Vyasa Pancha Lakshana: cluster-aware context ────────────
        _cl = _load_clusters()
        if _cl and block:
            _ent_ids = [e.get("id", "") for e in (env.get("data") or {}).get("entities", [])]
            _cluster_ids = set()
            for _eid in _ent_ids:
                _cid = _cluster_entity_map.get(_eid)
                if _cid is not None:
                    _cluster_ids.add(str(_cid))
            if _cluster_ids:
                _cluster_lines = []
                for _cid in sorted(_cluster_ids, key=lambda c: _cl.get(c, {}).get("size", 0), reverse=True)[:3]:
                    _cinfo = _cl.get(_cid, {})
                    if _cinfo:
                        _cluster_lines.append(f"Community {_cinfo.get('label', _cid)} ({_cinfo.get('size', 0)} entities)")
                if _cluster_lines:
                    _cluster_ctx = "Belongs to knowledge communities:\n  " + "\n  ".join(_cluster_lines)
                    block = block + "\n\n" + _cluster_ctx
                    logger.info("Cluster context: %d communities added", len(_cluster_lines))
        # Lineage spine (the fix): one-hop recall drops the multi-hop guru chain, so
        # surface the REAL transmission line at the TOP — walk guru_of through every
        # recalled figure: Babaji → Lahiri → Tinkori → Satyacharan → Shailendra Sharma.
        try:
            names = [e.get("name", "") for e in (env.get("data") or {}).get("entities", [])]
            chain = _lineage_chain(mem, names)
            if len(chain) >= 3:
                spine = "Lineage of transmission (guru to disciple): " + " → ".join(chain)
                block = (spine + "\n\n" + block) if block else spine
        except Exception:  # noqa — spine is a bonus; never break the block over it
            pass
        return block or ""
    except Exception as e:  # noqa — a graph hiccup must never break a chat turn
        logger.warning("build_graph_context failed (%s) — degrading to no graph context",
                       type(e).__name__)
        return ""
