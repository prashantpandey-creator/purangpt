"""Tests for the narrative engine — run against the real graph data.

Usage: venv/bin/python -m narrative_engine.test_engine
"""
from __future__ import annotations

import json
import os
import sys

# ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_pass.recall import Memory
from narrative_engine import world, character, combat, seeker, narrative, persistence, scene

_GRAPH = "tools/read_pass/out/graph_manifest.json"
_RAM = "tools/read_pass/out/guruji_ram.json"

_passed = 0
_failed = 0


def _check(name: str, condition: bool, detail: str = ""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  OK  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}: {detail}")


def _load_memory() -> Memory:
    if not os.path.exists(_GRAPH) or not os.path.exists(_RAM):
        print(f"SKIP: graph files not found at {_GRAPH} / {_RAM}")
        sys.exit(0)
    return Memory.load(_GRAPH, _RAM)


# === WORLD TESTS ==============================================================

def test_list_locations(mem: Memory):
    print("\n--- world.list_locations ---")
    result = world.list_locations(mem)
    _check("envelope success", result["success"])
    locs = result["data"]["locations"]
    _check("has locations", len(locs) > 0, f"got {len(locs)}")
    if locs:
        _check("location has name", "name" in locs[0])
        _check("location has kind", "kind" in locs[0])


def test_location_detail(mem: Memory):
    print("\n--- world.location_detail ---")
    # try common Puranic locations
    for loc_name in ["Ayodhya", "Kurukshetra", "Lanka", "Hastinapura", "Mathura"]:
        result = world.location_detail(loc_name, mem)
        if result["success"]:
            d = result["data"]
            _check(f"{loc_name} found", True)
            _check(f"{loc_name} has location data", "location" in d)
            _check(f"{loc_name} residents is list", isinstance(d.get("residents"), list))
            break
    else:
        # if none found, test the not-found case
        result = world.location_detail("Nonexistent_Place_XYZ", mem)
        _check("not_found returns false", not result["success"])
        _check("not_found has error", len(result["errors"]) > 0)


def test_location_not_found(mem: Memory):
    print("\n--- world.location_detail (not found) ---")
    result = world.location_detail("Atlantis_Not_In_Puranas", mem)
    _check("not found returns false", not result["success"])
    _check("error code present", result["errors"][0]["code"] == "not_found")


# === CHARACTER TESTS ==========================================================

def test_character_sheet(mem: Memory):
    print("\n--- character.character_sheet ---")
    for char_name in ["Krishna", "Arjuna", "Shiva", "Rama", "Hanuman"]:
        result = character.character_sheet(char_name, mem)
        if result["success"]:
            d = result["data"]
            _check(f"{char_name} found", True)
            _check(f"{char_name} has identity", "identity" in d)
            _check(f"{char_name} identity has name", "name" in d["identity"])
            _check(f"{char_name} has family", isinstance(d.get("family"), list))
            _check(f"{char_name} has weapons", isinstance(d.get("weapons"), list))
            break
    else:
        _check("at least one character found", False, "none of the test names matched")


def test_character_abilities(mem: Memory):
    print("\n--- character.character_abilities ---")
    for char_name in ["Arjuna", "Krishna", "Rama"]:
        result = character.character_abilities(char_name, mem)
        if result["success"]:
            _check(f"{char_name} abilities envelope", True)
            _check(f"{char_name} has abilities list",
                   isinstance(result["data"].get("abilities"), list))
            break


def test_character_not_found(mem: Memory):
    print("\n--- character.character_sheet (not found) ---")
    result = character.character_sheet("Gandalf_Wrong_Universe", mem)
    _check("not found returns false", not result["success"])


def test_character_relationships(mem: Memory):
    print("\n--- character.character_relationships ---")
    for char_name in ["Krishna", "Arjuna"]:
        result = character.character_relationships(char_name, mem)
        if result["success"]:
            _check(f"{char_name} relationships envelope", True)
            _check(f"{char_name} has entities",
                   isinstance(result["data"].get("entities"), list))
            break


