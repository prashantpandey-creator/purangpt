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

## Current status (as of 2026-06-23, post graph-health audit)

| Phase | Status | Details |
|-------|--------|---------|
| 0 — Grouper (`group.py`) | ✅ Done, 6/6 tests | 21,884 chunks → 338 chapter windows |
| 1 — Comprehension (`comprehend.py`, `run.py`) | ✅ Done, 9/9 tests | Multi-provider (see below). Schema: `schema.py` |
| 2 — Citation verify (`verify.py`) | ✅ Done, 11/11 tests | Deterministic, no LLM. Marker grammar: `_MARKER_RE` (fixed from Bhagavata-only) |
| 3 — Entity merge → graph (`graph.py`) | ✅ Done | Union-find merge, 580+ predicates, manifest mode. `identity.py` found 2,006 same_as pairs (NOT yet applied as merges) |
| 4 — Wire into live Guruji | ✅ **Partially done** | `recall.py` + `factsheet.py` + `decode.py` wired. Graph injected as `{knowledge_context}` at query time (fail-graceful). **BUT:** graph files are gitignored/local-only — NOT on the prod server yet (STEP 2b of roadmap) |
| Full corpus decode | 🔶 **8 real texts decoded, 16 quarantined** | See audit results below |

### Graph health audit (2026-06-23)

A `graph_health` audit (`tools/graph_health/`, 12 tests) discovered that **16 of 24
decoded texts were fabricated** — decoded against Bhagavata chunk windows, not their
own text. Every one shared `bhagavata-1-*` chunk IDs, `bhp_` markers, and 419-420
record counts. They are 16 copies of the Bhagavata decode wearing different names.
**Quarantined** to `out/quarantine/`.

**8 real texts remain:** Bhagavata (342 records, 99% lens), Mahabharata (1989, 56%),
Ramayana (158, 99%), Brahma (117, 100%), Padma (469, 0%), Skanda (698, 0%),
Gheranda (4, 100%), Bhagavata-proof (8). `graph_manifest.json` needs rebuild from
only these 8 — current manifest (14,280 entities / 29,435 edges) is ~70% fabricated.

### LLM providers for comprehension

`comprehend.py` supports THREE providers, auto-detected from env:
- **DeepSeek** (`DEEPSEEK_API_KEY`) — the default, cheapest for bulk decode
- **Gemini** (`GEMINI_API_KEY`, model `gemini-3.5-flash`) — historical; hit the
  free-tier 429 at Bhagavata chapter 98. Still works as a fallback.
- **In-house** (`INHOUSE_DECODE=1`) — runs comprehension on **Claude itself** via
  Workflow fan-out, disk-cached. Built when Gemini quota was exhausted. No network
  call at decode time (reads from the cache). See `inhouse.py` +
  `make_inhouse_caller`.

Provider priority: `INHOUSE_DECODE=1` wins over any LLM key; otherwise first env key
found from DeepSeek → Gemini. `run.py --provider <name>` overrides.

**Gemini is NOT the primary provider anymore.** The original Bhagavata run used
Gemini; subsequent texts used DeepSeek and in-house Claude. New sessions should NOT
assume Gemini is available or needed.

## The decryption lens (what makes this *PuranGPT's* and not generic)

The comprehension prompt injects relevant **Shailendra Sharma commentary** as the
interpretive frame: don't just extract "Krishna teaches Arjuna" — extract what that
*means in Shailendra's Kriya-Yoga framework*. The lens corpus is
`sharma_texts.jsonl` (**390 chunks**: the original Gita commentary + the Awakener
EN translation, 145 chunks). It illuminates Gita-adjacent themes (karma yoga, the
gunas, dhyana) and Sharma's broader teaching across the Puranas. The lens is
pluggable: additional Sharma books widen coverage. When no relevant lens passage
exists, the read-pass falls back to a generic-but-faithful comprehension prompt.

