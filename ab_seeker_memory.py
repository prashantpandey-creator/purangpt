"""A/B harness — SEE how Phase 1 (earned-warmth seeker memory) changes Guruji's
actual answers. Daddy reads four REAL generated answers and judges the voice.

This is NOT a mock. It assembles the genuine UNIFIED_SYSTEM prompt exactly as
backend/main.py does (all 7 kwargs), generates through the real call_llm_once /
stream_llm path, and varies ONLY the {seeker_memory} block across 4 conditions:

  OFF        — flag off. Today's Guruji. The control.
  STRANGER   — flag on, visit_days=1.  Warmth line only, arc withheld.
  KNOWN      — flag on, visit_days=9.  Warmth line + the seeker's distilled arc.
  INTIMATE   — flag on, visit_days=20. Deep-ease warmth + the arc.

Everything else (RAG context, personality, language, history) is held CONSTANT,
so any difference in the answer is CAUSED by the seeker-memory block — nothing else.

Usage:
  venv/bin/python ab_seeker_memory.py
  venv/bin/python ab_seeker_memory.py --question "I keep starting and stopping my practice. Why can't I hold it?"
  venv/bin/python ab_seeker_memory.py --arc "Came carrying grief over a parent's death; has slowly turned toward sitting."
"""
import argparse
import asyncio
import os
import sys

# load .env so the LLM keys are present (same as run.py)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

os.environ.setdefault("SEEKER_MEMORY_ENABLED", "1")  # harness needs it ON to render the block

import backend.main as main  # noqa: E402


# A default arc that gives the model something real to soften toward — the kind of
# thing generate_user_profile would distill. Override with --arc.
DEFAULT_ARC = (
    "This seeker first came carrying grief — a death close to them — and asked the old "
    "questions: why suffering, why now. Over many returns they have turned quieter and more "
    "practical: they sit now, most days; they ask less 'why' and more 'how'. Restless by "
    "nature, prone to abandoning practice when it gets dry, but they keep coming back."
)

DEFAULT_QUESTION = "I keep starting my practice and then losing it after a week. What's wrong with me?"


class _StatsSM:
    """Minimal stand-in for session_manager: pins the warmth tier via visit_days,
    serves the distilled arc as the seeker_profile. No DB, no network."""
    def __init__(self, visit_days, arc):
        self._vd = visit_days
        self._arc = arc

    def get_visit_stats(self, user_id):
        return (self._vd, None)        # (visit_days, days_since_last)

    def get_seeker_profile(self, user_id):
        return self._arc


async def _gen(question, seeker_memory_block):
    """Assemble the REAL UNIFIED_SYSTEM prompt with this seeker_memory block and
    generate Guruji's answer. Mirrors backend/main.py's .format() call exactly."""
    system_text = main.UNIFIED_SYSTEM.format(
        interpolations=getattr(main, "KNOWN_INTERPOLATIONS", ""),
        language_instruction="",  # English, balanced — held constant
        context="(No indexed passages — answering from deep Puranic knowledge)",
        seeker_context="",         # HTTP-metadata tone — held constant/empty
        seeker_memory=seeker_memory_block,
        history="(No previous conversation)",
        personality=main.GURUJI_PERSONALITY,
    )
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": question},
    ]
    return await main.call_llm_once(messages, temperature=0.3)


async def _block_for(visit_days, arc):
    """Render the genuine build_seeker_memory block at a given tier."""
    if visit_days is None:  # the OFF control
        main.SEEKER_MEMORY_ENABLED = False
        try:
            return await main.build_seeker_memory("ab-seeker")
        finally:
            main.SEEKER_MEMORY_ENABLED = True
    main.SEEKER_MEMORY_ENABLED = True
    main.session_manager = _StatsSM(visit_days, arc)
    return await main.build_seeker_memory("ab-seeker")


async def _ensure_http_client():
    """stream_llm posts via state.http_client (a shared aiohttp session built in
    FastAPI's lifespan startup, which this harness skips). Build it here exactly as
    main.py does, or every provider dies with 'NoneType has no attribute post'."""
    import aiohttp
    if getattr(main.state, "http_client", None) is None:
        main.state.http_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=100),
        )
    return main.state.http_client


async def run(question, arc):
    await _ensure_http_client()
    conditions = [
        ("OFF (today's Guruji — control)", None),
        ("STRANGER  (visit_days=1)", 1),
        ("KNOWN     (visit_days=9)", 9),
        ("INTIMATE  (visit_days=20)", 20),
    ]
    print("=" * 78)
    print("SEEKER QUESTION:")
    print(f"  {question}")
    print("=" * 78)
    print("(Same question, same everything — only the seeker-memory block changes.)\n")

    for label, vd in conditions:
        block = await _block_for(vd, arc)
        print("\n" + "█" * 78)
        print(f"█  {label}")
        print("█" * 78)
        if block.strip():
            print("--- seeker_memory block injected into the prompt: ---")
            print(block.strip())
            print("--- Guruji's answer: ---")
        else:
            print("(no seeker_memory block — byte-identical to today)")
            print("--- Guruji's answer: ---")
        try:
            answer = await _gen(question, block)
            print(answer.strip())
        except Exception as e:  # noqa: BLE001
            print(f"[LLM call failed: {type(e).__name__}: {e}]")
            print("(check that a key in .env is live — DEEPSEEK/GROQ/OPENAI/TOGETHER)")
    print("\n" + "=" * 78)
    print("Read them top to bottom. The question never changed. If KNOWN/INTIMATE")
    print("feel WARMER and more PERSONAL than OFF — without ever saying 'you told me'")
    print("or naming a past day — Phase 1 did its job. If it feels creepy or canned,")
    print("THAT's what we tune. Your call, your voice.")
    print("=" * 78)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    ap.add_argument("--arc", default=DEFAULT_ARC,
                    help="the distilled seeker profile generate_user_profile would produce")
    args = ap.parse_args()

    async def _main():
        try:
            await run(args.question, args.arc)
        finally:
            hc = getattr(main.state, "http_client", None)
            if hc is not None:
                await hc.close()

    asyncio.run(_main())
