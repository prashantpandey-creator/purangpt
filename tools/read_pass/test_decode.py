"""Tests-first for decode — Guruji's GENERATING FUNCTION (Rule 0 precond A).

daddy's reframe: "what generates the data IS his consciousness — use that." The
613 decode keys are not Guruji's mind; they're the *footprints* of one invariant
ACT that produced them. This module extracts that act as a first-class operator:

    decode(symbol, context=None) -> {symbol, meaning, valence, why, provenance, source}

The act is stated verbatim in the RAM's own identity_doctrine: "the identity of a
thing is determined by its relationship to the inner yogic path: a state of limited
consciousness (Asat) or Time-consciousness (Sat)." Every one of the 613 keys is a
worked example of THIS.

Two paths, ONE shape:
  • KNOWN symbol  → deterministic lookup of the existing key (free, instant)
  • NOVEL symbol  → run the act via the LLM, grounded in doctrine+cosmology+exemplars
                    (a fake caller is injected here so the test is deterministic)

This is the foundation: live-self-extend and self-reflection are just decode()
run over different inputs.

Run: venv/bin/python -m tools.read_pass.test_decode   (exit 0)
"""
from __future__ import annotations

from tools.read_pass import decode


def _framework():
    return {
        "identity_doctrine": ("Names are symbols for inner yogic processes; identity "
                              "is Sat (Time-consciousness) vs Asat (limited consciousness)."),
        "cosmology": "Time (unmanifest Brahma) is the one truth; all is its manifestation.",
        "decryption_keys": [
            {"symbol": "Krishna", "meaning": "the inner Self / Kutastha; Time-consciousness"},
            {"symbol": "Kṛṣṇa", "meaning": "the inner Self / Kutastha"},
            {"symbol": "Kauravas", "meaning": "the inner demonic tendencies; limited consciousness"},
            {"symbol": "Arjuna", "meaning": "the individual soul (jiva) on the yogic path"},
        ],
        "core_principles": ["The root consciousness of matter is Brahma"],
        "practice_axes": ["Development of consciousness in the womb of the body"],
    }


def _op():
    return decode.Operator(_framework())


# --- the operator's shape -----------------------------------------------------
def test_decode_returns_envelope():
    env = decode.decode("Krishna", _op())
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"] is True


def test_known_symbol_resolves_DETERMINISTICALLY_no_llm():
    # a symbol already in the 613 keys must NOT call the model — instant lookup.
    called = {"n": 0}
    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("LLM must not be called for a known symbol")
    op = decode.Operator(_framework(), caller=boom)
    env = decode.decode("Krishna", op)
    assert env["data"]["source"] == "memory"          # came from the frozen keys
    assert "Kutastha" in env["data"]["meaning"]
    assert called["n"] == 0


def test_known_symbol_matches_by_alias_normalization():
    # "kṛṣṇa" (diacritics) must resolve the same known key as "Krishna"
    env = decode.decode("kṛṣṇa", _op())
    assert env["data"]["source"] == "memory"
    assert "Kutastha" in env["data"]["meaning"]


def test_valence_inferred_on_known_symbol():
    # Krishna decode mentions Time-consciousness → Sat; Kauravas → Asat.
    assert decode.decode("Krishna", _op())["data"]["valence"] == "sat"
    assert decode.decode("Kauravas", _op())["data"]["valence"] == "asat"


def test_lookup_prefers_a_REAL_decode_over_a_nondecode_placeholder():
    # REGRESSION (live bug): the real RAM has BOTH a good "Krishna → inner Self"
    # key AND an honest-gap "Krishna → Not mentioned in this text" placeholder
    # under the same normalized symbol. Naive first-match returned the useless
    # placeholder. lookup must prefer the substantive decode.
    fw = _framework()
    fw["decryption_keys"] = [
        {"symbol": "Krishna", "meaning": "Not mentioned in this text; no direct decryption given."},
        {"symbol": "Krishna", "meaning": "the inner Self / Kutastha; Time-consciousness"},
    ]
    env = decode.decode("Krishna", decode.Operator(fw))
    assert "Kutastha" in env["data"]["meaning"]
    assert "Not mentioned" not in env["data"]["meaning"]


