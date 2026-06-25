"""combat — astra rules and guna-based ability resolution.

Divine weapons (astras) in the Puranas have RULES — not invented game mechanics,
but constraints explicitly described in the texts. This module encodes those rules
and resolves combat interactions through the knowledge graph.

Examples from the texts:
  - Brahmastra can counter Brahmastra (Mahabharata)
  - Narayanastra grows stronger against resistance, weak against surrender
  - Pashupatastra cannot be used against lesser warriors
  - Karna's Brahmastra fails because of Parashurama's curse

The graph enforces these. A character can't use an astra they haven't earned,
can't fire it when cursed, and the rules of engagement come from the verses.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm
from narrative_engine.seeker import SeekerState
from narrative_engine.character import character_abilities, character_relationships


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# relationship roots that mean "handles this weapon" — substring-matched against
# normalized predicates so "received_astra", "uses_weapon", "previously_owned"
# all count, but kinship predicates (son/father/brother) do not.
_WIELD_RELS = {
    "wield", "use", "uses", "used", "fire", "fires", "fired", "receiv",
    "owned", "owns", "wields_weapon", "uses_weapon", "received_astra",
    "grant", "grants", "gave", "gives", "given", "withdraw", "withdraws",
    "guard", "guarded", "carries", "carried", "launch", "hurl", "hurled",
}


# known astra rules from the texts (expandable as more texts are decoded)
# each rule is a dict with conditions and effects
_ASTRA_RULES: Dict[str, Dict[str, Any]] = {
    "brahmastra": {
        "type": "astra",
        "countered_by": ["brahmastra"],
        "restrictions": ["cannot recall once fired", "must not use against non-combatants"],
        "guna_requirement": {"min_sattva": 0.25},
        "tapasya_requirement": {"deity": "brahma", "min": 50},
        "source_text": "mahabharata",
    },
    "pashupatastra": {
        "type": "astra",
        "countered_by": [],
        "restrictions": ["cannot use against lesser warriors",
                         "destroys everything in its path"],
        "guna_requirement": {"min_sattva": 0.35},
        "tapasya_requirement": {"deity": "shiva", "min": 100},
        "source_text": "mahabharata",
    },
    "narayanastra": {
        "type": "astra",
        "countered_by": ["surrender"],
        "special_rules": ["grows stronger against resistance",
                          "neutralized by laying down arms"],
        "restrictions": ["single use per incarnation"],
        "guna_requirement": {"min_sattva": 0.30},
        "tapasya_requirement": {"deity": "vishnu", "min": 80},
        "source_text": "mahabharata",
    },
    "sudarshana_chakra": {
        "type": "divine_weapon",
        "countered_by": [],
        "restrictions": ["only wielded by Vishnu or his avatars"],
        "special_rules": ["returns to wielder after striking",
                          "cannot be stopped once launched"],
        "source_text": "bhagavata",
    },
    "gandiva": {
        "type": "divine_bow",
        "countered_by": [],
        "restrictions": [],
        "special_rules": ["infinite arrows when strung",
                          "given by Agni at Khandava"],
        "source_text": "mahabharata",
    },
    "vajra": {
        "type": "divine_weapon",
        "countered_by": [],
        "restrictions": ["wielded by Indra"],
        "special_rules": ["made from Dadhichi's bones"],
        "source_text": "bhagavata",
    },
    "trishula": {
        "type": "divine_weapon",
        "countered_by": [],
        "restrictions": ["wielded by Shiva"],
        "source_text": "bhagavata",
    },
}


# astra entities are NOT tagged kind=weapon in the graph — they live scattered
# across 'practice'/'concept'/empty kinds with inconsistent naming ("Brahma astra"
# vs "brahmastra" vs "Brahmāstra"). We match on a normalized root so curated rules
# can be grounded against whatever form the graph actually stored.
def _astra_roots(astra_name: str) -> set:
    """Normalized name variants for matching a curated astra to graph entities.

    Splitting must happen on the RAW name (before _norm strips underscores and
    spaces), then each variant is normalized. _norm collapses to alnum-only, so
    "sudarshana chakra" and "sudarshana_chakra" both become "sudarshanachakra" —
    we therefore also keep the split tokens (e.g. "sudarshana") as their own roots.
    """
    raw = astra_name.strip()
    variants = {raw}

    # underscore / space split on the RAW name → keep first token + joined forms
    sep_tokens = raw.replace("_", " ").split()
    if len(sep_tokens) > 1:
        variants.add(" ".join(sep_tokens))
        variants.add(sep_tokens[0])      # "sudarshana"
        variants.add("".join(sep_tokens))

    # "<stem>astra" → also expose the stem and a spaced form
    n = _norm(raw)
    if n.endswith("astra") and len(n) > 5:
        stem = n[:-5]
        if stem:
            variants.add(stem)
            variants.add(f"{stem} astra")

    # normalize every variant; drop empties
    return {_norm(v) for v in variants if _norm(v)}


def ground_astra(astra_name: str, memory: Memory, max_evidence: int = 5) -> Dict[str, Any]:
    """Find graph evidence for an astra: entities, wielders, verse citations.

    Read-only. Survives graph rebuilds — matches on normalized name roots, so it
    works whether the astra is stored as 'Brahma astra' or 'brahmastra'.
    """
    roots = _astra_roots(astra_name)

    # A weapon node should be small. If a "match" carries hundreds of chapters,
    # it's a mega-node (a deity that absorbed the weapon as an alias via identity
    # merge) — NOT the weapon. Treating it as the weapon drags in the deity's
    # whole edge set. We track these separately and lower confidence instead.
    _MEGA_NODE_CHAPTERS = 100

    matched_entities = []
    matched_ids = set()
    absorbed_into = []  # weapon swallowed into a larger node
    for e in memory.entities:
        forms = [e.get("name", "")] + list(e.get("all_forms", []) or [])
        if any(_norm(f) in roots for f in forms if f):
            # is this the weapon itself, or a mega-node it got merged into?
            if len(e.get("chapters", [])) >= _MEGA_NODE_CHAPTERS and \
                    _norm(e.get("name", "")) not in roots:
                absorbed_into.append(e.get("name", ""))
                continue
            matched_entities.append(e)
            matched_ids.add(e.get("id"))

    wielders = []
    verse_cites = []
    seen_wielders = set()
    for ed in memory.edges:
        src, dst, rel = ed.get("src"), ed.get("dst"), ed.get("rel", "")
        if src in matched_ids or dst in matched_ids:
            other_id = dst if src in matched_ids else src
            other = next((e for e in memory.entities if e.get("id") == other_id), None)
            if other and other_id not in seen_wielders:
                kind = (other.get("kind") or "").lower()
                rel_n = _norm(rel)
                # only count a connection as a WIELDER if the relationship is
                # weapon-handling — not kinship. The identity merge can fold a
                # weapon into a deity's mega-node, dragging in relatives; the
                # relationship filter rejects those (Devaki "son" is not a wielder).
                is_weapon_rel = any(
                    w in rel_n for w in _WIELD_RELS) or rel_n in _WIELD_RELS
                if (kind in {"deity", "king", "sage", "demon", "warrior", "person"}
                        and is_weapon_rel):
                    seen_wielders.add(other_id)
                    wielders.append({
                        "name": other.get("name", ""),
                        "kind": other.get("kind", ""),
                        "relationship": rel,
                    })
            for vr in (ed.get("verse_ranges") or [])[:2]:
                if vr not in verse_cites:
                    verse_cites.append(vr)

    chapters = sorted({ch for e in matched_entities for ch in e.get("chapters", [])})

    if matched_entities:
        confidence = "high"
    elif absorbed_into:
        confidence = "absorbed"  # weapon exists only as a merged alias
    else:
        confidence = "none"      # graph has no record of this astra

    return _envelope(
        True,
        {
            "astra": astra_name,
            "matched_forms": [e.get("name", "") for e in matched_entities],
            "wielders": wielders[:max_evidence],
            "verse_citations": verse_cites[:max_evidence],
            "chapters_present": len(chapters),
            "absorbed_into": absorbed_into,
            "confidence": confidence,
        },
        {"n_matched_entities": len(matched_entities),
         "n_wielders": len(wielders),
         "confidence": confidence},
        [],
    )


def get_astra_rules(astra_name: str, memory: Optional[Memory] = None) -> Dict[str, Any]:
    """Get the known rules for a divine weapon.

    If `memory` is supplied, the curated rules are enriched with live graph
    evidence (wielders, verse citations) under a `grounding` key.
    """
    key = _norm(astra_name)
    for rule_key, rules in _ASTRA_RULES.items():
        if _norm(rule_key) == key:
            data = {"astra": astra_name, "rules": rules}
            if memory is not None:
                g = ground_astra(astra_name, memory)
                if g["success"]:
                    data["grounding"] = g["data"]
            return _envelope(True, data, {}, [])

    return _envelope(False, None, {},
                     [{"code": "unknown_astra",
                       "message": f"no known rules for '{astra_name}' — "
                                  "check the graph for verse-grounded info"}])


def available_abilities(seeker: SeekerState, memory: Memory) -> Dict[str, Any]:
    """What combat abilities the seeker currently has access to, given their
    guna balance, tapasya, boons, and curses."""
    available = []
    blocked = []

    for boon in seeker.boons:
        boon_name = boon.get("name", "")
        key = _norm(boon_name)
        rules = None
        for rule_key, r in _ASTRA_RULES.items():
            if _norm(rule_key) == key:
                rules = r
                break

        if rules:
            # check guna requirement
            guna_ok = True
            guna_req = rules.get("guna_requirement", {})
            if guna_req.get("min_sattva") and seeker.guna.sattva < guna_req["min_sattva"]:
                guna_ok = False

            # check tapasya requirement
            tap_ok = True
            tap_req = rules.get("tapasya_requirement", {})
            if tap_req:
                deity = tap_req.get("deity", "")
                min_tap = tap_req.get("min", 0)
                tap = seeker.tapasya.get(deity)
                if not tap or tap.accumulated < min_tap:
                    tap_ok = False

            # check curses
            cursed = any(_norm(c.get("name", "")) == key for c in seeker.curses)

            if guna_ok and tap_ok and not cursed:
                available.append({
                    "name": boon_name,
                    "type": rules.get("type", "unknown"),
                    "rules": rules,
                    "status": "ready",
                })
            else:
                reasons = []
                if not guna_ok:
                    reasons.append(f"guna imbalance (need sattva >= {guna_req.get('min_sattva')})")
                if not tap_ok:
                    reasons.append(f"insufficient tapasya with {tap_req.get('deity')}")
                if cursed:
                    reasons.append("blocked by curse")
                blocked.append({
                    "name": boon_name,
                    "type": rules.get("type", "unknown"),
                    "status": "blocked",
                    "reasons": reasons,
                })
        else:
            available.append({
                "name": boon_name,
                "type": "unknown",
                "rules": None,
                "status": "ready",
            })

    return _envelope(True, {
        "available": available,
        "blocked": blocked,
        "guna": seeker.guna.to_dict(),
    }, {"n_available": len(available), "n_blocked": len(blocked)}, [])


def resolve_attack(attacker_name: str, astra_name: str,
                   defender_name: str, defender_action: str,
                   memory: Memory) -> Dict[str, Any]:
    """Resolve an astra attack using the text's own rules.

    defender_action: 'resist', 'surrender', 'counter_with:<astra>', 'dodge'
    """
    key = _norm(astra_name)
    rules = None
    for rule_key, r in _ASTRA_RULES.items():
        if _norm(rule_key) == key:
            rules = r
            break

    if not rules:
        return _envelope(True, {
            "outcome": "unknown",
            "reason": f"no encoded rules for {astra_name} — resolve narratively",
            "attacker": attacker_name,
            "defender": defender_name,
        }, {}, [])

    outcome = "hit"
    reason = f"{astra_name} strikes {defender_name}"

    # check counter rules
    if defender_action.startswith("counter_with:"):
        counter_astra = defender_action.split(":", 1)[1]
        counters = [_norm(c) for c in rules.get("countered_by", [])]
        if _norm(counter_astra) in counters:
            outcome = "neutralized"
            reason = f"{counter_astra} counters {astra_name} — both annihilated"

    # special rules (e.g., Narayanastra vs surrender)
    special = rules.get("special_rules", [])
    if defender_action == "surrender":
        for s in special:
            if "surrender" in s.lower() or "laying down" in s.lower():
                outcome = "neutralized"
                reason = f"{astra_name} neutralized — {s}"
                break

    if defender_action == "resist":
        for s in special:
            if "resistance" in s.lower() or "stronger" in s.lower():
                outcome = "devastating"
                reason = f"{astra_name} grows devastating — {s}"
                break

    return _envelope(True, {
        "attacker": attacker_name,
        "astra": astra_name,
        "defender": defender_name,
        "defender_action": defender_action,
        "outcome": outcome,
        "reason": reason,
        "rules_applied": rules,
    }, {}, [])


# relationship roots that make striking someone ADHARMIC (pushes tamas). These
# come from the texts' own ethics: killing kin, teachers, or the surrendered is
# the gravest violation (cf. Arjuna's despair in Gita 1 — "how can I kill my own
# kinsmen, my teachers?"). Striking a hostile demon in righteous defense does not.
_KIN_RELS = {"father", "mother", "son", "daughter", "brother", "sister",
             "wife", "husband", "grandson", "grandfather", "uncle", "nephew",
             "cousin", "kin", "kinsman", "family"}
_GURU_RELS = {"guru", "teacher", "instructs", "taught", "disciple", "student",
              "preceptor", "mentor"}


def _moral_weight(attacker: str, defender: str, defender_action: str,
                  outcome: str, memory: Memory) -> Dict[str, Any]:
    """Derive the guna consequence of an act of violence from its dharmic weight.

    Reads the attacker↔defender relationship from the graph. Striking kin or a
    teacher, or striking one who has surrendered, pushes tamas. Righteous defense
    against a hostile holds or raises sattva. Not invented mechanics — the Gita's
    own framing of why some killing corrodes and some does not.
    """
    rel_kinds = set()
    rels = character_relationships(attacker, memory)
    if rels["success"]:
        a_norm = _norm(defender)
        for ent in rels["data"].get("entities", []):
            if _norm(ent.get("name", "")) == a_norm:
                for r in ent.get("relationships", []) or []:
                    rel_kinds.add(_norm(r))

    is_kin = any(any(k in r for k in _KIN_RELS) for r in rel_kinds)
    is_guru = any(any(g in r for g in _GURU_RELS) for r in rel_kinds)
    struck_surrendered = (defender_action == "surrender" and outcome != "neutralized")

    shift: Dict[str, float] = {}
    notes: List[str] = []

    if struck_surrendered:
        shift = {"tamas": 0.12, "sattva": -0.06}
        notes.append("struck one who had laid down arms — gravely adharmic")
    elif is_kin and outcome in ("hit", "devastating"):
        shift = {"tamas": 0.10, "sattva": -0.05}
        notes.append("raised a weapon against kin — the Gita's central anguish")
    elif is_guru and outcome in ("hit", "devastating"):
        shift = {"tamas": 0.08, "sattva": -0.04}
        notes.append("struck a teacher — a violation of the guru-bond")
    elif outcome == "neutralized":
        shift = {"sattva": 0.03, "rajas": -0.02}
        notes.append("met force with restraint — neither destroyed")
    elif outcome in ("hit", "devastating"):
        # default martial act against a non-kin opponent: rajas rises (action,
        # passion), slight tamas — combat is never wholly clean.
        shift = {"rajas": 0.06, "tamas": 0.02, "sattva": -0.02}
        notes.append("a martial act in the field of battle")

    return {
        "guna_shift": shift,
        "relationship_to_defender": sorted(rel_kinds) or ["none recorded"],
        "is_kin": is_kin,
        "is_guru": is_guru,
        "struck_surrendered": struck_surrendered,
        "notes": notes,
    }


def encounter(seeker: SeekerState, astra_name: str, defender_name: str,
              defender_action: str, memory: Memory,
              record_karma: bool = True) -> Dict[str, Any]:
    """A full combat exchange that FEEDS the seeker's arc.

    Resolves the attack, derives the guna consequence from the act's dharmic
    weight (who you struck, how), applies it to the seeker, and optionally records
    a karma entry. This is what makes violence cost something — the throughline
    from a single strike to the seeker's evolving guna.
    """
    # the seeker is the attacker
    resolution = resolve_attack(seeker.name or "Seeker", astra_name,
                                defender_name, defender_action, memory)
    res = resolution["data"]
    outcome = res.get("outcome", "unknown")

    # ground the astra in the graph (high / absorbed / none) so the fight knows
    # whether it's standing on real corpus evidence or a curated/early draft.
    grounding = ground_astra(astra_name, memory)["data"]
    confidence = grounding.get("confidence", "none")

    weight = _moral_weight(seeker.name or "Seeker", defender_name,
                           defender_action, outcome, memory)
    guna_before = seeker.guna.to_dict()

    # DRAFT WARNINGS, tiered by severity so a client can render the right banner
    # and `is_canon` reflects REAL gaps (no rules / no entity), not soft ones
    # (a missing kin-edge is a caveat, not a fabrication).
    #   severity "blocking" -> the resolution itself is a placeholder/assumed
    #   severity "soft"     -> resolution stands, but one input fell back generic
    draft_warnings: List[Dict[str, str]] = []
    if outcome == "unknown":
        draft_warnings.append({"severity": "blocking", "message":
            f"No curated engagement rules for '{astra_name}' — outcome is a "
            f"placeholder; resolve narratively until the astra's verses decode."})
    if confidence == "none":
        draft_warnings.append({"severity": "blocking", "message":
            f"'{astra_name}' has no entity in the graph — its powers are "
            f"curated/assumed, not yet corpus-grounded. EARLY DRAFT."})
    elif confidence == "absorbed":
        draft_warnings.append({"severity": "blocking", "message":
            f"'{astra_name}' survives only as an alias merged into "
            f"{grounding.get('absorbed_into')} — wielder/evidence unreliable "
            f"until identity is split. EARLY DRAFT."})
    if not weight.get("relationship_to_defender") or \
            weight.get("relationship_to_defender") == ["none recorded"]:
        draft_warnings.append({"severity": "soft", "message":
            f"No recorded relationship between attacker and '{defender_name}' — "
            f"the dharmic weight falls back to a generic martial reading."})

    if weight["guna_shift"]:
        if record_karma:
            # records the choice AND applies the guna shift (make_choice does both)
            seeker.make_choice(
                event_id=f"combat:{_norm(astra_name)}_vs_{_norm(defender_name)}",
                description=f"Fired {astra_name} at {defender_name} ({defender_action})",
                choice=f"{outcome}",
                guna_shift=weight["guna_shift"],
                consequences=weight["notes"],
            )
        else:
            seeker.guna.shift(
                ds=weight["guna_shift"].get("sattva", 0),
                dr=weight["guna_shift"].get("rajas", 0),
                dt=weight["guna_shift"].get("tamas", 0),
            )

    return _envelope(True, {
        "resolution": res,
        "moral_weight": weight,
        "grounding": grounding,
        "draft_warnings": draft_warnings,
        # canon = no BLOCKING gaps. Soft caveats (a missing kin-edge) don't
        # demote a text-true resolution to "early draft".
        "is_canon": not any(w["severity"] == "blocking" for w in draft_warnings),
        "guna_before": guna_before,
        "guna_after": seeker.guna.to_dict(),
        "karma_recorded": record_karma and bool(weight["guna_shift"]),
    }, {"outcome": outcome,
        "confidence": confidence,
        "n_warnings": len(draft_warnings),
        "dominant_after": seeker.guna.dominant}, [])