# === COMBAT TESTS =============================================================

def test_astra_rules():
    print("\n--- combat.get_astra_rules ---")
    result = combat.get_astra_rules("Brahmastra")
    _check("brahmastra found", result["success"])
    if result["success"]:
        rules = result["data"]["rules"]
        _check("has countered_by", "countered_by" in rules)
        _check("has restrictions", "restrictions" in rules)

    result = combat.get_astra_rules("Pashupatastra")
    _check("pashupatastra found", result["success"])

    result = combat.get_astra_rules("Narayanastra")
    _check("narayanastra found", result["success"])
    if result["success"]:
        _check("narayanastra has special rules",
               len(result["data"]["rules"].get("special_rules", [])) > 0)


def test_astra_unknown():
    print("\n--- combat.get_astra_rules (unknown) ---")
    result = combat.get_astra_rules("Lightsaber")
    _check("unknown astra returns false", not result["success"])


def test_astra_grounding(mem: Memory):
    print("\n--- combat.ground_astra ---")
    # Gandiva is a clean weapon entity in the graph
    result = combat.ground_astra("Gandiva", mem)
    _check("gandiva grounding envelope", result["success"])
    _check("gandiva confidence is high", result["data"]["confidence"] == "high",
           f"got {result['data']['confidence']}")
    _check("gandiva has wielders", len(result["data"]["wielders"]) > 0)
    # every wielder relationship must be weapon-like, never pure kinship
    for w in result["data"]["wielders"]:
        rel_n = w["relationship"].lower()
        _check(f"gandiva wielder '{w['name']}' rel is weapon-like ({rel_n})",
               any(r in rel_n for r in combat._WIELD_RELS))

    # an astra absent from this manifest => confidence none, no fabricated wielders
    result = combat.ground_astra("Pashupatastra", mem)
    _check("pashupatastra confidence none/absorbed",
           result["data"]["confidence"] in ("none", "absorbed"))
    _check("pashupatastra no fabricated wielders when absent",
           result["data"]["confidence"] != "none" or len(result["data"]["wielders"]) == 0)

    # _astra_roots variants (all roots are _norm'd → alnum-only, lowercase)
    roots = combat._astra_roots("Brahmastra")
    _check("brahmastra roots include full name", "brahmastra" in roots)
    _check("brahmastra roots include stem", "brahm" in roots)
    # underscore form: _norm strips the separator, so we keep the first token too
    roots = combat._astra_roots("Sudarshana_chakra")
    _check("sudarshana roots include joined", "sudarshanachakra" in roots)
    _check("sudarshana roots include first word", "sudarshana" in roots)

    # enriched rules carry grounding when memory is passed
    result = combat.get_astra_rules("Gandiva", mem)
    _check("enriched rules have grounding", "grounding" in result["data"])
    # without memory, no grounding key (backward compatible)
    result = combat.get_astra_rules("Gandiva")
    _check("rules without memory have no grounding", "grounding" not in result["data"])


def test_resolve_attack(mem: Memory):
    print("\n--- combat.resolve_attack ---")
    # brahmastra vs brahmastra = neutralized
    result = combat.resolve_attack("Arjuna", "Brahmastra", "Ashwatthama",
                                    "counter_with:Brahmastra", mem)
    _check("brahmastra counter envelope", result["success"])
    _check("brahmastra counter = neutralized",
           result["data"]["outcome"] == "neutralized")

    # narayanastra vs surrender = neutralized
    result = combat.resolve_attack("Ashwatthama", "Narayanastra", "Pandavas",
                                    "surrender", mem)
    _check("narayanastra surrender envelope", result["success"])
    _check("narayanastra surrender = neutralized",
           result["data"]["outcome"] == "neutralized")

    # narayanastra vs resist = devastating
    result = combat.resolve_attack("Ashwatthama", "Narayanastra", "Bhima",
                                    "resist", mem)
    _check("narayanastra resist envelope", result["success"])
    _check("narayanastra resist = devastating",
           result["data"]["outcome"] == "devastating")


