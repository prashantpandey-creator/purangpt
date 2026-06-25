"""codex — the canonical weapon-truth, assembled from the corpus.

The source of truth a "true to the Puranic interpretation, to the teeth" game
needs: combat reads it for rules, a future animation layer reads it for how a
weapon LOOKS and BEHAVES — neither invents. It is NOT a hand-built cathedral;
it ASSEMBLES whatever the corpus holds today from three layers and grows as the
graph decodes more:

  1. GRAPH (literal)   — the weapon entity, who wields it, where it came from,
                         what it did (wields/obtained_weapon_from/uses/killed).
  2. CURATED (rules)   — engagement physics from _ASTRA_RULES (counters, surrender,
                         restrictions) — grounded-in-principle, confidence-tiered.
  3. DECODE (inner)    — Sharma's interpretation key, the weapon's SUBTLE meaning
                         ("Gandiva = the spine / channel of prana"; "Vajra = the
                         indestructible spiritual power, the spine"). This is what
                         makes it true to the *interpretation*, not just the object.

Every field is grounded or honestly absent. An animation layer that obeys this
codex cannot contradict the texts — that is the whole point.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm
from narrative_engine.character import _resolve_entity, _find_by_id, _is_weapon_rel
from narrative_engine import combat


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _decode_meaning(name: str, memory: Memory) -> str:
    """Sharma's inner-meaning key for a weapon, if the corpus decoded one."""
    n = _norm(name)
    # try exact, then substring (e.g. "Gandiva" matches "Gandiva bow")
    best = ""
    for k in memory.keys:
        sym = _norm(k.get("symbol", ""))
        if sym == n:
            return k.get("meaning", "")
        if (n in sym or sym in n) and sym and not best:
            best = k.get("meaning", "")
    return best


def weapon_entry(name: str, memory: Memory) -> Dict[str, Any]:
    """One canonical weapon record assembled from all three layers.

    Fields are grounded where the corpus has them and flagged when it doesn't —
    so the entry never lies, and an animation/combat client can trust each field
    or see exactly where the seam is.
    """
    ent = _resolve_entity(_norm(name), memory)
    in_graph = ent is not None

    # --- layer 1: literal graph facts -----------------------------------------
    wielders: List[Dict[str, str]] = []
    sources: List[str] = []
    deeds: List[str] = []
    if in_graph:
        eid = ent["id"]
        for ed in memory.edges:
            src, dst, rel = ed.get("src"), ed.get("dst"), ed.get("rel", "")
            if dst != eid and src != eid:
                continue
            other_id = src if dst == eid else dst
            other = _find_by_id(other_id, memory.entities)
            oname = other.get("name", "") if other else ""
            rl = (rel or "").lower()
            # who wields THIS weapon (edge points wielder -> weapon)
            if dst == eid and ("wield" in rl or rl in ("uses", "uses_weapon",
                                                       "invoked", "obtained")):
                wielders.append({"name": oname, "relationship": rel})
            # where it came from (X gave/granted this weapon)
            elif dst == eid and ("gave" in rl or "grant" in rl or "from" in rl):
                sources.append(oname)
            # what it did
            elif src == eid and rl in ("killed", "kills", "slays", "destroyed",
                                       "neutralizes", "defeated"):
                deeds.append(f"{rel} {oname}")

    # --- layer 2: curated engagement rules + grounding confidence -------------
    rules_env = combat.get_astra_rules(name, memory)
    rules = rules_env["data"]["rules"] if rules_env["success"] else None
    grounding = combat.ground_astra(name, memory)["data"]

    # --- layer 3: Sharma's inner meaning --------------------------------------
    inner = _decode_meaning(name, memory)

    # --- honesty: which fields are grounded vs absent -------------------------
    gaps = []
    if not in_graph:
        gaps.append("not an entity in the graph (existence unconfirmed by corpus)")
    if rules is None:
        gaps.append("no curated engagement rules (combat behavior unspecified)")
    if not inner:
        gaps.append("no decoded inner meaning (interpretation layer absent)")
    if not wielders:
        gaps.append("no recorded wielder")

    return _envelope(
        True,
        {
            "name": name,
            "in_graph": in_graph,
            "kind": ent.get("kind", "") if in_graph else "",
            # layer 1 — literal
            "wielders": wielders[:8],
            "sources": sorted(set(sources))[:8],
            "deeds": deeds[:8],
            # layer 2 — engagement
            "rules": rules,
            "confidence": grounding.get("confidence", "none"),
            # layer 3 — interpretation (true-to-the-teeth requires this)
            "inner_meaning": inner,
            # animation contract (text-grounded descriptors; filled as decoded)
            "animation_hints": _animation_hints(name, rules, inner),
            # honesty
            "gaps": gaps,
            "truth_level": _truth_level(in_graph, rules, inner),
        },
        {"in_graph": in_graph, "has_rules": rules is not None,
         "has_inner": bool(inner), "n_gaps": len(gaps)},
        [],
    )


def _truth_level(in_graph: bool, rules, inner: str) -> str:
    """How completely is this weapon grounded across the three layers?"""
    score = sum([bool(in_graph), rules is not None, bool(inner)])
    return {3: "full", 2: "strong", 1: "partial", 0: "ungrounded"}[score]


def _animation_hints(name: str, rules, inner: str) -> Dict[str, Any]:
    """The contract an animation layer obeys — text-grounded only.

    We do NOT invent visuals. We surface the behavioral facts the texts state
    (e.g. 'returns to wielder', 'cannot be stopped once launched') as motion
    hints, and leave appearance for the decode/ingestion to fill. A renderer
    reads this; it never free-styles past it.
    """
    behaviors: List[str] = []
    if rules:
        behaviors += list(rules.get("special_rules", []) or [])
        for r in rules.get("restrictions", []) or []:
            behaviors.append(f"restriction: {r}")
    return {
        # motion/behavior the texts assert (drives how it ACTS on screen)
        "behaviors": behaviors,
        # inner meaning can tint the visual register (e.g. spine/prana glow)
        "inner_register": inner or "[NEEDS-INGESTION]",
        # appearance is deliberately unfilled until decoded — do not fabricate
        "appearance": "[NEEDS-INGESTION: decode the weapon's described form]",
    }


def codex_index(memory: Memory, limit: int = 60) -> Dict[str, Any]:
    """All weapon-like entities the corpus knows, with their truth-level.

    The browsable index — what the game CAN render true-to-form today, and what
    still needs ingestion. Grows automatically as the graph decodes more.
    """
    weapon_roots = ("astra", "gandiv", "gāṇḍīv", "chakra", "bow", "trishul",
                    "vajra", "pinaka", "sharanga", "brahmashira", "pasupata",
                    "pāśupat", "sudarshan", "brahmastra")
    seen, out = set(), []
    for e in memory.entities:
        n = _norm(e.get("name", ""))
        if any(root in n for root in weapon_roots) and n not in seen:
            seen.add(n)
            inner = _decode_meaning(e.get("name", ""), memory)
            out.append({
                "name": e.get("name", ""),
                "kind": e.get("kind", ""),
                "chapters": len(e.get("chapters", [])),
                "has_inner_meaning": bool(inner),
            })
    out.sort(key=lambda x: -x["chapters"])
    return _envelope(True, {"weapons": out[:limit]},
                     {"total": len(out)}, [])
