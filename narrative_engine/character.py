"""character — NPC factsheets, abilities, and graph-grounded dialogue.

Every character response traces back to the knowledge graph. The LLM generates
dialogue but is constrained by what the graph knows — no inventing relationships,
weapons, or events that aren't in the decoded corpus.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm, recall
from tools.read_pass.factsheet import factsheet
from tools.read_pass.decode import Operator


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# predicates that indicate weapon/power possession
# weapon/astra relationship ROOTS — matched as SUBSTRINGS so the rebuilt graph's
# rich predicate vocabulary is caught: wields/wielder, uses/uses_weapon,
# obtained_weapon_from, gave_weapon, gave_gneya_astra_to, received_weapon_from,
# grants_weapon, invoked (an astra), neutralizes (an astra). The de-merge expanded
# the verb set far past the old exact-match list (which missed Arjuna's Gandiva).
_WEAPON_PRED_ROOTS = (
    "wield", "weapon", "astra", "bow", "obtained_weapon", "gave_weapon",
    "received_weapon", "grants_weapon", "grant_weapon", "invoked", "neutraliz",
)
# kept for back-compat / exact hits
_WEAPON_PREDS = {
    "wields", "possesses", "receives", "receives_from", "obtains",
    "given", "grants", "bestows", "weapon", "bow", "astra", "uses",
}


# target-name roots that mark the OTHER entity as a weapon/astra (so a generic
# rel like "uses"/"obtained" still counts when what's used IS a weapon)
_WEAPON_TARGET_ROOTS = ("astra", "gandiv", "gāṇḍīv", "chakra", "bow", "trishul",
                        "vajra", "pinaka", "sharanga", "brahmashira", "pasupata",
                        "pāśupat", "sudarshan")


def _is_weapon_rel(rel: str, target_name: str = "") -> bool:
    r = (rel or "").lower()
    if r in _WEAPON_PREDS or any(root in r for root in _WEAPON_PRED_ROOTS):
        return True
    # generic rel (uses/obtained/gave) but the TARGET is itself a weapon
    t = (target_name or "").lower()
    if r in ("uses", "obtained", "gave", "invoked", "returns", "asked_for",
             "requests_weapon_from", "cuts") and any(root in t for root in _WEAPON_TARGET_ROOTS):
        return True
    return False


# predicates that indicate a boon or curse
_BOON_PREDS = {"blesses", "grants_boon", "boon", "bestows"}
_CURSE_PREDS = {"curses", "cursed", "curse"}

# predicates that indicate lineage/family
_FAMILY_PREDS = {
    "father", "mother", "son", "daughter", "wife", "husband",
    "brother", "sister", "child", "parent", "grandfather",
    "grandmother", "grandson", "granddaughter", "ancestor",
    "descendant", "spouse",
}

# predicates that indicate teacher/student
_GURU_PREDS = {"teaches", "instructs", "guru", "disciple", "student", "trained_by"}

# --- kin directionality -----------------------------------------------------
# The decoder writes kin edges in BOTH conventions for the same fact:
# {Dasharatha, son, Rama} AND {Dasharatha, father, Rama} both encode "Dasharatha
# is Rama's parent". The one reliable invariant across every kin edge is that the
# SRC is the senior (parent/ancestor/grandparent) and the DST the junior — the
# rel WORD is noisy. So we relabel from the queried entity's POV by edge POSITION,
# keeping the gendered word only when it actually describes the OTHER end.
_PARENT_WORDS = {"father", "mother"}
_CHILD_WORDS = {"son", "daughter"}
_GRANDPARENT_WORDS = {"grandfather", "grandmother"}
_GRANDCHILD_WORDS = {"grandson", "granddaughter"}
_SPOUSE_WORDS = {"husband", "wife", "spouse", "married"}
_SIBLING_WORDS = {"brother", "sister", "sibling"}
_SPOUSE_INVERSE = {"husband": "wife", "wife": "husband"}

_PARENT_AXIS = _PARENT_WORDS | _CHILD_WORDS | {"parent", "child"}
_GRAND_AXIS = _GRANDPARENT_WORDS | _GRANDCHILD_WORDS | {"grandparent", "grandchild"}
_LINEAGE_AXIS = {"ancestor", "descendant"}

# labels specific enough to win a de-dup tie over a generic one
_SPECIFIC_KIN = (_PARENT_WORDS | _CHILD_WORDS | _GRANDPARENT_WORDS
                 | _GRANDCHILD_WORDS | {"husband", "wife", "brother", "sister"})


def _kin_label(rel: str, queried_is_src: bool) -> Optional[str]:
    """Relationship label from the QUERIED entity's POV (src is always senior).

    Returns the gendered word when it describes the OTHER (non-queried) end, else
    a direction-correct generic ('parent'/'child'/...). None for non-kin rels so
    the caller keeps its existing handling.
    """
    r = (rel or "").lower()
    if r in _PARENT_AXIS:
        if queried_is_src:                      # other end is my child
            return r if r in _CHILD_WORDS else "child"
        return r if r in _PARENT_WORDS else "parent"   # other end is my parent
    if r in _GRAND_AXIS:
        if queried_is_src:
            return r if r in _GRANDCHILD_WORDS else "grandchild"
        return r if r in _GRANDPARENT_WORDS else "grandparent"
    if r in _LINEAGE_AXIS:
        return "descendant" if queried_is_src else "ancestor"
    if r in _SPOUSE_WORDS:
        if queried_is_src:
            return r if r in ("husband", "wife") else "spouse"
        return _SPOUSE_INVERSE.get(r, "spouse")
    if r in _SIBLING_WORDS:
        if queried_is_src:
            return r if r in ("brother", "sister") else "sibling"
        return "sibling"
    return None


def _dedupe_kin(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse multiple family edges to the SAME displayed person, preferring the
    most specific (gendered) label — so 'Dasharatha (father)' wins over the
    generic 'Dasharatha (parent)' the reciprocal edge produced."""
    best: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for e in entries:
        key = (e.get("name") or "").lower()
        if key not in best:
            best[key] = e
            order.append(key)
        else:
            cur_specific = (best[key].get("relationship") or "").lower() in _SPECIFIC_KIN
            new_specific = (e.get("relationship") or "").lower() in _SPECIFIC_KIN
            if new_specific and not cur_specific:
                best[key] = e
    return [best[k] for k in order]


