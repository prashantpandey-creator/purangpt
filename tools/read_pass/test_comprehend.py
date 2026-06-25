"""Tests for the comprehension pipeline's deterministic parts (Rule 0 precond A).

The Gemini call is injected as a fake `caller`, so these run offline and lock
the lens-selection / prompt-assembly / parsing / validation / error-envelope
logic. Run: venv/bin/python -m tools.read_pass.test_comprehend  (exit 0).
"""
from __future__ import annotations
import json

from tools.read_pass import comprehend, schema

# A minimal valid record the fake Gemini "returns".
_GOOD = {
    "chapter_summary": "Suta narrates the Bhagavata to the sages.",
    "entities": [
        {"name": "Suta", "kind": "sage", "verse_ranges": ["1"]},
        {"name": "Krishna", "kind": "deity", "aliases": ["Vishnu"], "verse_ranges": ["3"]},
    ],
    "relationships": [
        {"src": "Suta", "rel": "narrates_to", "dst": "sages", "verse_ranges": ["1"]},
    ],
    "story": {"title": "The Gathering at Naimisaranya",
              "arc": "Sages assemble; Suta begins the recitation.",
              "characters": ["Suta"], "comic_potential": "strong framing scene"},
    "teachings": [
        {"teaching": "Devotion uproots the threefold suffering.",
         "lens_note": "bhakti as kriya in Sharma's frame", "verse_ranges": ["2"]},
    ],
}

_WINDOW = {
    "purana": "Bhagavata Purana", "chapter_label": "Chapter 1",
    "seq_start": 1, "seq_end": 34,
    "chunk_ids": ["bhagavata-1-1", "bhagavata-1-2"],
    "text": "krishna yoga atman ... bhp_01.01.001 ... arjuna meditation self",
}


def test_schema_validate_accepts_good_and_rejects_missing_provenance():
    assert schema.validate(_GOOD) == []
    bad = json.loads(json.dumps(_GOOD))
    del bad["entities"][0]["verse_ranges"]
    probs = schema.validate(bad)
    assert any("verse_ranges" in p for p in probs), probs


def test_select_lens_applies_on_yoga_vocab_and_skips_otherwise():
    lens = [{"text": "Commentary: yoga is the stilling of the mind. " * 20}]
    applied = comprehend.select_lens(_WINDOW, lens)
    assert applied and "yoga" in applied.lower()
    dry = {"chapter_label": "geography", "text": "a list of rivers and mountains"}
    assert comprehend.select_lens(dry, lens) == ""


def test_select_lens_empty_when_no_books():
    assert comprehend.select_lens(_WINDOW, []) == ""


def test_select_lens_matches_diacritic_sanskrit():
    # the source is transliterated WITH diacritics; the lens must still fire.
    # 'kṛṣṇa' / 'ātman' must match even though signals are ASCII.
    lens = [{"text": "Commentary on the Self. " * 20}]
    diacritic_window = {"chapter_label": "Chapter 1",
                        "text": "dharmaḳsetre kṛṣṇaḥ ātman bhagavān vāsudeva " * 5}
    applied = comprehend.select_lens(diacritic_window, lens)
    assert applied, "lens must fire on diacritic Sanskrit (krsna/atman/bhagavan)"


def test_build_prompt_includes_lens_block_and_text():
    p = comprehend.build_prompt(_WINDOW, "SHARMA-LENS-TEXT")
    assert "SHARMA-LENS-TEXT" in p
    assert "bhp_01.01.001" in p
    p2 = comprehend.build_prompt(_WINDOW, "")
    assert "No specific lens" in p2


def test_parse_response_handles_fenced_json():
    assert comprehend.parse_response('```json\n{"a":1}\n```') == {"a": 1}
    assert comprehend.parse_response('{"a":2}') == {"a": 2}


def test_parse_response_salvages_truncated_json():
    # DeepSeek truncates dense-genealogy chapters mid-array. The salvage must
    # recover the complete entities/relationships emitted before the cutoff
    # rather than throwing the whole chapter away.
    truncated = (
        '{"chapter_summary": "x", "entities": ['
        '{"name": "Vyasa", "kind": "sage", "verse_ranges": ["1"]}, '
        '{"name": "Shuka", "kind": "sage", "verse_ranges": ["2"]}, '
        '{"name": "Pari'  # <-- cut off mid-object
    )
    rec = comprehend.parse_response(truncated)
    # the two COMPLETE entities survive; the half-written one is dropped
    names = [e["name"] for e in rec.get("entities", [])]
    assert "Vyasa" in names and "Shuka" in names, names
    assert "Pari" not in names


def test_comprehend_window_success_stamps_provenance():
    def fake(prompt, model, key):
        return json.dumps(_GOOD)
    env = comprehend.comprehend_window(_WINDOW, [], "fake-key", caller=fake,
                                       provider="deepseek", model="deepseek-chat")
    assert env["success"] is True, env["errors"]
    prov = env["data"]["_provenance"]
    assert prov["chunk_ids"] == _WINDOW["chunk_ids"]
    # provider/model stamp makes each record auditable
    assert prov["provider"] == "deepseek"
    assert prov["model"] == "deepseek-chat"
    assert "lens_applied" in prov and "salvaged" in prov
    assert env["metadata"]["lens_applied"] is False  # no lens books passed


def test_comprehend_window_bad_json_returns_false_envelope():
    env = comprehend.comprehend_window(_WINDOW, [], "k",
                                       caller=lambda *a: "not json {")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "bad_json"


def test_comprehend_window_backfills_missing_optional_keys():
    # a record missing only optional content keys is now SALVAGED (backfilled),
    # not rejected — partial comprehension still lands.
    incomplete = {"chapter_summary": "x"}
    env = comprehend.comprehend_window(_WINDOW, [], "k",
                                       caller=lambda *a: json.dumps(incomplete))
    assert env["success"] is True, env["errors"]
    assert env["data"]["entities"] == []
    assert env["data"]["story"]["arc"]  # backfilled from summary


def test_comprehend_window_prunes_invalid_node_and_keeps_good_ones():
    # one good entity + one malformed (no verse_ranges). The malformed node is
    # PRUNED and the chapter still lands with the good node — this is how the
    # dense-genealogy truncation chapters get salvaged instead of dropped.
    mixed = {"chapter_summary": "x",
             "entities": [{"name": "Real", "kind": "sage", "verse_ranges": ["1"]},
                          {"name": "Ghost"}],  # malformed: no verse_ranges
             "relationships": [], "teachings": [],
             "story": {"title": "t", "arc": "a"}}
    env = comprehend.comprehend_window(_WINDOW, [], "k",
                                       caller=lambda *a: json.dumps(mixed))
    assert env["success"] is True, env["errors"]
    names = [e["name"] for e in env["data"]["entities"]]
    assert names == ["Real"], names
    assert env["metadata"].get("pruned_invalid_nodes") is True


def test_comprehend_window_call_failure_caught():
    def boom(*a):
        raise RuntimeError("network down")
    env = comprehend.comprehend_window(_WINDOW, [], "k", caller=boom)
    assert env["success"] is False
    assert env["errors"][0]["code"] == "call_failed"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
