"""Tests for storyteller — the lean two-verb teller (Tell + Ask).

Run: venv/bin/python -m tools.read_pass.storyteller.test_check  (from purangpt/)

No spoiler gate (deliberately removed — Puranic stories don't have spoilers; see
check.py docstring). The deterministic core is: classify an interruption, and move
the bookmark correctly. The load-bearing test: a QUESTION must NOT move the
bookmark, so narration resumes exactly where it paused.
"""
from tools.read_pass.storyteller.check import (
    run, classify_intent, next_action, Bookmark,
)

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}


# ── intent classification ─────────────────────────────────────────────────────
def test_commands_classified():
    assert classify_intent("continue")["intent"] == "continue"
    assert classify_intent("go on then")["intent"] == "continue"
    assert classify_intent("what happens next?")["intent"] == "continue"
    assert classify_intent("go back a bit")["intent"] == "go_back"
    assert classify_intent("say that again")["intent"] == "go_back"
    assert classify_intent("where are we?")["intent"] == "recap"
    assert classify_intent("remind me what's happened")["intent"] == "recap"
    print("ok: commands_classified")


def test_questions_classified():
    assert classify_intent("who is this guy?")["intent"] == "who"
    assert classify_intent("why did he do that?")["intent"] == "why"
    assert classify_intent("what does the bow mean?")["intent"] == "what"
    assert classify_intent("tell me about Hanuman")["intent"] == "what"
    print("ok: questions_classified")


def test_kind_split():
    # commands vs questions get the right 'kind'
    assert classify_intent("continue")["kind"] == "command"
    assert classify_intent("where are we")["kind"] == "command"
    assert classify_intent("who is Sita")["kind"] == "question"
    assert classify_intent("why did Rama leave")["kind"] == "question"
    # empty → other/other; unrecognized non-empty → treated as a question to answer
    assert classify_intent("")["kind"] == "other"
    assert classify_intent("hmm interesting")["kind"] == "question"
    print("ok: kind_split")


def test_command_beats_question_word():
    # "where are we" contains no who/why but is a recap; "what happens next" is a
    # CONTINUE command, not a 'what' question — order in the matcher guarantees it.
    assert classify_intent("where are we now")["intent"] == "recap"
    assert classify_intent("what happens next")["intent"] == "continue"
    print("ok: command_beats_question_word")


# ── the bookmark dataclass ────────────────────────────────────────────────────
def test_bookmark_advance_and_back():
    bm = Bookmark(corpus="ramayana")
    bm.advance(); bm.advance()
    assert bm.index == 2 and bm.told == 2
    bm.back()
    assert bm.index == 1
    assert bm.told == 2, "going back must NOT un-tell — told is the high-water mark"
    # can't go below zero
    bm.back(); bm.back(); bm.back()
    assert bm.index == 0
    print("ok: bookmark_advance_and_back")


# ── THE LOAD-BEARING TEST: a question must not move the bookmark ──────────────
def test_question_does_not_move_bookmark():
    """The whole point of an interruptible teller: you can stop, ask anything, and
    it RESUMES where it paused. So a question routes to 'answer' and leaves the
    bookmark untouched."""
    bm = Bookmark(corpus="ramayana", index=7, told=7)
    act = next_action("who is this demon?", bm)
    assert act["action"] == "answer"
    assert act["bookmark"]["index"] == 7, "a question moved the bookmark — resume broke!"
    assert act["bookmark"]["told"] == 7
    print("ok: question_does_not_move_bookmark  <<< the one that matters")


def test_continue_advances_bookmark():
    bm = Bookmark(corpus="ramayana", index=3, told=3)
    act = next_action("go on", bm)
    assert act["action"] == "narrate"
    assert act["bookmark"]["index"] == 4
    print("ok: continue_advances_bookmark")


def test_go_back_steps_bookmark():
    bm = Bookmark(corpus="ramayana", index=5, told=8)
    act = next_action("go back", bm)
    assert act["action"] == "renarrate"
    assert act["bookmark"]["index"] == 4
    assert act["bookmark"]["told"] == 8, "back must not lower the told high-water mark"
    print("ok: go_back_steps_bookmark")


def test_recap_uses_last_recap_no_move():
    bm = Bookmark(corpus="ramayana", index=9, told=9,
                  last_recap="Rama has been exiled to the forest.")
    act = next_action("where are we?", bm)
    assert act["action"] == "recap"
    assert act["recap"] == "Rama has been exiled to the forest."
    assert act["bookmark"]["index"] == 9, "recap must not move position"
    print("ok: recap_uses_last_recap_no_move")


# ── the JSON contract ─────────────────────────────────────────────────────────
def test_run_envelope():
    env = run("continue", {"corpus": "ramayana", "index": 0, "told": 0})
    assert set(env.keys()) == ENVELOPE_KEYS
    assert env["success"] is True, env["errors"]
    assert env["data"]["action"] == "narrate"
    assert env["data"]["bookmark"]["index"] == 1
    print("ok: run_envelope")


def test_run_fresh_bookmark_defaults():
    # no bookmark passed → starts fresh at index 0
    env = run("who is Rama?")
    assert env["success"] is True
    assert env["data"]["action"] == "answer"
    assert env["data"]["bookmark"]["index"] == 0
    print("ok: run_fresh_bookmark_defaults")


def test_run_error_envelope():
    env = run(None)
    assert env["success"] is False
    assert env["data"] is None
    assert env["errors"][0]["code"] == "no_text"
    print("ok: run_error_envelope")


if __name__ == "__main__":
    test_commands_classified()
    test_questions_classified()
    test_kind_split()
    test_command_beats_question_word()
    test_bookmark_advance_and_back()
    test_question_does_not_move_bookmark()
    test_continue_advances_bookmark()
    test_go_back_steps_bookmark()
    test_recap_uses_last_recap_no_move()
    test_run_envelope()
    test_run_fresh_bookmark_defaults()
    test_run_error_envelope()
    print("\nALL TESTS PASSED")
