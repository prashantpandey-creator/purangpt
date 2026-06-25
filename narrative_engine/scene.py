"""scene — one-call screen assembly for a game client.

A client rendering "you stand in Ayodhya" shouldn't have to make three round
trips (location, NPCs, what-can-I-do). assemble_scene() bundles everything
needed to paint one screen into a single envelope:

  - where you are (location detail + present NPCs from the graph)
  - who you are right now (guna, dominant quality, recent karma)
  - what you can do (movement options, talk targets, combat abilities ready)

It is pure COMPOSITION over the primitive modules — world / combat / seeker.
No new graph access patterns, no new state. If the graph is thin for a place,
the scene degrades honestly (empty npc list, no exits) rather than inventing.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory
from narrative_engine import world, combat, character, encounters
from narrative_engine.seeker import SeekerState


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def assemble_scene(seeker: SeekerState, memory: Memory,
                   location: Optional[str] = None,
                   act: Optional[str] = None) -> Dict[str, Any]:
    """Bundle location + self + available actions for one screen render.

    location defaults to the seeker's current_location. Returns success=False
    only if there is genuinely no location to render (no arg and seeker is
    nowhere); a location unknown to the graph still returns a valid scene with
    empty surroundings so the client can show "an uncharted place."

    `act` (optional granthi-act key) folds in the encounters that populate that
    act AND the weapons/astras the present NPCs wield — so a fight scene knows
    what's in play, all graph-grounded.
    """
    loc_name = location or seeker.current_location
    if not loc_name:
        return _envelope(False, None, {},
                         [{"code": "no_location",
                           "message": "seeker has no location and none was given"}])

    # --- where you are -------------------------------------------------------
    loc_result = world.location_detail(loc_name, memory)
    if loc_result["success"]:
        loc_data = loc_result["data"]
        place = loc_data["location"]
        npcs = loc_data["residents"]
        events = loc_data["events"]
        exits = loc_data["connected_places"]
        charted = True
    else:
        # unknown to the graph — render an honest blank stage, don't fabricate
        place = {"name": loc_name, "kind": "uncharted", "aliases": [],
                 "chapters": [], "verse_ranges": []}
        npcs, events, exits = [], [], []
        charted = False

    # --- who you are right now ----------------------------------------------
    recent_choices = [
        {"event": c.event_id, "choice": c.choice}
        for c in seeker.choices[-3:]
    ]
    self_state = {
        "name": seeker.name,
        "guna": seeker.guna.to_dict(),
        "dominant_quality": seeker.guna.dominant,
        "tapasya": {d: t.accumulated for d, t in seeker.tapasya.items()},
        "boons": [b.get("name", "") for b in seeker.boons],
        "curses": [c.get("name", "") for c in seeker.curses],
        "recent_choices": recent_choices,
        "visited_count": len(seeker.visited_locations),
    }

    # --- what you can do -----------------------------------------------------
    abilities = combat.available_abilities(seeker, memory)
    ready_astras = abilities["data"].get("available", []) if abilities["success"] else []
    blocked_astras = abilities["data"].get("blocked", []) if abilities["success"] else []

    actions = {
        "move_to": [
            {"name": e["name"], "kind": e.get("kind", ""),
             "via": e.get("relationship", "")}
            for e in exits
        ],
        "talk_to": [
            {"name": n["name"], "kind": n.get("kind", "")}
            for n in npcs
        ],
        "combat_ready": [
            {"name": a["name"], "type": a.get("type", "")}
            for a in ready_astras
        ],
        "combat_blocked": [
            {"name": a["name"], "reasons": a.get("reasons", [])}
            for a in blocked_astras
        ],
        # always-available verbs (don't depend on graph state)
        "always": ["meditate", "look", "status", "karma"],
    }

    # --- the armory in play: what the present NPCs wield (graph-grounded) -----
    # A fight scene needs to know which iconic weapons/astras are on the field.
    armory = []
    for n in npcs[:8]:  # cap — top residents
        sheet = character.character_sheet(n["name"], memory)
        if not sheet["success"]:
            continue
        ws = sheet["data"].get("weapons", [])
        wields = sorted({w["name"] for w in ws if w.get("weapon_role") == "weapon"})
        if wields:
            armory.append({"npc": n["name"], "wields": wields[:6]})

    # --- the encounters that belong to this act (who you might behold here) ---
    act_encounters = []
    if act:
        eb = encounters.encounters_for_act(act, memory)
        if eb["success"]:
            act_encounters = [
                {"entity": c["entity"], "register": c["register"],
                 "principle": c["principle"], "text": c["text"]}
                for c in eb["data"]["encounters"][:8]
            ]

    return _envelope(
        True,
        {
            "location": place,
            "charted": charted,
            "act": act,
            "surroundings": {
                "npcs": npcs,
                "events": events[:5],
                "exits": exits,
            },
            "self": self_state,
            "actions": actions,
            "armory": armory,
            "act_encounters": act_encounters,
        },
        {
            "charted": charted,
            "n_npcs": len(npcs),
            "n_exits": len(exits),
            "n_ready_astras": len(ready_astras),
            "n_armed_npcs": len(armory),
            "n_act_encounters": len(act_encounters),
        },
        [],
    )
