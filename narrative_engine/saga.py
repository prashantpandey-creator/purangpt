"""saga — assemble a character's whole story-cluster from the live graph.

The convergence layer. Where codex.py answers "what IS this weapon" and
character.py answers "who is this being", saga() answers the question a game
actually asks: "what is the STORY this character carries — their weapons, the
vows and curses that drive them, their lineage, the deeds they're remembered for,
and what they're secretly a form of."

It is the proof that the Puranic graph is a CONTENT ENGINE, not a lookup table:
one entity, and the weapon + dharma + curse + lineage + avatar all fall out of a
single edge-cluster, every strand cited to the corpus. Nothing invented; strands
the graph lacks simply come back empty.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm
from narrative_engine.character import _resolve_entity, _find_by_id


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# predicate-root → story strand. Order matters: first match wins per edge.
_STRANDS = [
    ("weapons", ("weapon", "astra", "wield", "bow", "_brahmastra")),
    ("vows_and_curses", ("curse", "vow", "destined", "deathless", "immortal",
                         "doomed", "fated")),
    ("boons", ("boon", "blesses", "blessed", "grants_boon", "granted_boon")),
    ("lineage", ("father", "mother", "son", "daughter", "brother", "sister",
                 "descend", "ancestor", "gotra", "progenitor", "wife", "husband")),
    ("identity", ("avatar", "incarnat", "reincarnat", "alias", "aspect",
                  "same_as", "manifest", "form_of", "embodi")),
    ("deeds", ("kill", "slay", "defeat", "attack", "fought", "destroy", "conquers",
               "vanquish", "wounds", "struck")),
]


def _strand_for(rel: str) -> str:
    r = (rel or "").lower()
    for strand, roots in _STRANDS:
        if any(root in r for root in roots):
            return strand
    return "other"


def saga(name: str, memory: Memory, max_per_strand: int = 10) -> Dict[str, Any]:
    """Everything the graph knows about a character, sorted into story strands."""
    ent = _resolve_entity(_norm(name), memory)
    if ent is None:
        return _envelope(False, None, {},
                         [{"code": "not_found", "message": f"'{name}' not in graph"}])
    eid = ent["id"]

    strands: Dict[str, List[Dict[str, Any]]] = {
        "weapons": [], "vows_and_curses": [], "boons": [],
        "lineage": [], "identity": [], "deeds": [], "other": [],
    }

    for ed in memory.edges:
        src, dst, rel = ed.get("src"), ed.get("dst"), ed.get("rel", "")
        if src != eid and dst != eid:
            continue
        outgoing = src == eid
        other_id = dst if outgoing else src
        other = _find_by_id(other_id, memory.entities)
        other_name = other.get("name", "") if other else ""
        strand = _strand_for(rel)
        strands[strand].append({
            "subject": ent["name"] if outgoing else other_name,
            "relation": rel,
            "object": other_name if outgoing else ent["name"],
            "direction": "outgoing" if outgoing else "incoming",
            "verse_ranges": (ed.get("verse_ranges") or [])[:2],
        })

    # trim each strand
    counts = {}
    for k in strands:
        counts[k] = len(strands[k])
        strands[k] = strands[k][:max_per_strand]

    # a one-line "what is this character" derived from the strands present
    headline = _headline(ent["name"], strands, counts)

    return _envelope(
        True,
        {
            "name": ent["name"],
            "kind": ent.get("kind", ""),
            "chapters": len(ent.get("chapters", [])),
            "headline": headline,
            "strands": strands,
            # the convergence proof: does this one character carry the full braid?
            "carries": [k for k, c in counts.items()
                        if c > 0 and k != "other"],
        },
        {"strand_counts": counts,
         "total_edges": sum(counts.values())},
        [],
    )


def _headline(name: str, strands, counts) -> str:
    """A terse, graph-derived gloss — no fabrication, just what the strands say."""
    bits = []
    if strands["identity"]:
        forms = [s["object"] for s in strands["identity"]
                 if "avatar" in s["relation"].lower() or "incarnat" in s["relation"].lower()]
        if forms:
            bits.append(f"a form of {forms[0]}")
    if counts["weapons"]:
        w = [s["object"] for s in strands["weapons"]
             if "astra" in s["object"].lower() or "bow" in s["object"].lower()]
        if w:
            bits.append(f"wields {w[0]}")
    if strands["vows_and_curses"]:
        v = strands["vows_and_curses"][0]
        bits.append(f"{v['relation'].replace('_', ' ')} {v['object']}")
    if counts["deeds"]:
        bits.append(f"{counts['deeds']} recorded deeds")
    return f"{name}: " + "; ".join(bits) if bits else name


def convergence_check(name: str, memory: Memory) -> Dict[str, Any]:
    """Proof metric: how many of the story strands does this one entity carry?

    A high score is the whole thesis — weapon+dharma+curse+lineage+identity from a
    single character, all graph-grounded.
    """
    s = saga(name, memory)
    if not s["success"]:
        return s
    carries = s["data"]["carries"]
    return _envelope(
        True,
        {
            "name": s["data"]["name"],
            "carries": carries,
            "n_strands": len(carries),
            "is_full_braid": len(set(carries) & {
                "weapons", "vows_and_curses", "lineage", "identity", "deeds"}) >= 4,
        },
        s["metadata"], [])
