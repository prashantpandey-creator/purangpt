"""world — the spatial model of the Puranic universe.

Maps the knowledge graph's entity/relationship data into navigable locations.
Locations are entities of kind 'place'/'location'/'realm'/'city'/'forest'/etc.
with edges connecting them to residents, events, and neighboring locations.

Every answer traces to the graph — no invented geography. If the graph doesn't
know a location, we say so honestly rather than fabricating.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from tools.read_pass.recall import Memory, _norm


# kinds that represent navigable places in the Puranic cosmos
_PLACE_KINDS = {
    "place", "location", "realm", "loka", "city", "kingdom", "forest",
    "mountain", "river", "ocean", "island", "dvipa", "tirtha", "ashram",
    "palace", "battlefield", "heaven", "hell", "underworld",
}

# predicates that indicate spatial relationships (entity is AT a place)
_SPATIAL_PREDS = {
    "resides_in", "rules", "lives_in", "governs", "born_in", "dies_in",
    "travels_to", "visits", "visited", "meditates_in", "fights_at",
    "performs_at", "kingdom", "capital", "located_in", "part_of",
    "conquers", "conquered", "attacks", "built", "king",
    "associated_with", "subjugates",
}

# predicates that indicate topological connections between places
_TOPOLOGY_PREDS = {
    "contains", "part_of", "located_in", "leads_to", "flows_from",
    "flows_to", "borders", "surrounds", "near",
    "has_supporting_mountains", "has_kesaracalas_east",
}

# predicates that indicate an event happened at / is associated with a place
_EVENT_PREDS = {
    "performs", "fights", "battles", "kills", "defeats", "marries",
    "teaches", "instructs", "blesses", "curses", "sacrifices",
    "appeared_from", "embodies", "incarnated_as", "created",
}


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _is_place(entity: Dict[str, Any]) -> bool:
    kind = (entity.get("kind") or "").lower().strip()
    return kind in _PLACE_KINDS


def list_locations(memory: Memory) -> Dict[str, Any]:
    """All navigable locations in the graph."""
    places = [e for e in memory.entities if _is_place(e)]
    data = [{
        "id": e["id"],
        "name": e.get("name", ""),
        "kind": e.get("kind", ""),
        "chapters": len(e.get("chapters", [])),
    } for e in sorted(places, key=lambda x: -len(x.get("chapters", [])))]
    return _envelope(True, {"locations": data, "count": len(data)},
                     {}, [])


def location_detail(name: str, memory: Memory) -> Dict[str, Any]:
    """Everything the graph knows about a location: residents, events, exits."""
    n = _norm(name)
    if not n:
        return _envelope(False, None, {}, [{"code": "empty_name", "message": "no location name"}])

    place = _resolve(name, memory, predicate=_is_place)

    if not place:
        return _envelope(False, None, {},
                         [{"code": "not_found", "message": f"location '{name}' not in graph"}])

    pid = place["id"]

    # who lives here / rules here
    residents = []
    events = []
    connected_places = []
    seen_res = set()
    seen_evt = set()

    for ed in memory.edges:
        src, dst, rel = ed.get("src"), ed.get("dst"), ed.get("rel", "")

        # edges pointing TO this place (someone resides_in / travels_to here)
        if dst == pid and rel in _SPATIAL_PREDS:
            if src not in seen_res:
                seen_res.add(src)
                ent = _find_by_id(src, memory.entities)
                if ent:
                    residents.append({
                        "name": ent.get("name", ""),
                        "kind": ent.get("kind", ""),
                        "relationship": rel,
                        "verse_ranges": ed.get("verse_ranges", [])[:3],
                    })

        # edges FROM this place (this place is connected to another)
        if src == pid and rel in _SPATIAL_PREDS:
            target = _find_by_id(dst, memory.entities)
            if target and _is_place(target):
                connected_places.append({
                    "name": target.get("name", ""),
                    "kind": target.get("kind", ""),
                    "relationship": rel,
                })
            elif target and dst not in seen_res:
                seen_res.add(dst)
                residents.append({
                    "name": target.get("name", ""),
                    "kind": target.get("kind", ""),
                    "relationship": rel,
                    "verse_ranges": ed.get("verse_ranges", [])[:3],
                })

        # topology edges (contains, leads_to, flows_from, etc.)
        if (src == pid or dst == pid) and rel in _TOPOLOGY_PREDS:
            other_id = dst if src == pid else src
            target = _find_by_id(other_id, memory.entities)
            if target and _is_place(target):
                direction = "outward" if src == pid else "inward"
                connected_places.append({
                    "name": target.get("name", ""),
                    "kind": target.get("kind", ""),
                    "relationship": rel,
                    "direction": direction,
                })

        # events associated with this place (someone does X here)
        if (src == pid or dst == pid) and rel in _EVENT_PREDS:
            other_id = dst if src == pid else src
            if other_id not in seen_evt:
                seen_evt.add(other_id)
                ent = _find_by_id(other_id, memory.entities)
                if ent:
                    events.append({
                        "actor": ent.get("name", ""),
                        "action": rel,
                        "verse_ranges": ed.get("verse_ranges", [])[:3],
                    })

    data = {
        "location": {
            "name": place.get("name", ""),
            "kind": place.get("kind", ""),
            "aliases": place.get("all_forms", []),
            "chapters": place.get("chapters", []),
            "verse_ranges": place.get("verse_ranges", [])[:5],
        },
        "residents": sorted(residents, key=lambda x: x["name"]),
        "events": events[:20],
        "connected_places": connected_places,
    }
    return _envelope(True, data, {"n_residents": len(residents),
                                   "n_events": len(events)}, [])


def entities_at_location(name: str, memory: Memory) -> Dict[str, Any]:
    """NPCs present at a location — what a game client needs to populate a scene."""
    detail = location_detail(name, memory)
    if not detail["success"]:
        return detail
    return _envelope(True,
                     {"location": name, "npcs": detail["data"]["residents"]},
                     detail["metadata"], [])


def nearby_locations(name: str, memory: Memory, max_hops: int = 2) -> Dict[str, Any]:
    """Reachable places from a location via spatial/topology edges — the game nav graph."""
    n = _norm(name)
    if not n:
        return _envelope(False, None, {}, [{"code": "empty_name", "message": "no name"}])

    start = _resolve(name, memory, predicate=_is_place)
    if not start:
        return _envelope(False, None, {},
                         [{"code": "not_found", "message": f"location '{name}' not in graph"}])

    nav_preds = _SPATIAL_PREDS | _TOPOLOGY_PREDS
    place_ids = {e["id"] for e in memory.entities if _is_place(e)}

    visited: Set[str] = {start["id"]}
    frontier = [start["id"]]
    reachable = []

    for hop in range(max_hops):
        next_frontier = []
        for pid in frontier:
            for ed in memory.edges:
                src, dst, rel = ed.get("src"), ed.get("dst"), ed.get("rel", "")
                if rel not in nav_preds:
                    continue
                neighbor_id = None
                if src == pid and dst in place_ids:
                    neighbor_id = dst
                elif dst == pid and src in place_ids:
                    neighbor_id = src
                if neighbor_id and neighbor_id not in visited:
                    visited.add(neighbor_id)
                    next_frontier.append(neighbor_id)
                    ent = _find_by_id(neighbor_id, memory.entities)
                    if ent:
                        reachable.append({
                            "name": ent.get("name", ""),
                            "kind": ent.get("kind", ""),
                            "hops": hop + 1,
                            "via": rel,
                        })
        frontier = next_frontier
        if not frontier:
            break

    return _envelope(True,
                     {"origin": start.get("name", ""), "reachable": reachable},
                     {"n_reachable": len(reachable), "max_hops": max_hops}, [])


def character_journey(char_name: str, memory: Memory, limit: int = 30) -> Dict[str, Any]:
    """Places a character appears in, derived from chapter co-occurrence.

    This is the real navigation model — the graph is character-centric, not
    map-centric, so "follow Rama's path" works better than "walk from A to B."
    """
    n = _norm(char_name)
    if not n:
        return _envelope(False, None, {}, [{"code": "empty_name", "message": "no name"}])

    char = _resolve(char_name, memory)
    if not char:
        return _envelope(False, None, {},
                         [{"code": "not_found", "message": f"'{char_name}' not in graph"}])

    char_chapters = set(char.get("chapters", []))
    if not char_chapters:
        return _envelope(True, {"character": char.get("name", ""), "locations": []},
                         {"n_locations": 0}, [])

    place_ids = {e["id"] for e in memory.entities if _is_place(e)}
    co_occur: Dict[str, Dict[str, Any]] = {}

    for e in memory.entities:
        if e["id"] not in place_ids or e["id"] == char.get("id"):
            continue
        shared = char_chapters & set(e.get("chapters", []))
        if shared:
            co_occur[e["id"]] = {
                "name": e.get("name", ""),
                "kind": e.get("kind", ""),
                "shared_chapters": len(shared),
                "first_chapter": min(shared),
            }

    # also check direct edges for relationship context
    char_id = char["id"]
    for ed in memory.edges:
        src, dst, rel = ed.get("src"), ed.get("dst"), ed.get("rel", "")
        if src == char_id and dst in co_occur:
            co_occur[dst].setdefault("relationships", []).append(rel)
        elif dst == char_id and src in co_occur:
            co_occur[src].setdefault("relationships", []).append(rel)

    locations = sorted(co_occur.values(), key=lambda x: -x["shared_chapters"])[:limit]

    return _envelope(True,
                     {"character": char.get("name", ""), "locations": locations},
                     {"n_locations": len(locations), "total_chapters": len(char_chapters)},
                     [])


def _resolve(name: str, memory: Memory, predicate=None) -> Optional[Dict[str, Any]]:
    """Exact primary-name match wins over alias — same discipline as
    character._resolve_entity, with an optional predicate (e.g. _is_place).

    Post-de-merge, blobs list other entities as `aspect_of` forms; a naive
    alias scan hijacks the query to the biggest node. Prefer the entity that IS
    this name; fall back to alias only when no standalone node passes the filter.
    """
    n = _norm(name)
    if not n:
        return None
    pred = predicate or (lambda e: True)
    exact = [e for e in memory.entities
             if _norm(e.get("name", "")) == n and pred(e)]
    if exact:
        return max(exact, key=lambda e: len(e.get("chapters", [])))
    for e in memory.entities:
        if not pred(e):
            continue
        forms = list(e.get("all_forms", []) or [])
        if any(_norm(x) == n for x in forms if x):
            return e
    return None


def _find_by_id(eid: str, entities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return next((e for e in entities if e.get("id") == eid), None)
