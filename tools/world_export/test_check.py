"""Tests for world_export — locked against the REAL 8755-entity graph.

Run (from purangpt/ repo root):
  venv/bin/python -m tools.world_export.test_check

These assert real-graph-in -> Unreal-world-JSON-out: the envelope shape, the
exact data schema build_ayodhya_level.py consumes, graph-grounded cast
assembly (Ayodhya's full Ramayana cast reconstructed from one resident),
deterministic placement, and the failure envelopes. The graph is loaded ONCE
and shared so the suite stays fast.
"""
import json
import os
import tempfile

from tools.world_export.check import (
    run, _DEFAULT_AESTHETIC, _GRAPH_PATH, _RAM_PATH, _skyline, _place,
    _NON_CHARACTER_KINDS, _is_character,
)
from tools.read_pass.recall import Memory

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
WORLD_KEYS = {"location", "aesthetic", "skyline", "npcs", "n_entities"}
NPC_KEYS = {"name", "kind", "chapters", "x", "y", "brief", "weapons", "family"}

# load the real graph once; reuse across every test
_MEM = Memory.load(_GRAPH_PATH, _RAM_PATH)


def test_envelope_and_world_schema():
    env = run("Ayodhya", memory=_MEM)
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True, env["errors"]
    assert env["errors"] == []
    assert set(env["data"].keys()) == WORLD_KEYS, env["data"].keys()
    for npc in env["data"]["npcs"]:
        assert set(npc.keys()) == NPC_KEYS, npc.keys()
    print("ok: envelope_and_world_schema")


def test_n_entities_is_full_graph():
    env = run("Ayodhya", memory=_MEM)
    # the moat: the export carries the real graph scale
    assert env["data"]["n_entities"] == len(_MEM.entities)
    assert env["data"]["n_entities"] > 8000, env["data"]["n_entities"]
    print("ok: n_entities_is_full_graph =", env["data"]["n_entities"])


def test_cast_reconstructed_from_one_resident():
    # Ayodhya has a SINGLE direct resident (Dasharatha) in the graph; the BFS
    # over family/guru edges must rebuild the dramatis personae around him.
    env = run("Ayodhya", cap=8, hops=2, memory=_MEM)
    names = [n["name"] for n in env["data"]["npcs"]]
    assert "Dasharatha" in names, names
    assert "Rama" in names, names           # reachable + most prominent
    assert len(names) > 1, "cast did not expand beyond the lone resident"
    print("ok: cast_reconstructed ->", names)


def test_cast_is_locally_relevant_not_globally_famous():
    # The semantic guard: global prominence pulled Indra (791ch, divine ancestor)
    # and Shakuni (a Mahabharata villain via a bridge edge) into Ayodhya and put
    # Indra front-and-centre. Local-relevance ranking must keep them OUT and put
    # an Ayodhya figure on the throne. (Locked regression — see FINDINGS.md.)
    env = run("Ayodhya", cap=8, hops=2, memory=_MEM)
    names = [n["name"] for n in env["data"]["npcs"]]
    assert "Indra" not in names, f"Indra (global, not Ayodhyan) leaked in: {names}"
    assert "Shakuni" not in names, f"Shakuni (wrong epic) leaked in: {names}"
    # front-and-centre at (600,0) is an Ayodhya royal, not a corpus-wide deity
    front = env["data"]["npcs"][0]
    assert front["x"] == 600.0 and front["y"] == 0.0, front
    assert front["name"] in {"Rama", "Dasharatha"}, front["name"]
    print("ok: cast_locally_relevant -> front:", front["name"], "|", names)


def test_tangential_resident_does_not_import_its_whole_epic():
    # Govardhana's ONLY graph tie is a single Brahmanda-Purana verse saying Rama
    # "built" it (bndp_1,16.44). The old anchor unioned that lone resident's FULL
    # chapter history, so Rama dragged his entire Ayodhya household — Sita,
    # Lakshmana, Bharata, Kaikeyi, Shatrughna, none of whom touch Govardhana — in
    # as its "cast." Confidently wrong: the wrong epic, in the wrong place. The
    # fix anchors relevance on the LOCATION's OWN chapters, so non-local kin fall
    # below the cap. Rama himself MAY remain (he is the graph-attested resident);
    # his household must NOT. (Locked regression — see FINDINGS.md.)
    env = run("Govardhana", cap=8, hops=2, memory=_MEM)
    assert env["success"] is True, env
    names = [n["name"] for n in env["data"]["npcs"]]
    for ghost in ("Sita", "Lakshmana", "Bharata", "Kaikeyi", "Shatrughna",
                  "Dasharatha", "Daśaratha"):
        assert ghost not in names, f"Rama's household imported into Govardhana: {names}"
    print("ok: tangential_resident_no_epic_import ->", names)


