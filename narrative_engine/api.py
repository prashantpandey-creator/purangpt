"""api — FastAPI router exposing the narrative engine as JSON endpoints.

This is the game-facing surface. Any client — text adventure, Godot, UE5, web
browser, Vision Pro — hits these endpoints and gets back JSON it can render.

All endpoints follow the same envelope: {success, data, metadata, errors}.
The narrative engine never invents — every response traces to the knowledge graph.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from tools.read_pass.recall import Memory
from tools.read_pass.decode import Operator
from narrative_engine import world, character, combat, seeker, narrative, scene, lineage, encounters, codex, saga


router = APIRouter(prefix="/api/game", tags=["narrative_engine"])

# --- memory singleton (loaded once at startup) --------------------------------
_GRAPH_PATH = os.environ.get(
    "GRAPH_PATH", "tools/read_pass/out/graph_manifest.json")
_RAM_PATH = os.environ.get(
    "RAM_PATH", "tools/read_pass/out/guruji_ram.json")

_memory: Optional[Memory] = None
_operator: Optional[Operator] = None


def _get_memory() -> Memory:
    global _memory
    if _memory is None:
        _memory = Memory.load(_GRAPH_PATH, _RAM_PATH)
    return _memory


def _get_operator() -> Optional[Operator]:
    global _operator
    if _operator is None:
        try:
            mem = _get_memory()
            _operator = Operator(mem.keys)
        except Exception:
            pass
    return _operator


# --- request models -----------------------------------------------------------

class LocationQuery(BaseModel):
    name: str

class NearbyQuery(BaseModel):
    name: str
    max_hops: int = 2

class JourneyQuery(BaseModel):
    character: str
    limit: int = 30

class SceneQuery(BaseModel):
    location: Optional[str] = None
    act: Optional[str] = None

class CharacterQuery(BaseModel):
    name: str

class DialogueQuery(BaseModel):
    character: str
    topic: str

class AstraQuery(BaseModel):
    name: str

class AttackQuery(BaseModel):
    attacker: str
    astra: str
    defender: str
    defender_action: str = "resist"

class EncounterQuery(BaseModel):
    astra: str
    defender: str
    defender_action: str = "resist"
    record_karma: bool = True

class MeditateQuery(BaseModel):
    deity: str
    intensity: float = 1.0

class ChoiceQuery(BaseModel):
    event_id: str
    description: str
    choice: str
    guna_shift: Dict[str, float] = Field(default_factory=dict)
    consequences: List[str] = Field(default_factory=list)

class NarrativeQuery(BaseModel):
    text_name: str
    chapter: Optional[str] = None

class ConsequenceQuery(BaseModel):
    entity: str
    max_depth: int = 5


# --- seeker state: DB-backed with an in-memory hot cache ----------------------
# The dict is a per-process cache; persistence.py is the durable store. On a
# cache miss we try to load from Postgres; if there's no DB the engine still
# works, it just won't survive a restart (graceful degradation).
from narrative_engine import persistence

_seekers: Dict[str, seeker.SeekerState] = {}


def _get_seeker(session_id: str) -> seeker.SeekerState:
    if session_id not in _seekers:
        loaded = persistence.load_seeker(session_id)
        _seekers[session_id] = loaded if loaded is not None else seeker.SeekerState()
    return _seekers[session_id]


def _save_seeker(session_id: str, sk: seeker.SeekerState,
                 user_id: Optional[str] = None) -> None:
    """Persist after a mutation. No-op (logged) if there's no DB."""
    persistence.save_seeker(session_id, sk, user_id)


# === WORLD ENDPOINTS ==========================================================

@router.get("/world/locations")
async def list_locations():
    """All navigable locations in the Puranic universe."""
    return world.list_locations(_get_memory())


@router.post("/world/location")
async def get_location(q: LocationQuery):
    """Full detail for a location: residents, events, connected places."""
    return world.location_detail(q.name, _get_memory())


@router.post("/world/npcs")
async def get_npcs_at_location(q: LocationQuery):
    """NPCs present at a location — populate a scene."""
    return world.entities_at_location(q.name, _get_memory())


@router.post("/world/nearby")
async def get_nearby_locations(q: NearbyQuery):
    """Reachable places from a location — the navigation graph."""
    return world.nearby_locations(q.name, _get_memory(), q.max_hops)


@router.post("/world/journey")
async def get_character_journey(q: JourneyQuery):
    """Places a character visits — follow their path through the cosmos."""
    return world.character_journey(q.character, _get_memory(), q.limit)


# === CHARACTER ENDPOINTS ======================================================