def test_encounter(mem: Memory):
    print("\n--- combat.encounter (violence feeds the arc) ---")
    # striking one who surrendered is gravely adharmic (graph-independent rule)
    sk = seeker.SeekerState(name="Tester")
    before_tamas = sk.guna.tamas
    r = combat.encounter(sk, "Brahmastra", "SomeFoe", "surrender", mem)
    d = r["data"]
    _check("encounter envelope", r["success"])
    _check("encounter has resolution", "resolution" in d)
    _check("encounter has moral_weight", "moral_weight" in d)
    _check("strike-surrendered flagged", d["moral_weight"]["struck_surrendered"])
    _check("strike-surrendered pushes tamas", sk.guna.tamas > before_tamas)
    _check("strike-surrendered recorded as karma", d["karma_recorded"])
    _check("encounter wrote a choice", len(sk.choices) == 1)
    _check("choice event tags combat",
           sk.choices[0].event_id.startswith("combat:"))
    # --- grounding + draft-warning surface (honest about thin data) ---
    _check("encounter has grounding", "grounding" in d)
    _check("grounding has confidence", "confidence" in d.get("grounding", {}))
    _check("encounter has draft_warnings list", isinstance(d.get("draft_warnings"), list))
    _check("encounter has is_canon flag", "is_canon" in d)
    # warnings are tiered dicts {severity, message}
    _check("draft_warnings are tiered dicts",
           all(isinstance(w, dict) and "severity" in w and "message" in w
               for w in d.get("draft_warnings", [])))

    # an UNKNOWN astra must warn loudly (no curated rules) AND be non-canon
    sk_u = seeker.SeekerState(name="Unknowner")
    ru = combat.encounter(sk_u, "Fakeastra", "Foe", "resist", mem)
    rud = ru["data"]
    _check("unknown astra warns", len(rud.get("draft_warnings", [])) > 0,
           f"warnings={rud.get('draft_warnings')}")
    _check("unknown astra outcome is placeholder",
           rud["resolution"]["outcome"] == "unknown")
    _check("unknown astra is NOT canon", rud["is_canon"] is False)
    _check("unknown astra has a blocking warning",
           any(w["severity"] == "blocking" for w in rud["draft_warnings"]))

    # a curated, graph-present astra with only a soft (relationship) gap stays canon
    sk_c = seeker.SeekerState(name="Canoner")
    rc = combat.encounter(sk_c, "Brahmastra", "Ashwatthama", "counter_with:Brahmastra", mem)
    rcd = rc["data"]
    _check("brahmastra-counter resolves neutralized",
           rcd["resolution"]["outcome"] == "neutralized")
    # only soft warnings (no rules-gap, Brahmastra IS curated) => still canon
    _check("brahmastra fight has no blocking warning",
           not any(w["severity"] == "blocking" for w in rcd["draft_warnings"]))
    _check("brahmastra fight is canon", rcd["is_canon"] is True)

    # a neutralized exchange = restraint, nudges sattva up (not tamas)
    sk2 = seeker.SeekerState(name="Restrained")
    before_sattva = sk2.guna.sattva
    r2 = combat.encounter(sk2, "Brahmastra", "Rival", "counter_with:Brahmastra", mem)
    d2 = r2["data"]
    _check("neutralized outcome", d2["resolution"]["outcome"] == "neutralized")
    _check("restraint raises sattva", sk2.guna.sattva > before_sattva)

    # record_karma=False applies guna but writes no choice
    sk3 = seeker.SeekerState(name="Silent")
    combat.encounter(sk3, "Brahmastra", "Foe", "surrender", mem, record_karma=False)
    _check("no-karma encounter writes no choice", len(sk3.choices) == 0)
    _check("no-karma encounter still shifts guna",
           sk3.guna.tamas > seeker.SeekerState().guna.tamas)

    # the encounter's guna change shows up in the karma chain's turning points
    chain = seeker.karma_chain(sk)
    _check("encounter appears in karma chain", chain["data"]["n_choices"] == 1)

    # _moral_weight relationship classification (kin roots match correctly)
    w = combat._moral_weight("X", "Y", "resist", "hit", mem)
    _check("moral_weight returns guna_shift", "guna_shift" in w)
    _check("moral_weight lists relationship", "relationship_to_defender" in w)