def test_seeded_cast_overrides_residents():
    # Govardhana's place-resident BFS defaults to the WRONG (Ramayana) cast — Rama
    # and his household — because its only graph tie is a single "Rama built it"
    # verse. A Sharma-biography level wants its OWN dramatis personae instead. The
    # `seeds` override must replace the place-resident roots wholesale: with
    # ["Mahavatar Babaji"] as the seed, the cast is Babaji's ego-network, NOT
    # Ayodhya royalty. (Locked — design world_level_design.md §0/§7.)
    env = run("Govardhan", seeds=["Mahavatar Babaji"], cap=8, hops=2, memory=_MEM)
    assert env["success"] is True, env
    names = [n["name"] for n in env["data"]["npcs"]]
    assert "Mahavatar Babaji" in names, f"seed not in cast: {names}"
    assert "Rama" not in names, f"Ramayana default beat the seed: {names}"
    assert "Sita" not in names, f"Ramayana default beat the seed: {names}"
    print("ok: seeded_cast_overrides_residents ->", names)


def test_not_found_location_with_seeds_still_builds():
    # "Mahurgad" is a Sharma-biography place that does NOT exist as a graph entity
    # (location_detail → not_found). Without seeds that's a clean failure; WITH
    # seeds the place is just a label and the cast is 100% the seeds' world, so it
    # must still produce a buildable level JSON. (Locked — world_level_design.md §7.)
    env = run("Mahurgad", seeds=["Matsyendranatha", "Dattatreya"],
              cap=8, hops=2, memory=_MEM)
    assert env["success"] is True, env
    assert env["data"]["location"], "no location label emitted"
    assert env["data"]["skyline"], "no skyline emitted for non-graph place"
    names = [n["name"] for n in env["data"]["npcs"]]
    assert len(names) > 0, "seed-derived cast is empty"
    assert any(s in names for s in ("Matsyendranatha", "Dattatreya")), names
    print("ok: not_found_location_with_seeds_still_builds ->",
          env["data"]["location"], "|", names)


def test_non_character_entities_excluded_from_cast():
    # The biography decode emits non-being entities — a PRACTICE ("Kriya Yoga"),
    # a CONCEPT ("constable"), a TEXT ("Ramayana") — that the BFS happily pulls in
    # as "cast" because they sit on a being's edges. They can't stand in a level as
    # NPCs. The kind-denylist must drop them BEFORE the cap, so real beings refill
    # the freed slots. Seeded on the Sharma line, Kriya Yoga/constable must be gone
    # while the sages remain. (Locked regression — see FINDINGS.md Bug 3.)
    env = run("Mahurgad", seeds=["Shailendra Sharma", "Babaji", "Satyacharan Lahiri"],
              cap=8, hops=1, memory=_MEM)
    assert env["success"] is True, env
    names = [n["name"] for n in env["data"]["npcs"]]
    assert "Kriya Yoga" not in names, f"a practice leaked in as an NPC: {names}"
    assert "constable" not in names, f"a concept leaked in as an NPC: {names}"
    assert "Shailendra Sharma" in names, f"the seed sage dropped: {names}"
    assert "Babaji" in names, f"the seed sage dropped: {names}"
    print("ok: non_character_entities_excluded ->", names)