@router.post("/character/sheet")
async def get_character_sheet(q: CharacterQuery):
    """Full character profile: identity, relationships, abilities, decode."""
    return character.character_sheet(q.name, _get_memory(), _get_operator())


@router.post("/character/abilities")
async def get_character_abilities(q: CharacterQuery):
    """Combat abilities: weapons, boons, curses, guru lineage."""
    return character.character_abilities(q.name, _get_memory())


@router.post("/character/relationships")
async def get_character_relationships(q: CharacterQuery):
    """All relationships — for dialogue and interaction logic."""
    return character.character_relationships(q.name, _get_memory())


@router.post("/character/dialogue")
async def get_dialogue_context(q: DialogueQuery):
    """Everything an LLM needs to generate in-character NPC dialogue."""
    return character.dialogue_context(q.character, q.topic,
                                      _get_memory(), _get_operator())


# === COMBAT ENDPOINTS =========================================================

@router.post("/combat/astra/rules")
async def get_astra_rules(q: AstraQuery):
    """Rules for a divine weapon — from the texts, enriched with graph evidence."""
    return combat.get_astra_rules(q.name, _get_memory())


@router.post("/combat/astra/grounding")
async def get_astra_grounding(q: AstraQuery):
    """Graph evidence for an astra: wielders, verse citations, chapters."""
    return combat.ground_astra(q.name, _get_memory())


@router.post("/combat/astra/available")
async def get_available_abilities(request: Request):
    """What the seeker can currently use in combat."""
    session_id = request.headers.get("x-session-id", "default")
    sk = _get_seeker(session_id)
    return combat.available_abilities(sk, _get_memory())


@router.post("/combat/astra/fire")
async def resolve_attack(q: AttackQuery):
    """Resolve an astra attack using the text's own rules (stateless)."""
    return combat.resolve_attack(q.attacker, q.astra, q.defender,
                                  q.defender_action, _get_memory())


@router.post("/combat/encounter")
async def combat_encounter(q: EncounterQuery, request: Request):
    """A full exchange that feeds the seeker's arc: attack → guna consequence → karma.

    The seeker (from x-session-id) is the attacker. Persists after the encounter.
    """
    session_id = request.headers.get("x-session-id", "default")
    user_id = request.headers.get("x-user-id")
    sk = _get_seeker(session_id)
    result = combat.encounter(sk, q.astra, q.defender, q.defender_action,
                              _get_memory(), record_karma=q.record_karma)
    _save_seeker(session_id, sk, user_id)
    return result


# === SCENE ENDPOINT (one-call screen assembly) ================================

@router.post("/scene")
async def get_scene(q: SceneQuery, request: Request):
    """Everything to paint one screen: location + self + available actions.

    If `location` is given, the seeker moves there first (and it persists).
    Otherwise renders the seeker's current location.
    """
    session_id = request.headers.get("x-session-id", "default")
    user_id = request.headers.get("x-user-id")
    sk = _get_seeker(session_id)
    if q.location and q.location != sk.current_location:
        sk.move_to(q.location)
        _save_seeker(session_id, sk, user_id)
    return scene.assemble_scene(sk, _get_memory(), q.location, q.act)


# === SEEKER ENDPOINTS =========================================================

@router.get("/seeker/state")
async def get_seeker_state(request: Request):
    """Player's current state: guna, tapasya, boons, curses, karma."""
    session_id = request.headers.get("x-session-id", "default")
    return seeker.get_state(_get_seeker(session_id))


@router.get("/seeker/karma")
async def get_seeker_karma(request: Request):
    """The path you walked — every choice, guna drift, turning points."""
    session_id = request.headers.get("x-session-id", "default")
    return seeker.karma_chain(_get_seeker(session_id))


@router.post("/seeker/meditate")
async def do_meditate(q: MeditateQuery, request: Request):
    """Perform tapasya toward a deity. Shifts guna toward sattva."""
    session_id = request.headers.get("x-session-id", "default")
    user_id = request.headers.get("x-user-id")
    sk = _get_seeker(session_id)
    result = seeker.meditate(sk, q.deity, q.intensity)
    _save_seeker(session_id, sk, user_id)
    return result


@router.post("/seeker/choice")
async def make_dharmic_choice(q: ChoiceQuery, request: Request):
    """Record a dharmic choice. Applies guna shift and consequences."""
    session_id = request.headers.get("x-session-id", "default")
    user_id = request.headers.get("x-user-id")
    sk = _get_seeker(session_id)
    result = seeker.make_choice(sk, q.event_id, q.description,
                                q.choice, q.guna_shift, q.consequences)
    _save_seeker(session_id, sk, user_id)
    return result


