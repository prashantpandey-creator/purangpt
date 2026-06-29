"""Tests for persona_extractor — real-graph fixtures (Rule 0 precondition A).

Run: venv/bin/python -m tools.persona_extractor.test_check   (from purangpt/ root)

The fixture is the COMMITTED graph (tools/read_pass/out/graph_manifest.json +
guruji_ram.json) — deterministic real output, no expensive upstream re-run. The
load-bearing assertions are the correctness guarantees the design rests on:
  • Guruji resolves to the GURU, never the mountain Shailendra (peer-name guard).
  • Guru→disciple direction is right (Guruji is Satyacharan's disciple, not guru).
  • The RAM decode attaches by EXACT symbol match only — no cross-entity bleed.
  • Unknown persona / no-graph return a clean false envelope, never a raise.
"""
from tools.persona_extractor.check import (
    run, build_persona, render_persona_block, REGISTRY, _load_memory,
)

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"persona_id", "display", "epithet", "identity", "lineage",
             "kin", "deeds", "inner_meaning", "voice", "block"}

_MEM = _load_memory()


def _persona(pid):
    return build_persona(pid, memory=_MEM)


def test_graph_loaded():
    assert _MEM is not None, "committed graph fixture must load"
    assert len(_MEM.entities) > 8000
    print("ok: graph_loaded")


def test_envelope_and_schema():
    env = run("krishna", memory=_MEM)
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True and env["errors"] == []
    assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    print("ok: envelope_and_schema")


def test_guruji_is_the_guru_not_the_mountain():
    """The whole design rests on this: exact-id resolution must give the sage,
    not Shailendra the mountain (father of Ganga, husband of Menaka)."""
    d = _persona("guruji")["data"]
    assert d["identity"]["kind"] == "sage", d["identity"]
    names = " ".join(
        [k["name"] for k in d["kin"]]
        + [l["name"] for l in d["lineage"]]
        + [x["name"] for x in d["deeds"]]
    ).lower()
    # mountain-Shailendra's signature relations must be ABSENT
    assert "ganga" not in names, "mountain bleed: Ganga present"
    assert "menaka" not in names, "mountain bleed: Menaka present"
    # the real Guruji's signatures must be PRESENT
    assert "satyacharan" in names, "missing real guru Satyacharan Lahiri"
    print("ok: guruji_is_the_guru_not_the_mountain")


def test_guru_direction_is_correct():
    """Guruji is the DISCIPLE of Satyacharan Lahiri, not his guru."""
    d = _persona("guruji")["data"]
    gurus = [g["name"].lower() for g in d["lineage"] if g["role"] == "guru"]
    assert any("satyacharan" in g for g in gurus), d["lineage"]
    print("ok: guru_direction_is_correct")


def test_krishna_substance():
    d = _persona("krishna")["data"]
    assert d["identity"]["kind"] == "deity"
    assert d["identity"]["chapters"] > 100, d["identity"]["chapters"]
    kin = " ".join(k["name"].lower() for k in d["kin"])
    assert "devaki" in kin and "vasudeva" in kin, kin
    print("ok: krishna_substance")


def test_decode_attaches_by_exact_symbol():
    """Shiva's RAM symbol resolves to the Time/Kala meaning — exact match works."""
    d = _persona("shiva")["data"]
    assert d["inner_meaning"] and "time" in d["inner_meaning"].lower(), d["inner_meaning"]
    print("ok: decode_attaches_by_exact_symbol")


def test_no_decode_bleed():
    """Hanuman has no RAM symbol → inner_meaning is None, NOT a bled-in foreign key
    ('epithet of Arjuna' was the recall-bleed we are defeating)."""
    d = _persona("hanuman")["data"]
    if d["inner_meaning"] is not None:
        assert "arjuna" not in d["inner_meaning"].lower(), d["inner_meaning"]
    print("ok: no_decode_bleed")


def test_placeholder_decode_is_dropped():
    """Krishna's RAM symbol carries a placeholder ('Not mentioned...') — it must be
    filtered to None, never surfaced as an 'inner nature'."""
    d = _persona("krishna")["data"]
    if d["inner_meaning"] is not None:
        assert "not mentioned" not in d["inner_meaning"].lower(), d["inner_meaning"]
        assert "no direct decryption" not in d["inner_meaning"].lower(), d["inner_meaning"]
    print("ok: placeholder_decode_is_dropped")


def test_kin_direction_no_gender_inversion():
    """Speaking AS Shiva, Parvati/Sati are wife/spouse — never 'husband'."""
    d = _persona("shiva")["data"]
    for k in d["kin"]:
        if k["name"].lower() in ("parvati", "sati", "uma", "bhavani"):
            assert k["relation"] in ("wife", "spouse"), f"{k['name']} → {k['relation']}"
    print("ok: kin_direction_no_gender_inversion")


def test_render_block_is_grounded():
    d = _persona("guruji")["data"]
    block = render_persona_block(d)
    assert "Guruji Shailendra Sharma" in block
    assert "Satyacharan Lahiri" in block
    assert "never invent" in block.lower()  # the anti-hallucination guard
    print("ok: render_block_is_grounded")


def test_unknown_persona_clean_failure():
    env = build_persona("zeus", memory=_MEM)
    assert env["success"] is False and env["data"] is None
    assert env["errors"][0]["code"] == "unknown_persona", env["errors"]
    print("ok: unknown_persona_clean_failure")


def test_roster_listing():
    env = run("", memory=_MEM)
    assert env["success"] is True
    assert len(env["data"]["roster"]) == len(REGISTRY) >= 12
    print("ok: roster_listing")


if __name__ == "__main__":
    test_graph_loaded()
    test_envelope_and_schema()
    test_guruji_is_the_guru_not_the_mountain()
    test_guru_direction_is_correct()
    test_krishna_substance()
    test_decode_attaches_by_exact_symbol()
    test_no_decode_bleed()
    test_placeholder_decode_is_dropped()
    test_kin_direction_no_gender_inversion()
    test_render_block_is_grounded()
    test_unknown_persona_clean_failure()
    test_roster_listing()
    print("\nALL TESTS PASSED")