# === SEEKER TESTS =============================================================

def test_seeker_state():
    print("\n--- seeker state ---")
    sk = seeker.SeekerState(name="Prashant")

    # initial state
    _check("initial sattva", 0.35 <= sk.guna.sattva <= 0.45)
    _check("initial dominant", sk.guna.dominant in ("sattva", "rajas", "tamas"))

    # meditate
    sk.meditate("Shiva", intensity=2.0)
    _check("tapasya recorded", "Shiva" in sk.tapasya)
    _check("tapasya accumulated", sk.tapasya["Shiva"].accumulated == 2.0)
    _check("sattva increased after meditation", sk.guna.sattva > 0.40)

    # make choice
    old_rajas = sk.guna.rajas
    sk.make_choice("test_event", "A test fork", "fight",
                   {"rajas": 0.1, "sattva": -0.05})
    _check("choice recorded", len(sk.choices) == 1)
    _check("rajas shifted", sk.guna.rajas > old_rajas - 0.1)

    # earn boon
    sk.earn_boon("Pashupatastra", "Shiva", "mbh_03.040")
    _check("boon earned", len(sk.boons) == 1)

    # check astra access
    can = sk.can_use_astra("Pashupatastra", "Shiva", min_tapasya=1.0)
    _check("can use pashupatastra (enough tapasya)", can["can_use"])

    can = sk.can_use_astra("Pashupatastra", "Shiva", min_tapasya=1000.0)
    _check("cannot use (insufficient tapasya)", not can["can_use"])

    # curse blocks astra
    sk.receive_curse("Pashupatastra", "Test", "")
    can = sk.can_use_astra("Pashupatastra", "Shiva", min_tapasya=1.0)
    _check("curse blocks astra", not can["can_use"])
    _check("curse reason correct", can["is_cursed"])

    # serialization roundtrip
    d = sk.to_dict()
    sk2 = seeker.SeekerState.from_dict(d)
    _check("roundtrip name", sk2.name == "Prashant")
    _check("roundtrip guna", abs(sk2.guna.sattva - sk.guna.sattva) < 0.001)
    _check("roundtrip tapasya", "Shiva" in sk2.tapasya)
    _check("roundtrip tapasya accumulated",
           sk2.tapasya["Shiva"].accumulated == sk.tapasya["Shiva"].accumulated)
    _check("roundtrip boons", len(sk2.boons) == len(sk.boons))
    _check("roundtrip curses", len(sk2.curses) == len(sk.curses))
    # the choices chain MUST survive — it's the seeker's karma history
    _check("roundtrip choices count", len(sk2.choices) == len(sk.choices),
           f"expected {len(sk.choices)}, got {len(sk2.choices)}")
    if sk2.choices and sk.choices:
        _check("roundtrip choice fields",
               sk2.choices[0].event_id == sk.choices[0].event_id and
               sk2.choices[0].choice == sk.choices[0].choice)
        # and a re-serialized copy must equal the first dump (idempotent)
        _check("roundtrip is idempotent", sk2.to_dict() == d)