@router.delete("/seeker/state")
async def reset_seeker_state(request: Request):
    """Wipe a seeker's state — fresh start. Clears cache and persisted row."""
    session_id = request.headers.get("x-session-id", "default")
    _seekers.pop(session_id, None)
    deleted = persistence.delete_seeker(session_id)
    return {"success": True, "data": {"reset": True, "db_row_deleted": deleted},
            "metadata": {}, "errors": []}


# === NARRATIVE ENDPOINTS ======================================================

@router.post("/narrative/events")
async def get_narrative_events(q: NarrativeQuery):
    """Events in a specific text, optionally filtered by chapter."""
    return narrative.get_narrative_events(q.text_name, _get_memory(), q.chapter)


@router.post("/narrative/consequences")
async def get_consequence_chain(q: ConsequenceQuery):
    """Trace cause-effect chains from an entity/event through the graph."""
    return narrative.consequence_chain(q.entity, _get_memory(), q.max_depth)


# === LINEAGE ENDPOINTS (the guru-spine, the bible's flagship MULTI-HOP) ========

@router.get("/lineage/spine")
async def get_guru_spine():
    """The Kriya parampara apex→present: Babaji→Lahiri→Tinkori→Satyacharan→Sharma.
    The graph-only multi-hop — each link verified via curated guru edges."""
    return lineage.guru_spine(_get_memory())


@router.post("/lineage/transmission")
async def get_transmission(q: CharacterQuery):
    """The 'Hand on the Head' events for a guru — verbatim from the biography."""
    return lineage.hand_on_the_head(_get_memory(), q.name)


# === ENCOUNTER BANK (Guruji's lived encounters, classified by act/register) ====

@router.get("/encounters/bank")
async def get_encounter_bank():
    """All of Guruji's lived encounters, tagged register/act/principle."""
    return encounters.encounter_bank(_get_memory())


@router.post("/encounters/act")
async def get_encounters_for_act(q: NarrativeQuery):
    """Encounters feeding one granthi-act (q.text_name = act key)."""
    return encounters.encounters_for_act(q.text_name, _get_memory())


@router.post("/encounters/with")
async def get_encounters_with(q: CharacterQuery):
    """Every recorded encounter with a given being."""
    return encounters.encounters_with(q.name, _get_memory())


# === WEAPON CODEX (canonical weapon-truth: graph + rules + inner meaning) ======

@router.get("/codex/weapons")
async def get_codex_index():
    """All weapon entities the corpus knows, with truth-level — the browsable list."""
    return codex.codex_index(_get_memory())


@router.post("/codex/weapon")
async def get_weapon_entry(q: CharacterQuery):
    """One weapon's full truth: wielders + rules + Sharma's inner meaning + anim hints.
    Every field grounded or honestly flagged — combat and animation read from this."""
    return codex.weapon_entry(q.name, _get_memory())


# === SAGA (a character's whole story-braid: weapon+curse+lineage+identity+deeds) =

@router.post("/saga")
async def get_saga(q: CharacterQuery):
    """Everything the graph knows about a character, sorted into story strands —
    the convergence layer. One entity, the full braid, all corpus-cited."""
    return saga.saga(q.name, _get_memory())


@router.post("/saga/convergence")
async def get_convergence(q: CharacterQuery):
    """Proof metric: how many story strands a single character carries."""
    return saga.convergence_check(q.name, _get_memory())


# === META ENDPOINTS ===========================================================

@router.get("/meta/stats")
async def get_graph_stats():
    """Graph statistics — entity count, edge count, predicate vocabulary."""
    mem = _get_memory()
    pred_counts: Dict[str, int] = {}
    for ed in mem.edges:
        rel = ed.get("rel", "")
        pred_counts[rel] = pred_counts.get(rel, 0) + 1

    return {
        "success": True,
        "data": {
            "n_entities": len(mem.entities),
            "n_edges": len(mem.edges),
            "n_decode_keys": len(mem.keys),
            "n_distinct_predicates": len(pred_counts),
            "top_predicates": sorted(pred_counts.items(),
                                      key=lambda x: -x[1])[:20],
        },
        "metadata": {},
        "errors": [],
    }


@router.get("/meta/health")
async def health_check():
    """Is the narrative engine operational?"""
    try:
        mem = _get_memory()
        return {
            "success": True,
            "data": {
                "status": "operational",
                "graph_loaded": len(mem.entities) > 0,
                "n_entities": len(mem.entities),
                "n_edges": len(mem.edges),
                "decode_keys_loaded": len(mem.keys) > 0,
                **persistence.db_status(),
            },
            "metadata": {},
            "errors": [],
        }
    except Exception as e:
        return {
            "success": False,
            "data": {"status": "error"},
            "metadata": {},
            "errors": [{"code": "load_error", "message": str(e)[:200]}],
        }
