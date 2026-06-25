"""Tests for creator_identity — written FIRST (Rule 0 precondition A), before run().

Run: venv/bin/python -m tools.creator_identity.test_check   (from purangpt/ repo root)

The contract under test:
  run(query: str) -> {success, data:{triggered:bool, directive:str}, metadata, errors}

  - triggered=True ONLY for questions about the app's creator (Prashant Pandey or an
    explicit "who made/built/created this app" phrase).
  - triggered=False (directive=="") for EVERYTHING else — especially deity/guru
    "who is X" questions and the prashanti/prakriti near-misses. directive=="" must
    mean main.py injects nothing → byte-identical prompt.
  - The directive, when present, must name Prashant as the disciple, carry the
    keyword facts, and instruct the model to stay in Guruji's voice.
"""
from tools.creator_identity.check import run

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"triggered", "directive"}


# ── Cases that MUST trigger (creator questions) ─────────────────────────────
TRIGGER_CASES = [
    "who is prashant pandey",
    "Who is Prashant Pandey?",
    "who is prashant",
    "tell me about prashant pandey",
    "who made this app",
    "who created this app",
    "who built purangpt",
    "who developed this",
    "who is the creator of this app",
    "who is the developer of purangpt",
    "who is the founder of this app",
    "who made you",                       # "you" = the app, in the creator sense
    "whos prashan pandey",                # typo the user themselves produced
    "who is prashanth pandey",            # spelling variant
]

# ── Cases that MUST NOT trigger ─────────────────────────────────────────────
NON_TRIGGER_CASES = [
    "who is Krishna",                     # deity — exclusion guard
    "who is Shiva",
    "who is Vyasa",
    "who is Rama",
    "who is your guru",                   # guru, not creator
    "who is Shailendra Sharma",           # Guruji himself, not Prashant
    "who is shailendra",
    "who are you",                        # the persona, not the creator
    "what is prakriti",                   # near-miss on 'prashant'
    "tell me about prashanti",            # the Linga-Purana yogic state — near-miss
    "what is prashna",                    # near-miss
    "how do I still my mind",             # ordinary spiritual question
    "what is ojas",
    "explain karma yoga",
]


def test_envelope_shape():
    env = run("who is prashant pandey")
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True, env
    assert env["errors"] == [], env["errors"]
    assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    assert isinstance(env["data"]["triggered"], bool)
    assert isinstance(env["data"]["directive"], str)
    print("ok: envelope_shape")


def test_all_trigger_cases():
    for q in TRIGGER_CASES:
        env = run(q)
        assert env["success"] is True, (q, env)
        assert env["data"]["triggered"] is True, f"should TRIGGER: {q!r}"
        assert env["data"]["directive"].strip(), f"triggered but empty directive: {q!r}"
    print(f"ok: all_trigger_cases ({len(TRIGGER_CASES)})")


def test_all_non_trigger_cases():
    for q in NON_TRIGGER_CASES:
        env = run(q)
        assert env["success"] is True, (q, env)
        assert env["data"]["triggered"] is False, f"should NOT trigger: {q!r}"
        assert env["data"]["directive"] == "", f"non-trigger must give empty directive: {q!r}"
    print(f"ok: all_non_trigger_cases ({len(NON_TRIGGER_CASES)})")


def test_directive_content():
    """When triggered, the directive must carry the persona + the facts."""
    d = run("who is prashant pandey")["data"]["directive"].lower()
    assert "disciple" in d, "must name Prashant as the disciple"
    assert "prashant" in d, "must name him"
    # the keyword facts the model generates prose from
    for fact in ("data scientist", "entrepreneur", "canada", "vedic", "india"):
        assert fact in d, f"directive missing keyword fact: {fact!r}"
    # persona protection — must instruct staying in character
    assert "character" in d or "guruji" in d or "sharma" in d, "must protect the persona"
    print("ok: directive_content")


def test_empty_query_is_noop():
    for q in ("", "   ", "\n"):
        env = run(q)
        assert env["success"] is True, env
        assert env["data"]["triggered"] is False
        assert env["data"]["directive"] == ""
    print("ok: empty_query_is_noop")


def test_bad_input_error_envelope():
    env = run(None)  # type: ignore[arg-type]
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] == "bad_input", env["errors"]
    print("ok: bad_input_error_envelope")


if __name__ == "__main__":
    test_envelope_shape()
    test_all_trigger_cases()
    test_all_non_trigger_cases()
    test_directive_content()
    test_empty_query_is_noop()
    test_bad_input_error_envelope()
    print("\nALL TESTS PASSED")
