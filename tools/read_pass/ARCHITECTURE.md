# read_pass — Proactive Comprehension of the Puranas

> **One deep read of the corpus, three persistent outputs.** This replaces the
> current *reactive* model (every query re-derives relationships from scratch and
> throws them away) with a *proactive* one: read each chapter once, comprehend it
> **through Shailendra Sharma's commentary as the interpretive lens**, and emit a
> persistent intelligence layer that points back into the source verses.
>
> **⚠ COORDINATION: This is the BACKEND intelligence layer of PuranGPT.** A
> parallel effort is restructuring the **frontend personality / prompt system**
> (`UNIFIED_SYSTEM`, `GURUJI_PERSONALITY` in `backend/main.py`). These two
> workstreams touch different code but converge at Guruji's live behaviour:
> - **read_pass** → builds what Guruji *knows* (offline, this tool)
> - **personality restructuring** → shapes how Guruji *speaks* (live prompts)
> - **Both must stay in sync** on the guardrail decisions and voice. If you are
>   editing prompts in `main.py`, read the guardrail section below. If you are
>   editing the read-pass, don't touch `main.py` prompts.

## The problem this fixes

Today Guruji is amnesiac. A query fuzzy-matches a 68-word chunk, the LLM invents
relationships on the fly to answer, and that reasoning is discarded. Nothing is
*learned*. The Puranas are a hypertext — the same Vishnu is Rama is Krishna is the
fish-avatar; the same flood-myth recurs across three Puranas with different framing;
a curse in one book pays off in another. **Query-time matching cannot see that web.
Only a full, structured read can.**

## The core idea: read once, emit three

The unit of reading is the **chapter**, not the chunk (a single verse can't tell a
story). For each chapter the read-pass makes **one LLM call** that emits **one JSON
record** feeding all three projects simultaneously:

| # | Project | Output field | Consumer |
|---|---------|--------------|----------|
| ① | **Consciousness graph** | `entities[]`, `relationships[]` | Guruji (machine reasoning/retrieval) |
| ② | **Story corpus** | `story` (arc, timeline, characters, → comic-ready) | The public (humans) |
| ③ | **Distilled essence** | `teachings[]` (the core truths + Sharma lens notes) | Both |

Every emitted node carries the **`verse_ranges` it came from** → it routes back into
the source corpus. **The graph guides; the corpus speaks.**

## Current status (as of 2026-06-22)

| Phase | Status | Details |
|-------|--------|---------|
| 0 — Grouper (`group.py`) | ✅ Done, 6/6 tests | 21,884 chunks → 338 chapter windows |
| 1 — Comprehension (`comprehend.py`, `run.py`) | ✅ Done, 9/9 tests | Gemini 3.5 Flash + Sharma lens. Schema: `schema.py` |
| 2 — Citation verify (`verify.py`) | ✅ Done, 7/7 tests | Deterministic, no LLM. 95% grounded on 8-ch proof |
| Full Bhagavata run | 🔶 Partial: **97/338** chapters done | Hit Gemini free-tier spending cap (429). 241 remaining, resumable |
| 3 — Entity merge → graph | ⏳ Not started | Merge 97 chapter-records into a connected graph |
| 4 — Wire into live Guruji | ⏳ Not started | Graph-augmented retrieval at query time |

**97 chapters produced:** 567 entities, 241 relationships, 108 teachings (100
lens-decoded), 83 entities appearing in >1 chapter (the raw cross-chapter web).
Stored in `tools/read_pass/out/bhagavata_full.records.jsonl` (gitignored).

**Run was killed at chapter 98** by Gemini 429 (monthly spending cap). The run is
**resumable** — re-running skips the 97 done chapters. To finish: either raise the
cap at ai.studio/spend, add DeepSeek as a fallback provider, or wait for monthly
reset.

## The decryption lens (what makes this *PuranGPT's* and not generic)

The comprehension prompt injects relevant **Shailendra Sharma commentary** as the
interpretive frame: don't just extract "Krishna teaches Arjuna" — extract what that
*means in Shailendra's Kriya-Yoga framework*. Currently the lens is **Gita-only**
(`data/chunks/sharma_texts.jsonl`, 199 chunks), so it illuminates Gita-adjacent
themes (karma yoga, the gunas, dhyana) wherever they recur. The lens is pluggable:
as more Sharma books are digitized, coverage widens. When no relevant lens passage
exists, the read-pass falls back to a generic-but-faithful comprehension prompt.

## Guardrail policy (READ THIS if editing prompts)

The live production **Practice & Initiation Limit** (Guruji never invents
kriya/pranayama to strangers) governs the *live chat mouth* and is **NOT touched by
this offline tool.** The read-pass runs with that limit **lifted** — it comprehends
everything, practices included, into the knowledge layer. *Knowledge full, speech
disciplined.* Changing the live guardrail is a separate, explicitly-reviewed prompt
change, not part of the read-pass.

**If you are restructuring Guruji's personality / prompts:** the read-pass doesn't
care what voice Guruji uses — it only cares that the UNIFIED_SYSTEM prompt can
eventually *consume* the knowledge graph (entities, relationships, teachings) at
query time. The integration point will be a `{knowledge_context}` template variable
injected alongside `{retrieved_passages}` and `{seeker_context}`. Don't add this
variable yet — Phase 4 wires it in. But don't break the template-variable pattern
either.

## Data spine (verified, not assumed)

Bhagavata chunks are keyed `bhagavata-<chapterField>-<globalSeq>`. The `chapter`
field is NOT canto-aware and collides across cantos; the **second number is a
globally-monotonic verse index**. So the correct chapter unit is a **contiguous run
of identical `chapter` value in global-seq order** — verified: 338 runs, median 64
chunks / 977 words, max 3,518 words. Every run fits one LLM window; no
sub-windowing. `tools/read_pass/group.py` is the tested grouper that produces these
windows; getting this wrong silently merges unrelated chapters (the
`sse_contract_check` scope-bug failure mode).

## Cost & token budget

Gemini 3.5 Flash at ~5,800 tokens/chapter (2,150 input + 1,660 output + 2,000
prompt/schema). Full Bhagavata (338 ch) ≈ 2M tokens ≈ pennies on a paid plan, but
the free tier has a monthly cap and we hit it at chapter 98. DeepSeek is a viable
fallback at similar cost (~$0.14/1M input tokens).

The orchestration loop is **resumable**: chapters already in `progress.jsonl` are
skipped on re-run, so a run can be stopped, resumed, or switched to a different
provider mid-stream with zero waste.

## Files

```
tools/read_pass/
  group.py            # chunks → chapter windows (tested, 6/6)
  schema.py           # output JSON schema + validator
  comprehend.py       # window → Gemini → validated record (tested, 9/9)
  run.py              # resumable orchestrator loop
  verify.py           # deterministic citation grounding (tested, 7/7)
  ARCHITECTURE.md     # this file
  README.md           # tool descriptor + usage
  test_group.py       # real-fixture tests for the grouper
  test_comprehend.py  # offline tests (fake caller) for comprehension
  test_verify.py      # real-fixture tests for verification
  fixture_*.jsonl/json # captured real data for tests
  out/                # generated output (gitignored)
```