def test_no_npc_has_a_non_character_kind():
    # The strong invariant across both a Puranic court, the tangential-resident
    # place that used to surface "Ramayana" (a text), and a seeded biography level:
    # EVERY emitted NPC carries a character kind, never one of the denylisted
    # non-being kinds (text/concept/practice/place/...). (Locked — FINDINGS.md Bug 3.)
    builds = [
        run("Ayodhya", memory=_MEM),
        run("Govardhana", memory=_MEM),
        run("Mahurgad", seeds=["Shailendra Sharma", "Babaji"], memory=_MEM),
    ]
    for env in builds:
        assert env["success"] is True, env
        for npc in env["data"]["npcs"]:
            assert npc["kind"] not in _NON_CHARACTER_KINDS, \
                f"non-character NPC emitted: {npc['name']} (kind={npc['kind']})"
    # the specific logged residual: "Ramayana" (a text) no longer an Ayodhya/Govardhana NPC
    gov_names = [n["name"] for n in builds[1]["data"]["npcs"]]
    assert "Ramayana" not in gov_names, f"the text 'Ramayana' is still an NPC: {gov_names}"
    print("ok: no_npc_has_a_non_character_kind (Ramayana gone from Govardhana)")


def test_narratological_artifacts_excluded_from_cast():
    # "Narrator" is mis-typed kind='sage' in the graph, so the kind denylist alone
    # would let it stand in as an NPC. The artifact-NAME filter must catch it.
    assert _is_character("Narrator", _MEM) is False, "'Narrator' leaked as a character"
    assert _is_character("Speaker", _MEM) is False, "'Speaker' leaked as a character"
    # a real being with the same kind must still pass
    assert _is_character("Vyasa", _MEM) is True, "real sage 'Vyasa' wrongly excluded"
    print("ok: narratological_artifacts_excluded_from_cast")


def test_npc_enrichment_is_graph_true():
    env = run("Ayodhya", memory=_MEM)
    rama = next((n for n in env["data"]["npcs"] if n["name"] == "Rama"), None)
    assert rama is not None
    assert rama["brief"], "Rama has no literal brief"
    assert "Brahma" in rama["weapons"], rama["weapons"]
    # family formatted exactly as the shipped JSON: "Name (relationship)"
    assert any("(" in f and f.endswith(")") for f in rama["family"]), rama["family"]
    assert any("Sita" in f for f in rama["family"]), rama["family"]
    print("ok: npc_enrichment ->", rama["weapons"], rama["family"][:3])


def test_cap_respected():
    env = run("Ayodhya", cap=3, hops=2, memory=_MEM)
    assert len(env["data"]["npcs"]) == 3, len(env["data"]["npcs"])
    print("ok: cap_respected")


def test_deterministic():
    a = run("Ayodhya", memory=_MEM)["data"]
    b = run("Ayodhya", memory=_MEM)["data"]
    assert a == b, "export is not deterministic"
    print("ok: deterministic")


def test_aesthetic_default_and_override():
    env = run("Ayodhya", memory=_MEM)
    assert env["data"]["aesthetic"] == _DEFAULT_AESTHETIC
    custom = {"key_light_color": [0.3, 0.3, 0.5], "note": "the smashan at night"}
    env2 = run("Ayodhya", aesthetic=custom, memory=_MEM)
    assert env2["data"]["aesthetic"] == custom
    print("ok: aesthetic_default_and_override")


def test_skyline_is_deterministic_and_shaped():
    sk = _skyline()
    assert len(sk) == 5
    assert all(len(row) == 4 for row in sk), sk
    # centre tower is the tallest (crests toward the great temple)
    heights = [row[3] for row in sk]
    assert heights[2] == max(heights), heights
    print("ok: skyline shaped")


def test_unknown_location_fails_cleanly():
    env = run("Nowhereville-Not-In-Corpus", memory=_MEM)
    assert env["success"] is False
    assert env["data"] is None
    assert env["errors"] and "code" in env["errors"][0], env["errors"]
    print("ok: unknown_location_fails ->", env["errors"][0]["code"])


def test_empty_name_fails_cleanly():
    env = run("   ", memory=_MEM)
    assert env["success"] is False
    assert env["errors"][0]["code"] == "empty_name", env["errors"]
    print("ok: empty_name_fails")


def test_write_to_disk_roundtrips():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "sub", "test_world.json")
        env = run("Ayodhya", write_to=path, memory=_MEM)
        assert env["success"] and os.path.exists(path)
        on_disk = json.load(open(path, encoding="utf-8"))
        assert on_disk == env["data"]
        assert env["metadata"]["written_to"] == path
    print("ok: write_to_disk_roundtrips")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nALL TESTS PASSED")