def character_sheet(name: str, memory: Memory,
                    operator: Optional[Operator] = None) -> Dict[str, Any]:
    """Full character profile: identity, relationships, abilities, decode meaning.

    This is what a game client uses to render an NPC's stats, dialogue options,
    and behavior rules. Every field traces to the graph.
    """
    n = _norm(name)
    if not n:
        return _envelope(False, None, {}, [{"code": "empty", "message": "no name"}])

    entity = _resolve_entity(n, memory)
    if not entity:
        return _envelope(False, None, {},
                         [{"code": "not_found", "message": f"'{name}' not in graph"}])

    eid = entity["id"]

    # partition edges by type
    weapons = []
    boons = []
    curses = []
    family = []
    gurus = []
    other_rels = []

    for ed in memory.edges:
        src, dst, rel = ed.get("src"), ed.get("dst"), ed.get("rel", "")
        if src != eid and dst != eid:
            continue

        other_id = dst if src == eid else src
        other = _find_by_id(other_id, memory.entities)
        other_name = other.get("name", other_id) if other else other_id
        direction = "outgoing" if src == eid else "incoming"
        verse_ranges = ed.get("verse_ranges", [])[:3]

        entry = {
            "name": other_name,
            "relationship": rel,
            "direction": direction,
            "verse_ranges": verse_ranges,
        }

        if _is_weapon_rel(rel, other_name):
            # distinguish the WEAPON itself from the SOURCE who armed you:
            # "obtained_weapon_from Rudra" -> Rudra is a source, not a weapon;
            # "wields Gandiva" / "uses Brahmastra" -> the target IS the weapon.
            t = (other_name or "").lower()
            r = (rel or "").lower()
            is_named_weapon = any(root in t for root in _WEAPON_TARGET_ROOTS)
            is_source_rel = ("from" in r or "grants_weapon" in r
                             or r in ("gave_weapon", "gave", "given", "receives",
                                      "received_weapon_from"))
            entry["weapon_role"] = (
                "weapon" if is_named_weapon
                else "source" if is_source_rel
                else "weapon")
            weapons.append(entry)
        elif rel in _BOON_PREDS:
            boons.append(entry)
        elif rel in _CURSE_PREDS:
            curses.append(entry)
        elif rel in _FAMILY_PREDS:
            lbl = _kin_label(rel, src == eid)
            if lbl:
                entry["relationship"] = lbl
            family.append(entry)
        elif rel in _GURU_PREDS:
            gurus.append(entry)
        else:
            other_rels.append(entry)

    # factsheet (literal grounding)
    fs = factsheet(name, memory)
    literal_brief = ""
    if fs.get("success") and fs.get("data"):
        literal_brief = fs["data"].get("brief", "")

    # decode meaning (consciousness layer)
    decode_meaning = None
    if operator:
        from tools.read_pass.decode import decode
        dec = decode(name, operator)
        if dec.get("success") and dec.get("data"):
            decode_meaning = {
                "meaning": dec["data"].get("meaning", ""),
                "valence": dec["data"].get("valence"),
                "source": dec["data"].get("source", ""),
            }

    data = {
        "identity": {
            "name": entity.get("name", ""),
            "kind": entity.get("kind", ""),
            "aliases": entity.get("all_forms", []),
            "chapters_present": len(entity.get("chapters", [])),
            "verse_ranges": entity.get("verse_ranges", [])[:5],
        },
        "literal_brief": literal_brief,
        "decode_meaning": decode_meaning,
        "family": _dedupe_kin(family),
        "gurus": gurus,
        "weapons": weapons,
        "boons": boons,
        "curses": curses,
        "other_relationships": other_rels[:20],
    }

    return _envelope(True, data,
                     {"n_total_edges": len(family) + len(gurus) + len(weapons)
                      + len(boons) + len(curses) + len(other_rels)},
                     [])


