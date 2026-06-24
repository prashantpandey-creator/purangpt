"""seeker_memory.distill — REVISE a session's running read of the seeker.

The WRITE-path heart of seeker memory (axis 2 of the "Smriti" design): given the
PRIOR running summary of a chat session and the latest exchange, produce a REVISED
running read of the seeker. It does NOT append blindly — it keeps what still holds,
OVERWRITES what the new exchange contradicts, and DROPS what is now stale. That
overwrite-on-contradiction is what makes the memory *evolve* instead of merely
*accumulate*.

Rule-0 shape: the LLM is INJECTED as `caller`, so this module is pure plumbing +
prompt construction — deterministic and unit-testable without a network call. The
live wire (main.py) passes a real `caller` backed by `call_llm_once`. Returns the
standard {success,data,metadata,errors} envelope; never raises for an expected
failure (empty input, a degraded provider) — it returns success=False so the live
fire-and-forget caller can simply skip the write and leave the prior summary intact.

Input contract:  distill_session_summary(prior_summary, exchange, caller, max_words=80)
Output contract (envelope.data on success): {summary, revised, prior_summary}
"""
from __future__ import annotations

import sys
import json
from typing import Any, Callable, Dict, List, Union

Exchange = Union[str, List[Dict[str, str]]]
Caller = Callable[..., str]

_SYSTEM = (
    "You distill a private, evolving read of a spiritual seeker from their "
    "conversation with their Guru. You are not summarizing the chat — you are "
    "maintaining one short, living note about WHO this seeker is: what they are "
    "grappling with, their level, their recurring themes."
)


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _format_exchange(exchange: Exchange) -> str:
    """Render the latest exchange as plain text the model can read."""
    if isinstance(exchange, str):
        return exchange.strip()
    lines = []
    for msg in exchange:
        role = (msg.get("role") or "").strip() or "?"
        content = (msg.get("content") or "").strip()
        if content:
            lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def _build_prompt(prior_summary: str, exchange_text: str, max_words: int) -> str:
    prior = (prior_summary or "").strip()
    if prior:
        prior_block = (
            "Here is your CURRENT running read of this seeker (it may be wrong or "
            "out of date):\n"
            f"\"\"\"\n{prior}\n\"\"\"\n\n"
            "Here is the latest exchange:\n"
            f"\"\"\"\n{exchange_text}\n\"\"\"\n\n"
            "Produce your UPDATED read. KEEP what still holds. REVISE — overwrite — "
            "anything this exchange CONTRADICTS (e.g. if the read said 'does not "
            "meditate' and they now describe a daily practice, rewrite that line; do "
            "NOT keep both). DROP what is now stale. Do not blindly append; this is a "
            "revision of one note, not a growing log."
        )
    else:
        prior_block = (
            "You have no prior read of this seeker yet. From the exchange below, write "
            "your FIRST short read of who they are.\n\n"
            "Latest exchange:\n"
            f"\"\"\"\n{exchange_text}\n\"\"\"\n"
        )
    return (
        prior_block
        + f"\n\nReturn ONLY the updated read as 1-3 plain sentences (max {max_words} "
        "words). No preamble, no markdown, no quotes around it."
    )


def distill_session_summary(prior_summary: str,
                            exchange: Exchange,
                            caller: Caller,
                            max_words: int = 80,
                            temperature: float = 0.2) -> Dict[str, Any]:
    """Revise the running session read. See module docstring for the contract."""
    prior = (prior_summary or "").strip()
    exchange_text = _format_exchange(exchange)
    metadata = {
        "had_prior": bool(prior),
        "exchange_chars": len(exchange_text),
        "max_words": max_words,
    }

    if not exchange_text:
        return _envelope(False, None, metadata,
                         [{"code": "empty_exchange",
                           "message": "no exchange text to distill from"}])

    prompt = _build_prompt(prior, exchange_text, max_words)
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        reply = caller(messages, temperature=temperature)
    except Exception as e:  # any provider/network failure → graceful skip
        return _envelope(False, None, metadata,
                         [{"code": "caller_failed", "message": f"{type(e).__name__}: {e}"}])

    summary = (reply or "").strip()
    if not summary:
        return _envelope(False, None, metadata,
                         [{"code": "empty_result",
                           "message": "caller returned an empty distillation"}])

    data = {
        "summary": summary,
        "revised": bool(prior),  # a revision only if there was something to revise
        "prior_summary": prior,
    }
    return _envelope(True, data, metadata, [])


# --- CLI: human by default, --json for the envelope. Uses a stub caller unless a
#     real one is wired (this module is normally imported, not run standalone). ---

def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    prior = ""
    exchange = ""
    if "--prior" in argv:
        prior = argv[argv.index("--prior") + 1]
    if "--exchange" in argv:
        exchange = argv[argv.index("--exchange") + 1]

    def _stub(messages, temperature=0.2):
        # No network here; echo the constructed user prompt so a human can eyeball it.
        return "[stub caller — wire call_llm_once for a real distill] " + messages[-1]["content"][:60]

    env = distill_session_summary(prior, exchange, caller=_stub)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        print(f"OK (revised={env['data']['revised']}): {env['data']['summary']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