def test_karma_chain():
    print("\n--- seeker.karma_chain ---")
    sk = seeker.SeekerState(name="Yudhishthira")
    # empty chain first
    r = seeker.karma_chain(sk)
    _check("empty karma envelope", r["success"])
    _check("empty karma 0 choices", r["data"]["n_choices"] == 0)
    _check("empty karma no turning points", len(r["data"]["turning_points"]) == 0)

    # a descent then redemption arc
    sk.make_choice("d1", "Stake kingdom", "gamble", {"rajas": 0.10, "sattva": -0.05}, ["kingdom_lost"])
    sk.make_choice("d2", "Stake brothers", "gamble_again", {"tamas": 0.20, "sattva": -0.08}, ["brothers_enslaved"])
    sk.make_choice("d3", "Stake Draupadi", "final_wager", {"tamas": 0.25, "sattva": -0.10}, ["draupadi_humiliated"])
    sk.make_choice("ex", "Accept exile", "accept_dharma", {"sattva": 0.30, "tamas": -0.15}, ["forest_years"])
    sk.make_choice("yk", "Answer Yaksha", "speak_truth", {"sattva": 0.25, "tamas": -0.10}, ["brothers_revived"])

    r = seeker.karma_chain(sk)
    d = r["data"]
    _check("karma 5 choices", d["n_choices"] == 5, f"got {d['n_choices']}")
    _check("karma steps ordered", [s["index"] for s in d["steps"]] == [0, 1, 2, 3, 4])
    _check("karma accrued all consequences", len(d["all_consequences"]) == 5)
    _check("karma detects turning points", len(d["turning_points"]) >= 2,
           f"got {len(d['turning_points'])}")
    # the replay must equal the live guna (faithful reconstruction)
    _check("karma replay matches current guna",
           d["replayed_guna"] == d["current_guna"])
    # first wager should push off sattva
    _check("karma first step shifts dominant",
           d["steps"][0]["dominant_changed"])
    # redemption: at least one turning point flips TO sattva
    _check("karma has redemption to sattva",
           any(tp["shifted_to"] == "sattva" for tp in d["turning_points"]))

    # timestamp survives the choice roundtrip (to_dict now emits it)
    one = sk.choices[0].to_dict()
    _check("choice to_dict emits timestamp", "timestamp" in one)


def test_persistence():
    print("\n--- persistence (DB-backed seeker state) ---")
    status = persistence.db_status()
    _check("db_status has persistence key", "persistence" in status)
    _check("db_status has db_available flag", "db_available" in status)

    # build a seeker with a full karma chain
    sk = seeker.SeekerState(name="PersistTester")
    sk.meditate("Shiva", 2.0)
    sk.earn_boon("Pashupatastra", "Shiva", "mbh_03.040")
    sk.make_choice("c1", "First fork", "act", {"sattva": 0.05})
    sk.make_choice("c2", "Second fork", "withdraw", {"tamas": 0.05})
    sk.move_to("Hastinapura")

    SID = "test-persist-session-unittest"

    if status["db_available"]:
        # real roundtrip against a live DB
        ok = persistence.save_seeker(SID, sk, user_id="unittest-user")
        _check("save succeeds with DB", ok)
        loaded = persistence.load_seeker(SID)
        _check("load returns a seeker", loaded is not None)
        if loaded:
            _check("persisted name", loaded.name == "PersistTester")
            _check("persisted choices survive", len(loaded.choices) == 2,
                   f"got {len(loaded.choices)}")
            _check("persisted tapasya", loaded.tapasya.get("Shiva") is not None)
            _check("persisted lossless", loaded.to_dict() == sk.to_dict())
        # UPSERT
        sk.meditate("Vishnu", 1.0)
        persistence.save_seeker(SID, sk, user_id="unittest-user")
        reloaded = persistence.load_seeker(SID)
        _check("upsert reflects new tapasya",
               reloaded is not None and "Vishnu" in reloaded.tapasya)
        # delete + miss
        _check("delete removes row", persistence.delete_seeker(SID))
        _check("load after delete is None", persistence.load_seeker(SID) is None)
    else:
        # graceful no-DB contract: everything returns falsy, nothing raises
        _check("save returns False without DB",
               persistence.save_seeker(SID, sk) is False)
        _check("load returns None without DB",
               persistence.load_seeker(SID) is None)
        _check("delete returns False without DB",
               persistence.delete_seeker(SID) is False)
        print("  (no DB reachable — tested graceful-fallback contract only)")