At query time, `guruji_ram.json` (613 decoded keys — Sharma's symbolic vocabulary)
is loaded by `recall.py`, `factsheet.py`, and `decode.py` as a second grounding
layer (the *symbolic* lens vs. the *textual* lens above).

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

**WHO CONSUMES THIS GRAPH NOW — and why repair is load-bearing (added 2026-06-24).**
The graph is no longer headed only for a someday `{knowledge_context}` slot. A parallel,
already-shipping workstream (`tools/seeker_memory/`) is converging on it:
- **`{knowledge_context}`** (this workstream) — what Guruji knows about the *texts*. ✅ built
  via `recall.py`/`decode.py`/`factsheet.py`, dark in prod until the graph ships to the box
  (roadmap STEP 2b).
- **`{seeker_memory}`** (the seeker-memory workstream) — what Guruji knows about the *person*
  across sessions. **Phase 1 SHIPPED 2026-06-24** (earned warmth + distilled arc, flag OFF,
  committed `55e2338`); Phase 2 (vector retrieval of the seeker's own past words) is being built
  now and is **graph-independent** — it does NOT read this graph.
- **The JOIN (roadmap STEP 4)** — the seeker becomes a *node in this graph's entity fabric*:
  *"you stand where Arjuna stood."* THIS is where graph correctness becomes load-bearing. The
  join places a real human against real entities; a fabricated or mis-directed entity (see
  `GRAPH_CORRECTIONS.md`, [[identity-merge-rel-is-blob]]) then becomes a falsehood spoken to a
  seeker about *their own life*, not just a wrong trivia fact. Every `verify.py`-gate and
  identity fix you land is the foundation that join stands on. The slots stay SEPARATE until then
  (`SEEKER_MEMORY_DESIGN.md` decision #4) — but the graph you're repairing is the join target.

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

~5,800 tokens/chapter (2,150 input + 1,660 output + 2,000 prompt/schema). The
initial Bhagavata run used Gemini 3.5 Flash but was killed at chapter 98 by the
free-tier spending cap (429). Subsequent work used DeepSeek (~$0.14/1M input) and
in-house Claude (Workflow fan-out, disk-cached — amortized via the existing
Claude Code session, no per-call billing).

**CRITICAL cost rule:** ALWAYS test-call + read usage metadata before bulk LLM runs.
Never estimate token cost from memory — the Gemini thinking-token incident proved
that raw counts can be wildly off. See memory `feedback-cost-verification.md`.

The orchestration loop is **resumable**: chapters already in `progress.jsonl` are
skipped on re-run, so a run can be stopped, resumed, or switched to a different
provider mid-stream with zero waste.

## Files

```
tools/read_pass/
  group.py            # chunks → chapter windows (tested, 6/6)
  schema.py           # output JSON schema + validator
  comprehend.py       # window → LLM → validated record (tested, 9/9; 3 providers)
  inhouse.py          # in-house Claude decode (disk-cached, for INHOUSE_DECODE=1)
  run.py              # resumable orchestrator loop
  verify.py           # deterministic citation grounding (tested, 11/11)
  predicate.py        # verb normalization for edge predicates
  graph.py            # union-find entity merge, manifest builder
  identity.py         # typed same_as/avatar_of/aspect_of edge discovery
  resolve.py          # entity resolution helpers
  synthesize.py       # semantic teaching clustering
  insights.py         # cross-text insight extraction
  timeline.py         # Yuga-scale event placement
  guruji_ram.py       # the 613 decode keys (Sharma's symbolic vocabulary)
  recall.py           # query-time associative memory (cue → knowledge_context)
  decode.py           # the generating function (symbol → inner meaning)
  factsheet.py        # literal grounding layer (the Gandiva fix)
  ARCHITECTURE.md     # this file
  CONSCIOUSNESS_ROADMAP.md  # the standing work queue for the autonomous loop
  SEEKER_MEMORY_DESIGN.md   # design doc for cross-session person memory
  README.md           # tool descriptor + usage
  test_*.py           # tests (97+ across all modules)
  fixture_*.jsonl/json # captured real data for tests
  out/                # generated output (gitignored; 8 real texts + quarantine)
```
