"""Tests for seeker_memory.distill_session_summary — written FIRST (Rule 0 precondition A).

Run: venv/bin/python -m tools.seeker_memory.test_distill   (from purangpt/ repo root)

distill_session_summary is the WRITE-path heart of seeker memory: given the PRIOR
running summary of a session + the latest exchange(s), it produces a REVISED running
read of the seeker — keeping what still holds, OVERWRITING what the new exchange
contradicts, DROPPING what is now stale. It must NOT append blindly (that is the
"accumulation dressed as evolution" failure the design explicitly kills).

The LLM is INJECTED as `caller` so these tests are deterministic and free — we never
hit the network. We assert two deterministic guarantees:
  1. PLUMBING: the prompt we hand the caller carries the prior summary + the exchange
     + an explicit REVISE/overwrite-on-contradiction instruction. (If the prompt
     doesn't instruct overwrite, the LLM can't be blamed for appending.)
  2. CONTRACT: the standard {success,data,metadata,errors} envelope, empty-input
     handling, and fail-graceful behaviour when the caller raises.
"""
from tools.seeker_memory.distill import distill_session_summary

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"summary", "revised", "prior_summary"}


# ---- fakes: a caller we fully control, and a spy that captures the prompt ----

def _fixed_caller(reply):
    """A fake LLM caller that ignores the messages and returns `reply`."""
    def _call(messages, temperature=0.2):
        return reply
    return _call


def _spy_caller(reply="ok"):
    """A fake caller that records the messages it was handed, for prompt asserts."""
    captured = {}

    def _call(messages, temperature=0.2):
        captured["messages"] = messages
        captured["temperature"] = temperature
        return reply
    return _call, captured


# A realistic prior + exchange used across several tests.
PRIOR = "Beginner seeker, asks about ritual worship. Says they do not meditate."
EXCHANGE = [
    {"role": "user", "content": "I've started sitting every morning for 40 minutes, "
                                "watching the breath. The restlessness is fading."},
    {"role": "assistant", "content": "Then the practice has already begun to find you."},
]


# ---------------------------------------------------------------------------
# 1. Envelope / contract
# ---------------------------------------------------------------------------

def test_envelope_shape():
    env = distill_session_summary(PRIOR, EXCHANGE, caller=_fixed_caller("revised read"))
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True, env
    assert env["errors"] == []
    assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    print("ok: envelope_shape")


def test_summary_is_the_caller_reply_trimmed():
    env = distill_session_summary(PRIOR, EXCHANGE, caller=_fixed_caller("  a daily meditator now  "))
    assert env["data"]["summary"] == "a daily meditator now", env["data"]
    assert env["data"]["revised"] is True
    assert env["data"]["prior_summary"] == PRIOR
    print("ok: summary_is_caller_reply_trimmed")


def test_empty_exchange_is_a_clean_failure_not_a_crash():
    # Nothing new to learn from → expected failure envelope, NOT an LLM call.
    spy, captured = _spy_caller()
    env = distill_session_summary(PRIOR, [], caller=spy)
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] == "empty_exchange", env["errors"]
    assert "messages" not in captured, "must not call the LLM with nothing to distill"
    print("ok: empty_exchange_clean_failure")


def test_caller_exception_is_failgraceful():
    def _boom(messages, temperature=0.2):
        raise RuntimeError("provider 500")
    env = distill_session_summary(PRIOR, EXCHANGE, caller=_boom)
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] == "caller_failed", env["errors"]
    print("ok: caller_exception_failgraceful")


def test_caller_returns_blank_is_a_failure():
    # An empty distillation is useless and must not overwrite a good prior with "".
    env = distill_session_summary(PRIOR, EXCHANGE, caller=_fixed_caller("   "))
    assert env["success"] is False, env
    assert env["errors"][0]["code"] == "empty_result", env["errors"]
    print("ok: blank_result_is_failure")


# ---------------------------------------------------------------------------
# 2. The REVISE plumbing — the deterministic guarantee that it doesn't just append
# ---------------------------------------------------------------------------

def test_prompt_carries_prior_summary_and_exchange():
    spy, captured = _spy_caller("revised")
    distill_session_summary(PRIOR, EXCHANGE, caller=spy)
    blob = " ".join(m["content"] for m in captured["messages"]).lower()
    assert "do not meditate" in blob, "prior summary must be in the prompt"
    assert "sitting every morning" in blob, "the new exchange must be in the prompt"
    print("ok: prompt_carries_prior_and_exchange")


def test_prompt_instructs_overwrite_on_contradiction():
    # This is THE guarantee: the prompt must tell the model to REVISE/overwrite/drop,
    # not append. Without this instruction, "evolution" is a lie.
    spy, captured = _spy_caller("revised")
    distill_session_summary(PRIOR, EXCHANGE, caller=spy)
    blob = " ".join(m["content"] for m in captured["messages"]).lower()
    assert "revise" in blob or "overwrite" in blob or "contradict" in blob, \
        "prompt must instruct revision, not blind append"
    assert "append" not in blob or "do not" in blob or "not append" in blob or "instead of append" in blob, \
        "prompt must not invite blind appending"
    print("ok: prompt_instructs_overwrite")


def test_empty_prior_is_handled_first_session():
    # First-ever distillation: no prior summary. Must still work (revised=False-ish:
    # there was nothing to revise, it's a fresh read), and must not put 'None' junk
    # into the prompt.
    spy, captured = _spy_caller("a fresh read of a new seeker")
    env = distill_session_summary("", EXCHANGE, caller=spy)
    assert env["success"] is True, env
    assert env["data"]["summary"] == "a fresh read of a new seeker"
    assert env["data"]["revised"] is False, "no prior → not a revision, a first read"
    blob = " ".join(m["content"] for m in captured["messages"]).lower()
    assert "none" not in blob.split(), "empty prior must not leak the literal 'None'"
    print("ok: empty_prior_first_session")


def test_temperature_is_low_for_a_factual_distill():
    spy, captured = _spy_caller("revised")
    distill_session_summary(PRIOR, EXCHANGE, caller=spy)
    assert captured["temperature"] <= 0.3, "distillation should be low-temp/factual"
    print("ok: low_temperature")


def test_exchange_can_be_a_plain_string():
    # Convenience: callers may pass a pre-formatted exchange string instead of a msg list.
    spy, captured = _spy_caller("revised")
    env = distill_session_summary(PRIOR, "User asked about khechari mudra.", caller=spy)
    assert env["success"] is True, env
    blob = " ".join(m["content"] for m in captured["messages"]).lower()
    assert "khechari" in blob
    print("ok: exchange_as_string")


if __name__ == "__main__":
    test_envelope_shape()
    test_summary_is_the_caller_reply_trimmed()
    test_empty_exchange_is_a_clean_failure_not_a_crash()
    test_caller_exception_is_failgraceful()
    test_caller_returns_blank_is_a_failure()
    test_prompt_carries_prior_summary_and_exchange()
    test_prompt_instructs_overwrite_on_contradiction()
    test_empty_prior_is_handled_first_session()
    test_temperature_is_low_for_a_factual_distill()
    test_exchange_can_be_a_plain_string()
    print("\nALL TESTS PASSED")
