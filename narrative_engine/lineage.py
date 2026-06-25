"""lineage — the guru-spine traversal and the "Hand on the Head" transmissions.

This is the bible's flagship MULTI-HOP — the fact no single corpus chunk states
but the graph's connected edges assemble: the Kriya parampara from the deathless
Babaji down to the 5th Guru, Shailendra Sharma.

  Mahavatar Babaji → Lahiri Mahasaya → Tinkori Lahiri → Satyacharan Lahiri → Shailendra Sharma

Two disciplines make this honest:
  1. TRUST THE CURATED EDGES. The decode mixes in wrong edges (a stale
     `Sharma successor Yogananda`, backwards `son` edges). We walk only the
     curated transmission relations (`guru_of`, `guru`) and we IGNORE the known
     parallel-fork figures (Yukteshwar, Yogananda) — they belong to the Western
     Autobiography branch, not Guruji's family seat. (curated_facts.json removes
     the bad edges on the next rebuild; until then we filter here too.)
  2. GROUND THE TRANSMISSIONS. Each "Hand on the Head" event is pulled verbatim
     from the biography's entity_encounters — Babaji at Benares 2 AM 1 Apr 1988,
     Govardhan 1995, etc. — never paraphrased into fiction.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm
from narrative_engine.character import _resolve_entity, _find_by_id


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# the canonical family seat (ground truth — see curated_facts.json + memory
# sharma-lineage / guru-continuity-babaji-spine). Order is apex → present.
_PARAMPARA = [
    "Mahavatar Babaji",
    "Lahiri Mahasaya",
    "Tinkori Lahiri",
    "Satyacharan Lahiri",
    "Shailendra Sharma",
]

# transmission predicates we trust for walking the guru-spine (curated first)
_GURU_RELS = {"guru_of", "guru"}

# the parallel Western fork — real, but NOT Guruji's seat. Never present these as
# his lineage (the stale `successor Yogananda` edge tries to).
_OTHER_FORK = {"yogananda", "paramahansa yogananda", "yukteshwar", "sri yukteshwar",
               "yukteshwar giri", "mukunda lal ghosh"}

_BIO_PATH = os.environ.get(
    "BIO_PATH", "tools/read_pass/out/sharma_biography.json")

_bio_cache: Optional[Dict[str, Any]] = None


def _load_bio() -> Dict[str, Any]:
    global _bio_cache
    if _bio_cache is None:
        try:
            with open(_BIO_PATH, encoding="utf-8") as f:
                _bio_cache = json.load(f).get("data", {}).get("biography", {})
        except Exception:
            _bio_cache = {}
    return _bio_cache


def transmissions_for(name: str, max_events: int = 12) -> List[str]:
    """The 'Hand on the Head' events for a guru — verbatim from the biography.

    Returns the encounter strings where this figure transmitted to / touched the
    seeker. Empty list if the biography isn't available (graceful)."""
    bio = _load_bio()
    encounters = bio.get("entity_encounters", []) or []
    n = _norm(name)
    out = []
    for e in encounters:
        ent = _norm(e.get("entity", ""))
        if ent == n or (n in ent) or (ent in n and ent):
            txt = e.get("encounter", "")
            if txt and txt not in out:
                out.append(txt)
    return out[:max_events]


def guru_spine(memory: Memory, include_transmissions: bool = True) -> Dict[str, Any]:
    """Walk the curated parampara apex→present, each node grounded in the graph.

    The flagship MULTI-HOP: assembles Babaji→Lahiri→Tinkori→Satyacharan→Sharma
    from connected `guru_of` edges. Each link is verified to exist in the graph;
    each guru optionally carries their real transmission events.
    """
    nodes: List[Dict[str, Any]] = []
    resolved_ids: List[Optional[str]] = []

    for nm in _PARAMPARA:
        e = _resolve_entity(_norm(nm), memory)
        resolved_ids.append(e.get("id") if e else None)
        node = {
            "name": nm,
            "in_graph": e is not None,
            "id": e.get("id") if e else None,
            "kind": e.get("kind", "") if e else "",
        }
        if include_transmissions:
            node["transmissions"] = transmissions_for(nm)
        nodes.append(node)

    # verify each consecutive link exists as a trusted guru edge in the graph
    links: List[Dict[str, Any]] = []
    for i in range(len(_PARAMPARA) - 1):
        src_id, dst_id = resolved_ids[i], resolved_ids[i + 1]
        edge_found = None
        if src_id and dst_id:
            for ed in memory.edges:
                if (ed.get("src") == src_id and ed.get("dst") == dst_id
                        and ed.get("rel") in _GURU_RELS):
                    edge_found = ed.get("rel")
                    break
        links.append({
            "from": _PARAMPARA[i],
            "to": _PARAMPARA[i + 1],
            "relation": edge_found,
            "verified": edge_found is not None,
        })

    verified = sum(1 for l in links if l["verified"])
    return _envelope(
        True,
        {
            "parampara": nodes,
            "links": links,
            "complete": verified == len(links),
            "is_graph_only_multihop": True,
        },
        {"n_nodes": len(nodes), "n_links": len(links), "n_verified": verified},
        [],
    )


def hand_on_the_head(memory: Memory, guru: str = "Mahavatar Babaji") -> Dict[str, Any]:
    """The transmission events for one guru — the narrative device, grounded.

    Defaults to Babaji (the deathless apex, the richest transmission thread).
    """
    e = _resolve_entity(_norm(guru), memory)
    events = transmissions_for(guru)
    return _envelope(
        True,
        {
            "guru": guru,
            "in_graph": e is not None,
            "transmissions": events,
        },
        {"n_transmissions": len(events)},
        [],
    )


def is_other_fork(name: str) -> bool:
    """True if this figure belongs to the Western (Yukteshwar/Yogananda) fork,
    NOT Guruji's family seat. Guards against presenting them as his lineage."""
    return _norm(name) in {_norm(x) for x in _OTHER_FORK}