def test_meditation_cap(mem: Memory):
    print("\n--- seeker.meditate (guna cap vs tapasya accumulation) ---")
    sk = seeker.SeekerState(name="Ascetic")
    sk.meditate("brahma", 60.0)
    # tapasya accumulates the FULL intensity (boon gating must still work)
    _check("tapasya accumulates full intensity",
           sk.tapasya["brahma"].accumulated == 60.0)
    # but a single session must NOT flatline the guna triple
    _check("single high-intensity meditation does not pin sattva",
           sk.guna.sattva < 0.55, f"sattva={sk.guna.sattva}")
    _check("rajas not annihilated by one session", sk.guna.rajas > 0.05)
    # sustained practice climbs higher than one big session
    sk2 = seeker.SeekerState(name="Devotee")
    for _ in range(10):
        sk2.meditate("shiva", 3.0)
    _check("sustained practice climbs sattva", sk2.guna.sattva > sk.guna.sattva)


def test_scene_assembly(mem: Memory):
    print("\n--- scene.assemble_scene ---")
    sk = seeker.SeekerState(name="Arjuna")
    sk.meditate("brahma", 60.0)
    sk.earn_boon("Brahmastra", "Drona", "mbh_01.123")
    sk.make_choice("test", "A fork", "focus", {"sattva": 0.05}, ["mastery"])

    # find a charted location to stand in
    locs = world.list_locations(mem)["data"]["locations"]
    loc_name = locs[0]["name"] if locs else "Kurukshetra"
    sk.move_to(loc_name)

    r = scene.assemble_scene(sk, mem)
    _check("scene envelope success", r["success"])
    d = r["data"]
    _check("scene has location", "location" in d)
    _check("scene has surroundings", "surroundings" in d)
    _check("scene has self", "self" in d)
    _check("scene has actions", "actions" in d)
    _check("scene self reflects boon", "Brahmastra" in d["self"]["boons"])
    _check("scene recent choices present", len(d["self"]["recent_choices"]) == 1)
    _check("scene actions has always-verbs",
           "meditate" in d["actions"]["always"])
    # Brahmastra should be combat-ready (60 tapasya > min 50)
    ready = [a["name"] for a in d["actions"]["combat_ready"]]
    _check("scene shows brahmastra ready", "Brahmastra" in ready,
           f"ready={ready}")

    # uncharted place => honest blank stage, still success
    r2 = scene.assemble_scene(sk, mem, location="Nowhere_Uncharted_XYZ")
    _check("uncharted scene still succeeds", r2["success"])
    _check("uncharted marked not charted", r2["data"]["charted"] is False)
    _check("uncharted has no npcs", r2["metadata"]["n_npcs"] == 0)

    # no location at all => honest failure
    empty = seeker.SeekerState(name="Lost")
    r3 = scene.assemble_scene(empty, mem)
    _check("no-location scene fails cleanly", not r3["success"])
    _check("no-location error code", r3["errors"][0]["code"] == "no_location")


def test_guna_normalization():
    print("\n--- guna normalization ---")
    g = seeker.GunaBalance(sattva=0.5, rajas=0.3, tamas=0.2)
    g.shift(ds=1.0)  # massive sattva boost
    total = g.sattva + g.rajas + g.tamas
    _check("guna sums to 1.0", abs(total - 1.0) < 0.001, f"got {total}")
    _check("sattva dominant after boost", g.dominant == "sattva")

    # all zeros edge case (shouldn't happen but be safe)
    g2 = seeker.GunaBalance(sattva=0.01, rajas=0.01, tamas=0.01)
    g2.shift(ds=-0.1, dr=-0.1, dt=-0.1)  # try to go negative
    _check("no negative gunas", g2.sattva > 0 and g2.rajas > 0 and g2.tamas > 0)
    total2 = g2.sattva + g2.rajas + g2.tamas
    _check("still sums to 1.0", abs(total2 - 1.0) < 0.001)


# === NARRATIVE TESTS ==========================================================

