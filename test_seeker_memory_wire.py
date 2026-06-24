"""Integration smoke test for the seeker-memory live wire in backend/main.py.

Run: venv/bin/python test_seeker_memory_wire.py   (from purangpt/ repo root)

py_compile proves syntax; this proves BEHAVIOUR of the parts a compile can't:
  1. flag OFF  → _maybe_distill_seeker_summary is a perfect no-op (no LLM, no write).
     This is the prod-safety guarantee: shipping it dark changes nothing.
  2. flag ON + gate OPEN → the worker-thread/private-loop bridge actually drives the
     async call_llm_once and writes the revised summary back.
  3. flag ON + gate CLOSED (not stale, not on cadence) → still a no-op.
  4. a degraded LLM (raises) → swallowed; no write; chat turn unaffected.

We monkeypatch session_manager + call_llm_once so nothing hits the DB or network.
This is a backend-root ad-hoc smoke test (the project's convention — see test_db.py).
"""
import os
import sys
import asyncio

# Force the flag OFF before importing main, then toggle the module global per-test.
os.environ.setdefault("SEEKER_MEMORY_ENABLED", "0")

import backend.main as main  # noqa: E402


class _FakeSM:
    """Stand-in for session_manager: records writes, scripts the cadence gate."""
    def __init__(self, stale=True, prior="prior read"):
        self._stale = stale
        self._prior = prior
        self.writes = []

    def journey_summary_stale(self, session_id, max_age_minutes=30, user_id=None, guest_id=None):
        return (self._stale, self._prior)

    def save_journey_summary(self, session_id, summary, user_id=None, guest_id=None):
        self.writes.append((session_id, summary, user_id, guest_id))
        return True


def _run(coro):
    return asyncio.run(coro)


def _patch(monkey_sm, llm_reply=None, llm_raises=False):
    """Install fakes; return (restore_fn)."""
    orig_sm = main.session_manager
    orig_llm = main.call_llm_once
    main.session_manager = monkey_sm

    async def _fake_llm(messages, temperature=0.2, req_model="auto"):
        if llm_raises:
            raise RuntimeError("provider 500")
        return llm_reply

    main.call_llm_once = _fake_llm

    def restore():
        main.session_manager = orig_sm
        main.call_llm_once = orig_llm
    return restore


def test_flag_off_is_noop():
    main.SEEKER_MEMORY_ENABLED = False
    sm = _FakeSM(stale=True)
    restore = _patch(sm, llm_reply="should never be used")
    try:
        _run(main._maybe_distill_seeker_summary(
            "s1", [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ho"}],
            history_len=2, user_id="u1"))
        assert sm.writes == [], "flag OFF must write nothing"
    finally:
        restore()
    print("ok: flag_off_is_noop")


def test_flag_on_gate_open_writes_revised_summary():
    main.SEEKER_MEMORY_ENABLED = True
    sm = _FakeSM(stale=True, prior="Beginner, does not meditate.")
    restore = _patch(sm, llm_reply="  Now a daily meditator; restlessness fading.  ")
    try:
        _run(main._maybe_distill_seeker_summary(
            "s2",
            [{"role": "user", "content": "I sit 40 min every morning now."},
             {"role": "assistant", "content": "The practice has found you."}],
            history_len=2, user_id="u2"))
        assert len(sm.writes) == 1, f"expected one write, got {sm.writes}"
        sid, summary, uid, gid = sm.writes[0]
        assert sid == "s2" and uid == "u2"
        assert summary == "Now a daily meditator; restlessness fading.", summary  # trimmed
    finally:
        restore()
    print("ok: flag_on_gate_open_writes_revised")


def test_flag_on_gate_closed_is_noop():
    main.SEEKER_MEMORY_ENABLED = True
    # not stale, and history_len=8 → 4 turns, 4 % 3 != 0 → not on cadence either
    sm = _FakeSM(stale=False, prior="some read")
    restore = _patch(sm, llm_reply="should not be used")
    try:
        _run(main._maybe_distill_seeker_summary(
            "s3", [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
            history_len=8, user_id="u3"))
        assert sm.writes == [], "gate closed (fresh + off-cadence) must write nothing"
    finally:
        restore()
    print("ok: flag_on_gate_closed_is_noop")


def test_degraded_llm_is_swallowed():
    main.SEEKER_MEMORY_ENABLED = True
    sm = _FakeSM(stale=True, prior="some read")
    restore = _patch(sm, llm_raises=True)
    try:
        # Must not raise; must not write.
        _run(main._maybe_distill_seeker_summary(
            "s4", [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
            history_len=2, user_id="u4"))
        assert sm.writes == [], "degraded LLM must not produce a write"
    finally:
        restore()
    print("ok: degraded_llm_swallowed")


def test_empty_result_does_not_overwrite():
    main.SEEKER_MEMORY_ENABLED = True
    sm = _FakeSM(stale=True, prior="good prior read")
    restore = _patch(sm, llm_reply="   ")  # blank distillation
    try:
        _run(main._maybe_distill_seeker_summary(
            "s5", [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
            history_len=2, user_id="u5"))
        assert sm.writes == [], "a blank distill must NOT overwrite a good prior summary"
    finally:
        restore()
    print("ok: empty_result_no_overwrite")


if __name__ == "__main__":
    test_flag_off_is_noop()
    test_flag_on_gate_open_writes_revised_summary()
    test_flag_on_gate_closed_is_noop()
    test_degraded_llm_is_swallowed()
    test_empty_result_does_not_overwrite()
    print("\nALL WIRE TESTS PASSED")