def character_abilities(name: str, memory: Memory) -> Dict[str, Any]:
    """Combat-relevant abilities: weapons, boons, curses, guru lineage.

    Each ability includes the verse citation and any known constraints from the
    graph (e.g., Pashupatastra requires Shiva's boon).
    """
    sheet = character_sheet(name, memory)
    if not sheet["success"]:
        return sheet

    d = sheet["data"]
    abilities = []

    for w in d.get("weapons", []):
        abilities.append({
            "name": w["name"],
            "type": "weapon",
            "source": w["name"] if w["direction"] == "incoming" else "self",
            "relationship": w["relationship"],
            "verse_ranges": w["verse_ranges"],
        })

    for b in d.get("boons", []):
        abilities.append({
            "name": b["name"],
            "type": "boon",
            "granted_by": b["name"] if b["direction"] == "incoming" else "self",
            "relationship": b["relationship"],
            "verse_ranges": b["verse_ranges"],
        })

    for c in d.get("curses", []):
        abilities.append({
            "name": c["name"],
            "type": "curse",
            "cursed_by": c["name"] if c["direction"] == "incoming" else "self",
            "relationship": c["relationship"],
            "verse_ranges": c["verse_ranges"],
        })

    # guru lineage affects what divine weapons are accessible
    guru_chain = [g["name"] for g in d.get("gurus", [])]

    return _envelope(True, {
        "character": d["identity"]["name"],
        "abilities": abilities,
        "guru_lineage": guru_chain,
        "n_abilities": len(abilities),
    }, {}, [])


def character_relationships(name: str, memory: Memory) -> Dict[str, Any]:
    """All relationships for a character — for dialogue and interaction logic."""
    rc = recall(name, memory)
    if not rc.get("success"):
        return _envelope(False, None, {}, rc.get("errors", []))

    data = rc.get("data", {})
    return _envelope(True, {
        "character": name,
        "entities": data.get("entities", []),
        "relationships": data.get("relationships", []),
        "decode_keys": data.get("decode_keys", []),
    }, rc.get("metadata", {}), [])


def dialogue_context(name: str, topic: str, memory: Memory,
                     operator: Optional[Operator] = None) -> Dict[str, Any]:
    """Everything an LLM needs to generate in-character dialogue for an NPC.

    Returns the character's identity, their relationship to the topic, relevant
    decode keys, and the literal grounding — so the LLM speaks FROM knowledge,
    not imagination.
    """
    sheet = character_sheet(name, memory, operator)
    if not sheet["success"]:
        return sheet

    # also recall what the graph knows about the topic itself
    topic_recall = recall(topic, memory)
    topic_data = topic_recall.get("data", {}) if topic_recall.get("success") else {}

    data = {
        "speaker": sheet["data"],
        "topic_context": {
            "entities": topic_data.get("entities", [])[:8],
            "relationships": topic_data.get("relationships", [])[:10],
            "decode_keys": topic_data.get("decode_keys", [])[:5],
        },
    }
    return _envelope(True, data, {}, [])


def _resolve_entity(n: str, memory: Memory) -> Optional[Dict[str, Any]]:
    """Resolve a query name to its entity — EXACT PRIMARY NAME wins over alias.

    Critical post-de-merge: many entities list others as `aspect_of` forms
    (Vishnu's all_forms contains "Krishna", "Arjuna"; Kurma aliases "Shiva").
    A naive "first entity whose form-list contains the name" hijacks the query
    to the biggest blob — Krishna -> Vishnu, Shiva -> Kurma. So we look for an
    entity whose OWN name == the query first, and only fall back to alias
    matching when no such standalone node exists. Ties on exact name break to
    the most chapter-present (the canonical node).
    """
    n = _norm(n)
    # 1. exact primary-name match (the entity that IS this name)
    exact = [e for e in memory.entities if _norm(e.get("name", "")) == n]
    if exact:
        return max(exact, key=lambda e: len(e.get("chapters", [])))
    # 2. fall back to alias/form match only when no standalone node exists
    for e in memory.entities:
        forms = list(e.get("all_forms", []) or [])
        if any(_norm(x) == n for x in forms if x):
            return e
    return None


def _find_by_id(eid: str, entities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return next((e for e in entities if e.get("id") == eid), None)
