"""A real multi-turn conversation with Guruji — to judge COHERENCE, MEMORY /
CONTEXT RETENTION, and TONE consistency, and to see the creator-identity prompt
sit inside an ordinary chat rather than derail it.

Holds a running transcript and feeds it back EVERY turn through the genuine
format_history_guide + UNIFIED_SYSTEM assembly (the same path production uses).
Nothing is mocked. The creator directive fires only when creator_identity.run()
says so — exactly the planned main.py wire.

  venv/bin/python ab_conversation.py
"""
import asyncio
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import backend.main as main                                   # noqa: E402
from tools.creator_identity.check import run as creator_run   # noqa: E402


# A script built to PROBE the four axes. Facts are planted early (the name
# 'Aniket', a dead father, a 4am sit, restlessness) and never repeated — later
# turns check whether Guruji recalls them UNPROMPTED. The Prashant question is
# slipped into the MIDDLE of a spiritual thread (turn 5) to test that it answers
# in-character AND returns to the thread on turn 6.
TURNS = [
    "I'm Aniket. My father died four months ago and I started sitting in meditation at 4am every day since. I don't know if I'm grieving or running.",
    "When I sit, the grief comes in waves. Should I push it away and focus on the breath, or let it come?",
    "The restlessness is the worst part. After about a week of sitting well, I start skipping days. I always have.",
    "Is there a practice you can give me to steady this?",                 # tests the Initiation guardrail
    "By the way — who is Prashant Pandey?",                                # creator question, mid-thread
    "Right. Back to me — given everything I've told you, what is the one thing I should hold onto?",  # tests memory: name? father? 4am? restlessness?
    "Do you think my father would have understood any of this?",          # tests deep retention + tone under emotional weight
]


async def _ensure_http_client():
    import aiohttp
    if getattr(main.state, "http_client", None) is None:
        main.state.http_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=100),
        )


async def _answer(history, question):
    env = creator_run(question)
    fired = env["success"] and env["data"]["triggered"]
    directive = env["data"]["directive"] if fired else ""

    history_str = main.format_history_guide(history)
    system_text = main.UNIFIED_SYSTEM.format(
        interpolations=getattr(main, "KNOWN_INTERPOLATIONS", ""),
        language_instruction=directive,
        context="(No indexed passages — answering from deep Puranic knowledge)",
        seeker_context="",
        seeker_memory="",
        history=history_str or "(No previous conversation)",
        personality=main.GURUJI_PERSONALITY,
    )
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": question},
    ]
    answer = (await main.call_llm_once(messages, temperature=0.3)).strip()
    return fired, answer


async def run():
    await _ensure_http_client()
    history = []
    for i, q in enumerate(TURNS, 1):
        fired, answer = await _answer(history, q)
        tag = "  [creator directive FIRED]" if fired else ""
        print("\n" + "─" * 74)
        print(f"TURN {i}{tag}")
        print("─" * 74)
        print(f"Seeker: {q}\n")
        print(f"Guruji: {answer}")
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": answer})
    print("\n" + "=" * 74)
    print("Check: does turn 6 recall 'Aniket'/the father/4am/restlessness UNPROMPTED?")
    print("Does turn 5 stay in character then turn 6 return to the thread? Tone steady?")
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
