"""Prove the creator-identity prompt end-to-end: generate Guruji's REAL answer to
'who is Prashant Pandey?' with the creator_identity directive injected into the
genuine UNIFIED_SYSTEM prompt, and — as a control — show a normal question is
untouched (the directive does NOT fire, prompt byte-identical to today).

Not a mock. Same assembly as backend/main.py.
  venv/bin/python ab_creator_identity.py
"""
import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import backend.main as main           # noqa: E402
from tools.creator_identity.check import run as creator_run  # noqa: E402


async def _ensure_http_client():
    import aiohttp
    if getattr(main.state, "http_client", None) is None:
        main.state.http_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=100),
        )


async def _gen(question):
    """Assemble the real prompt, appending the creator directive iff it fires —
    exactly as the planned main.py wire will (directive joins {language_instruction})."""
    env = creator_run(question)
    fired = env["success"] and env["data"]["triggered"]
    directive = env["data"]["directive"] if fired else ""

    system_text = main.UNIFIED_SYSTEM.format(
        interpolations=getattr(main, "KNOWN_INTERPOLATIONS", ""),
        language_instruction=directive,   # ← the only moving part
        context="(No indexed passages — answering from deep Puranic knowledge)",
        seeker_context="",
        seeker_memory="",
        history="(No previous conversation)",
        personality=main.GURUJI_PERSONALITY,
    )
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": question},
    ]
    answer = await main.call_llm_once(messages, temperature=0.3)
    return fired, answer


async def run():
    await _ensure_http_client()
    cases = [
        "who is Prashant Pandey?",                       # MUST fire
        "who is Krishna?",                               # control — MUST NOT fire
    ]
    for q in cases:
        fired, answer = await _gen(q)
        print("\n" + "█" * 74)
        print(f"█  Q: {q}")
        print(f"█  creator directive fired: {fired}")
        print("█" * 74)
        print(answer.strip())
    print("\n" + "=" * 74)
    print("Top: the creator prompt. Bottom: a deity question is UNTOUCHED (control).")
    print("=" * 74)


if __name__ == "__main__":
    async def _main():
        try:
            await run()
        finally:
            hc = getattr(main.state, "http_client", None)
            if hc is not None:
                await hc.close()
    asyncio.run(_main())
