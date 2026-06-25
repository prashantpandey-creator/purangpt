"""narrative — story progression, dharmic choices, and consequence chains.

Drives the story forward by querying the graph for what happens next in a given
Purana's narrative, presenting dharmic forks where the texts describe a character
facing a choice, and tracking consequences through the graph's cause-effect edges.

The narrative engine doesn't invent story — it SURFACES the story that's already
in the decoded corpus, making it interactive by letting the player experience
events from the perspective of different characters.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# predicates that indicate narrative events (cause → effect chains)
_CAUSE_PREDS = {
    "causes", "leads_to", "results_in", "triggers", "provokes",
    "inspires", "motivates",
}
_EFFECT_PREDS = {
    "caused_by", "result_of", "consequence_of", "due_to",
    "born_from", "arises_from",
}
_SEQUENCE_PREDS = {
    "precedes", "follows", "before", "after", "then", "next",
}


_TEXT_PREFIXES = {
    "bhagavata": "bhp", "bhagavatam": "bhp", "bhagavata purana": "bhp",
    "mahabharata": "mbh",
    "ramayana": "R", "ramayan": "R",
    "gita": "bg", "bhagavad gita": "bg",
    "brahma": "BrP", "brahma purana": "BrP",
    "gheranda": "GhS", "gheranda samhita": "GhS",
}


def _verse_prefix_for(text_name: str) -> Optional[str]:
    """Resolve a human text name to the GRETIL verse marker prefix."""
    n = text_name.lower().strip()
    if n in _TEXT_PREFIXES:
        return _TEXT_PREFIXES[n]
    for key, prefix in _TEXT_PREFIXES.items():
        if n in key or key in n:
            return prefix
    return None


def _entity_has_text(entity: Dict[str, Any], prefix: str) -> bool:
    """Does this entity have verse_ranges from the given text?"""
    for v in entity.get("verse_ranges", []):
        if str(v).startswith(prefix + "_"):
            return True
    return False


def _edge_has_text(edge: Dict[str, Any], prefix: str) -> bool:
    for v in edge.get("verse_ranges", []):
        if str(v).startswith(prefix + "_"):
            return True
    return False


def get_narrative_events(text_name: str, memory: Memory,
                         chapter_filter: Optional[str] = None) -> Dict[str, Any]:
    """Events in a specific text, optionally filtered by chapter.

    Matches entities/edges by their verse marker prefixes (bhp_, mbh_, R_, etc.)
    since chapter labels are generic and don't carry the text name.
    """
    if not text_name:
        return _envelope(False, None, {},
                         [{"code": "empty", "message": "no text name"}])

    prefix = _verse_prefix_for(text_name)
    if not prefix:
        return _envelope(False, None, {},
                         [{"code": "unknown_text",
                           "message": f"unknown text '{text_name}' — "
                                      f"known: {', '.join(sorted(_TEXT_PREFIXES.keys()))}"}])

    relevant_entities = []
    for e in memory.entities:
        if _entity_has_text(e, prefix):
            relevant_entities.append({
                "id": e["id"],
                "name": e.get("name", ""),
                "kind": e.get("kind", ""),
                "chapters": e.get("chapters", []),
            })

    relevant_ids = {e["id"] for e in relevant_entities}

    relevant_edges = []
    for ed in memory.edges:
        if (ed.get("src") in relevant_ids or ed.get("dst") in relevant_ids) \
                and _edge_has_text(ed, prefix):
            relevant_edges.append({
                "src_name": ed.get("src_name", ""),
                "rel": ed.get("rel", ""),
                "dst_name": ed.get("dst_name", ""),
                "chapters": ed.get("chapters", []),
                "verse_ranges": ed.get("verse_ranges", [])[:3],
            })

    return _envelope(True, {
        "text": text_name,
        "verse_prefix": prefix,
        "chapter_filter": chapter_filter,
        "entities": relevant_entities[:50],
        "events": relevant_edges[:100],
    }, {"n_entities": len(relevant_entities),
        "n_events": len(relevant_edges)}, [])


def consequence_chain(entity_name: str, memory: Memory,
                      max_depth: int = 5) -> Dict[str, Any]:
    """Trace the cause-effect chain from an entity/event through the graph.

    Follows cause/effect predicates to show what cascades from a given action
    or event — the narrative equivalent of "what happened because of this."
    """
    n = _norm(entity_name)
    if not n:
        return _envelope(False, None, {},
                         [{"code": "empty", "message": "no entity name"}])

    entity = None
    for e in memory.entities:
        names = [e.get("name", "")] + list(e.get("all_forms", []) or [])
        if any(_norm(x) == n for x in names if x):
            entity = e
            break

    if not entity:
        return _envelope(False, None, {},
                         [{"code": "not_found", "message": f"'{entity_name}' not in graph"}])

    # BFS through cause/effect edges
    chain = []
    visited = {entity["id"]}
    frontier = [entity["id"]]
    all_cause_effect = _CAUSE_PREDS | _EFFECT_PREDS

    for depth in range(max_depth):
        next_frontier = []
        for eid in frontier:
            for ed in memory.edges:
                if ed.get("rel") not in all_cause_effect:
                    continue
                if ed.get("src") == eid and ed.get("dst") not in visited:
                    visited.add(ed["dst"])
                    next_frontier.append(ed["dst"])
                    chain.append({
                        "depth": depth + 1,
                        "from": ed.get("src_name", ""),
                        "action": ed.get("rel", ""),
                        "to": ed.get("dst_name", ""),
                        "verse_ranges": ed.get("verse_ranges", [])[:3],
                    })
                if ed.get("dst") == eid and ed.get("src") not in visited:
                    visited.add(ed["src"])
                    next_frontier.append(ed["src"])
                    chain.append({
                        "depth": depth + 1,
                        "from": ed.get("src_name", ""),
                        "action": ed.get("rel", ""),
                        "to": ed.get("dst_name", ""),
                        "verse_ranges": ed.get("verse_ranges", [])[:3],
                    })
        frontier = next_frontier
        if not frontier:
            break

    return _envelope(True, {
        "origin": entity.get("name", ""),
        "chain": chain,
        "depth_reached": min(max_depth, len(set(c["depth"] for c in chain)) if chain else 0),
    }, {"n_links": len(chain)}, [])


def dharmic_fork(event_description: str, options: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Present a dharmic choice to the player.

    Each option includes a guna_shift that will be applied if chosen, and
    narrative consequences that will unfold. The options should be derived from
    the text's own moral framework — not invented Western morality.

    options format: [
        {
            "label": "Stand and fight",
            "description": "Draw your bow and face the enemy",
            "guna_shift": {"sattva": 0.0, "rajas": 0.05, "tamas": 0.0},
            "consequences": ["battle_begins", "reputation_increases"],
        },
        ...
    ]
    """
    if not options or len(options) < 2:
        return _envelope(False, None, {},
                         [{"code": "too_few", "message": "need at least 2 options"}])

    return _envelope(True, {
        "event": event_description,
        "options": options,
        "n_options": len(options),
    }, {}, [])