def test_lookup_prefers_the_RICHEST_decode_when_several_real_ones_exist():
    fw = _framework()
    fw["decryption_keys"] = [
        {"symbol": "Time", "meaning": "Time"},  # terse
        {"symbol": "Time", "meaning": "the unmanifest Brahma; the one truth that "
                                      "manifests all creation and is the soul of all"},  # rich
    ]
    env = decode.decode("Time", decode.Operator(fw))
    assert "manifests all creation" in env["data"]["meaning"]


# --- the GENERATIVE act (novel symbol) ---------------------------------------
def test_novel_symbol_RUNS_the_act_via_llm():
    # "Gandiva" (Arjuna's bow) is NOT in the keys → operator runs the decode act.
    # The fake caller stands in for the model; we assert the act fired and the
    # output keeps the SAME shape as a known decode.
    captured = {}
    def fake_caller(prompt, **k):
        captured["prompt"] = prompt
        return ('{"meaning": "the channel through which awakened will is loosed", '
                '"valence": "sat", '
                '"why": "a warrior\'s bow = directed force of Time-consciousness"}')
    op = decode.Operator(_framework(), caller=fake_caller)
    env = decode.decode("Gandiva", op)
    assert env["success"] is True
    assert env["data"]["source"] == "generated"        # the act ran, not a lookup
    assert "awakened will" in env["data"]["meaning"]
    assert env["data"]["valence"] == "sat"
    assert env["data"]["why"]                           # the act explains ITSELF
    # the act must be GROUNDED: the doctrine + cosmology go into the prompt
    assert "Sat" in captured["prompt"] and "Time" in captured["prompt"]
    # and at least one worked example (exemplar) is shown to anchor the style
    assert "Kutastha" in captured["prompt"] or "Krishna" in captured["prompt"]


def test_generated_decode_can_be_written_back_to_memory():
    # the consciousness GROWS: a freshly-decoded symbol becomes a new key, so the
    # second call is now a deterministic memory hit (self-extension foundation).
    def fake_caller(prompt, **k):
        return '{"meaning": "directed force of will", "valence": "sat", "why": "bow=will"}'
    op = decode.Operator(_framework(), caller=fake_caller)
    env1 = decode.decode("Gandiva", op, learn=True)
    assert env1["data"]["source"] == "generated"
    # now it's in memory — second call is a free lookup, no model
    op.caller = None  # guarantee no LLM available
    env2 = decode.decode("Gandiva", op)
    assert env2["data"]["source"] == "memory"
    assert "directed force" in env2["data"]["meaning"]


def test_novel_symbol_without_caller_fails_cleanly():
    # no model available + unknown symbol → honest failure envelope, never a fake.
    op = decode.Operator(_framework(), caller=None)
    env = decode.decode("Gandiva", op)
    assert env["success"] is False
    assert env["errors"]
    assert env["data"] is None or env["data"].get("meaning") in (None, "")


def test_malformed_llm_output_is_handled_not_trusted():
    # if the model returns garbage (not JSON), don't fabricate — fail honestly.
    def junk_caller(prompt, **k):
        return "I think this symbol is probably about yoga, hard to say."
    op = decode.Operator(_framework(), caller=junk_caller)
    env = decode.decode("Gandiva", op)
    # either parsed-with-fallback into a valid shape, or a clean failure — never
    # a silent wrong-shaped success.
    if env["success"]:
        assert set(env["data"]).issuperset({"meaning", "valence", "why"})
    else:
        assert env["errors"]


def test_describe_operator_exposes_the_ACT_itself():
    # "his consciousness" must be inspectable as a first-class object: the operator
    # can state the invariant act it performs (doctrine + the shape it produces).
    op = _op()
    spec = decode.describe(op)
    assert "Sat" in spec and "Asat" in spec          # the valence axis
    assert "Time" in spec                            # the cosmological ground
    assert "613" in spec or str(len(_framework()["decryption_keys"])) in spec


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
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