def test_narrative_events(mem: Memory):
    print("\n--- narrative.get_narrative_events ---")
    for text in ["bhagavata", "mahabharata", "ramayana"]:
        result = narrative.get_narrative_events(text, mem)
        if result["success"] and result["data"]["entities"]:
            _check(f"{text} has entities", len(result["data"]["entities"]) > 0)
            _check(f"{text} has events", isinstance(result["data"]["events"], list))
            break
    else:
        _check("at least one text has events", False, "no text matched")


def test_consequence_chain(mem: Memory):
    print("\n--- narrative.consequence_chain ---")
    for entity in ["Krishna", "Arjuna", "Rama"]:
        result = narrative.consequence_chain(entity, mem)
        if result["success"]:
            _check(f"{entity} consequence envelope", True)
            _check(f"{entity} has chain", isinstance(result["data"]["chain"], list))
            break


def test_nearby_locations(mem: Memory):
    print("\n--- world.nearby_locations ---")
    locs = world.list_locations(mem)["data"]["locations"]
    if locs:
        result = world.nearby_locations(locs[0]["name"], mem)
        _check("nearby envelope", result["success"])
        _check("nearby has origin", "origin" in result["data"])
        _check("nearby has reachable", isinstance(result["data"]["reachable"], list))
    result = world.nearby_locations("Nonexistent_XYZZY", mem)
    _check("nearby not found", not result["success"])


def test_character_journey(mem: Memory):
    print("\n--- world.character_journey ---")
    for name in ["Krishna", "Arjuna", "Rama", "Shiva"]:
        result = world.character_journey(name, mem)
        if result["success"]:
            _check(f"{name} journey envelope", True)
            _check(f"{name} journey has character", "character" in result["data"])
            _check(f"{name} journey has locations", isinstance(result["data"]["locations"], list))
            if result["data"]["locations"]:
                loc = result["data"]["locations"][0]
                _check(f"{name} journey loc has name", "name" in loc)
                _check(f"{name} journey loc has shared_chapters", "shared_chapters" in loc)
            break
    result = world.character_journey("Nonexistent_XYZZY", mem)
    _check("journey not found", not result["success"])


def test_dharmic_fork():
    print("\n--- narrative.dharmic_fork ---")
    result = narrative.dharmic_fork("The dice game", [
        {"label": "Intervene", "guna_shift": {"sattva": 0.05, "rajas": 0.03}},
        {"label": "Stay silent", "guna_shift": {"tamas": 0.05}},
    ])
    _check("fork envelope", result["success"])
    _check("fork has options", result["data"]["n_options"] == 2)

    # too few options
    result = narrative.dharmic_fork("Test", [{"label": "Only one"}])
    _check("too few options fails", not result["success"])


# === RUN ======================================================================

def main():
    global _passed, _failed
    print("=== Narrative Engine Tests ===\n")
    print(f"Graph: {_GRAPH}")
    print(f"RAM:   {_RAM}")

    mem = _load_memory()
    print(f"\nLoaded: {len(mem.entities)} entities, {len(mem.edges)} edges, "
          f"{len(mem.keys)} decode keys\n")

    # world
    test_list_locations(mem)
    test_location_detail(mem)
    test_location_not_found(mem)

    # character
    test_character_sheet(mem)
    test_character_abilities(mem)
    test_character_not_found(mem)
    test_character_relationships(mem)

    # combat (some don't need memory)
    test_astra_rules()
    test_astra_unknown()
    test_resolve_attack(mem)
    test_astra_grounding(mem)
    test_encounter(mem)

    # seeker (pure state, no memory needed)
    test_seeker_state()
    test_guna_normalization()
    test_karma_chain()
    test_meditation_cap(mem)
    test_scene_assembly(mem)
    test_persistence()

    # world (extended)
    test_nearby_locations(mem)
    test_character_journey(mem)

    # narrative
    test_narrative_events(mem)
    test_consequence_chain(mem)
    test_dharmic_fork()

    print(f"\n{'='*40}")
    print(f"  {_passed} passed, {_failed} failed")
    print(f"{'='*40}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
