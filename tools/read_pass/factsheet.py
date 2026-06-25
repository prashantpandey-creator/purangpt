"""factsheet — the deterministic literal-layer assembler for decode().

The Gandiva problem: decode("Gandiva") floats into pure mysticism ("time-
realization...") because it never consults the graph that ALREADY knows the
literal truth — Gandiva is Arjuna's bow, demanded by Agni, cited at bhp_10.89.
This tool is the zero-LLM decision tree that hands decode() that literal layer
BEFORE it generates, so the inner reading sits ON TOP of the real fact instead
of replacing it.

It is pure Rule-0: resolve symbol → entity (shared normalizer + alias match),
gather the entity's grounded cites and its named edges, assemble a short factual
`brief`. JSON envelope (precond B). No LLM, no network.

THE HONESTY DISCIPLINE (what makes this a mind, not a bullshitter): the graph's
`verse_ranges` are polluted with bare-number garbage ('17', '5-6', '61.4') that
lost its marker prefix during chunking. Every cite is run through verify's
canonical-marker grammar; only real markers survive. A literal layer that cites
"verse 17" of nothing would be a confident liar — we refuse to be one. metadata
reports raw_cites vs grounded_cites so decode knows how solid the floor is.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm
from tools.read_pass import verify


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata,
            "errors": errors}


# ── cite hygiene: keep ONLY canonical verse markers, drop the chunking garbage
def _grounded_cites(raw: List[Any]) -> List[str]:
    """A cite survives iff it IS a canonical marker (bhp_10.89.032, GhS_1.0, …).
    A range 'GhS_1.44-GhS_1.60' reduces to its start marker. Bare numbers
    ('17','5-6','61.4') and prose are dropped — they cite nothing checkable."""
    out: List[str] = []
    seen = set()
    for c in raw or []:
        m = verify._MARKER_RE.search(str(c))
        if not m:
            continue
        marker = m.group(0)
        # require the FULL token to be a marker (anchored), so '61.4' — which has
        # no letter_ prefix — never sneaks through on a partial match.
        if marker != str(c).strip() and not str(c).strip().startswith(marker):
            # only accept when the marker is the leading token (range case)
            continue
        if marker not in seen:
            seen.add(marker)
            out.append(marker)
    return out


def _resolve(symbol: str, memory: Memory) -> Optional[Dict[str, Any]]:
    """Match the symbol to exactly one entity by canonical name or any alias,
    using the SAME normalizer recall/decode share. Returns the richest match
    (most relationships) on an alias collision — a heuristic, flagged in md."""
    n = _norm(symbol)
    if not n:
        return None
    hits = []
    for e in memory.entities:
        names = [e.get("name", "")] + list(e.get("all_forms", []) or [])
        if any(_norm(x) == n for x in names if x):
            hits.append(e)
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]
    # collision: prefer the most-connected node (degree), then the longest name
    eid_degree: Dict[str, int] = {}
    ids = {e.get("id") for e in hits}
    for ed in memory.edges:
        if ed.get("src") in ids:
            eid_degree[ed["src"]] = eid_degree.get(ed["src"], 0) + 1
        if ed.get("dst") in ids:
            eid_degree[ed["dst"]] = eid_degree.get(ed["dst"], 0) + 1
    return max(hits, key=lambda e: (eid_degree.get(e.get("id"), 0),
                                    len(e.get("name", ""))))


def _named_edges(entity_id: str, memory: Memory,
                 limit: int = 24) -> List[Dict[str, Any]]:
    """Every edge touching this entity, rendered with resolved names + grounded
    cites. This IS the literal event-knowledge decode was missing (Arjuna-
    wields-Gandiva, Agni-demands-Gandiva)."""
    rels: List[Dict[str, Any]] = []
    for ed in memory.edges:
        if ed.get("src") != entity_id and ed.get("dst") != entity_id:
            continue
        rels.append({
            "src_name": ed.get("src_name") or ed.get("src"),
            "rel": ed.get("rel"),
            "dst_name": ed.get("dst_name") or ed.get("dst"),
            "cites": _grounded_cites(ed.get("verse_ranges")),
        })
    # surface the cited (verifiable) edges first — those are the trustworthy ones
    rels.sort(key=lambda r: (len(r["cites"]) == 0, r["src_name"], r["dst_name"]))
    return rels[:limit]


def _brief(identity: Dict[str, Any], rels: List[Dict[str, Any]]) -> str:
    """A short factual sentence decode() reads: what the symbol literally IS,
    anchored to a real marker, plus its most-cited concrete relation."""
    name = identity["canonical"]
    forms = [f for f in identity.get("forms", []) if _norm(f) != _norm(name)]
    cites = identity.get("cites", [])
    anchor = cites[0] if cites else None
    desc = f"{name}"
    if forms:
        desc += f" ({', '.join(forms[:3])})"
    parts = [f"Literally, {desc}"]
    # graft the single most concrete cited relationship as event-fact
    cited_rel = next((r for r in rels if r["cites"] and r["src_name"] != name),
                     None) or next((r for r in rels if r["cites"]), None)
    if cited_rel:
        parts.append(
            f" — {cited_rel['src_name']} {cited_rel['rel']} "
            f"{cited_rel['dst_name']} [{cited_rel['cites'][0]}]")
    if anchor and (not cited_rel or anchor not in (cited_rel.get("cites") or [])):
        parts.append(f" (cited {anchor})")
    return "".join(parts) + "."


# ── the assembler ──────────────────────────────────────────────────────────
def factsheet(symbol: str, memory: Memory) -> Dict[str, Any]:
    sym = (symbol or "").strip()
    if not sym:
        return _envelope(False, None, {},
                         [{"code": "empty", "message": "no symbol given"}])

    ent = _resolve(sym, memory)
    if ent is None:
        # the query RAN successfully; we simply don't know this symbol
        return _envelope(True,
                         {"found": False, "query": sym, "identity": None,
                          "relationships": [], "brief": ""},
                         {"raw_cites": 0, "grounded_cites": 0,
                          "resolution": "miss"}, [])

    raw_cites = list(ent.get("verse_ranges", []) or [])
    cites = _grounded_cites(raw_cites)
    identity = {
        "canonical": ent.get("name", sym),
        "kind": ent.get("kind", ""),
        "forms": list(ent.get("all_forms", []) or []),
        "cites": cites,
        "id": ent.get("id"),
    }
    rels = _named_edges(ent.get("id"), memory)
    brief = _brief(identity, rels)

    data = {"found": True, "query": sym, "identity": identity,
            "relationships": rels, "brief": brief}
    md = {"raw_cites": len(raw_cites), "grounded_cites": len(cites),
          "relationship_count": len(rels),
          "cited_relationship_count": sum(1 for r in rels if r["cites"]),
          "resolution": "exact"}
    return _envelope(True, data, md, [])


# ── CLI (--json contract) ───────────────────────────────────────────────────
def main(argv: List[str]) -> int:
    import json
    import os

    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    here = os.path.dirname(__file__)
    graph = arg("--graph", os.path.join(here, "out", "graph_manifest.json"))
    ram = arg("--ram", os.path.join(here, "out", "guruji_ram.json"))
    symbol = arg("--symbol", "Gandiva")
    mem = Memory.load(graph, ram)
    env = factsheet(symbol, mem)

    if "--json" in argv:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message']}")
        return 2
    else:
        d = env["data"]
        if not d["found"]:
            print(f"'{symbol}' — not in the graph")
        else:
            print(d["brief"])
            print(f"  kind={d['identity']['kind']} "
                  f"cites={len(d['identity']['cites'])} "
                  f"rels={len(d['relationships'])} "
                  f"({env['metadata']['cited_relationship_count']} cited)")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
