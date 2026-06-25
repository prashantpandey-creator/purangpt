# Jarvis — Design Doc

> ## ⚠️ STATUS CORRECTION (2026-06-23) — READ THIS FIRST
>
> **This doc's premise was wrong.** It was written as if the comprehension engine
> needed building (phases J0 "lift to corpus profile" + J1 "build_read_model").
> In reality that engine **already exists and is tested**, and **22 corpora are
> already comprehended** — it shipped from the merged `Jarvis -` session (PR #5).
> See `read-pass-comprehension-project.md` in memory for the true current state.
>
> What's already built (do NOT rebuild — §3/§4 below are OBSOLETE):
> - `run.py`/`group.py` — already corpus-agnostic (any chunk file via `--input`).
> - `graph.py` — the "read model" already: union-find entity merge, alias-overlap
>   (Krishna/Vishnu/Hari handled), 580+ discovered predicates, lineage/curse
>   traversal, incompatible-kind guards. Plus `identity.py` (two-layer manifest/
>   ground), `synthesize.py`, `timeline.py`, `guruji_ram.py`, etc.
>
> **What is genuinely unbuilt = §5, the Storyteller** — and per the 2026-06-23
> coherence decision it is a **MODE of the live Workspace doc-reader** (branch
> `claude/content-explorer`, see PROJECT_LEDGER.md), NOT a standalone app. The
> "PDF/book-reader" idea IS that Workspace reader. Coherence model: ONE
> comprehension trunk + sibling views (chat/comic/storyteller/trivia), none
> editing the graph (declared in `views/COMIC_PACKET_IDEA.md`).
>
> **The one real engine gap for the Storyteller:** `graph.py` tracks `chapters`
> (a set) but not *ordered* first-appearance. The spoiler gate needs `first_seen`
> ordered — a small surgical add to `graph.py` (added generally, not view-
> specifically, per the views rule). Spoiler = HARD-GATE (locked, see §7).
>
> Read §5 + §7 (Storyteller + locked decisions). Treat §3/§4 as historical.

---

> **Original status (now superseded):** proposal generalizing `tools/read_pass/`
> into a corpus-agnostic engine + a stateful Storyteller client.

---

## 1. The one-line thesis

**read_pass already is Jarvis's brain — it's just hardwired to one corpus and one
lens, and it has no query-time read model.** Jarvis = read_pass with three things
added:

1. **A corpus profile** — the corpus/lens/segmentation-specific knobs pulled out
   into config, so the *same* comprehension code runs on Ramayana, Mahabharata,
   or a non-Sanskrit book.
2. **A read model** — the per-chapter JSONL records merged into a queryable
   *comprehension graph* (entities deduped across chapters, relationships joined,
   teachings indexed) that a client can ask "who is X / why did Y happen / where
   are we" against.
3. **The Storyteller** — a stateful narration client that walks the corpus in
   reading order, tracks *narrative position*, and answers interrupts against the
   read model **without spoiling what's ahead**.

Nothing here replaces read_pass's record schema. We build *around* it.

```
                       ┌─────────────────────────────────────────┐
   raw corpus ───────► │  JARVIS COMPREHENSION (offline, batch)   │
   + corpus profile    │  group → comprehend(lens) → verify       │  ← read_pass, generalized
                       │  emits: per-segment records (JSONL)      │
                       └───────────────────┬─────────────────────┘
                                           │  build_read_model
                                           ▼
                       ┌─────────────────────────────────────────┐
                       │  COMPREHENSION GRAPH (read model)        │
                       │  entities (deduped) · relationships ·    │
                       │  story arcs (ordered) · teachings ·      │
                       │  every node → verse_ranges provenance    │
                       └──────────┬───────────────────┬──────────┘
                                  │                    │
                        query-time│              narration│
                                  ▼                    ▼
                   ┌──────────────────────┐  ┌───────────────────────────┐
                   │  {knowledge_context} │  │  STORYTELLER (stateful)   │
                   │  injected into the   │  │  position cursor · told[] │
                   │  existing /api/chat  │  │  interrupt resolver       │
                   │  (Phase 4 hookpoint) │  │  spoiler-safe answers     │
                   └──────────────────────┘  └───────────────────────────┘
```

---

## 2. What stays exactly as-is (do not touch)

- **The per-segment record schema** (`tools/read_pass/schema.py`):
  `chapter_summary`, `entities[]`, `relationships[]`, `story{}`, `teachings[]`,
  `_provenance{}`. Every node carries `verse_ranges`. This is the contract; the
  read model and storyteller are pure *consumers* of it.
- **The three-stage pipeline:** `group.py` → `comprehend.py` → `verify.py`,
  orchestrated by `run.py`, resumable via JSONL. Proven (95% grounded, 97/338
  Bhagavata chapters done).
- **Deterministic cite-verification** post-LLM. No hallucinated node reaches the
  read model — `verify.py` already guarantees this.
- **The tools convention:** JSON envelope, `--json`, co-located
  `test_*.py` + fixtures, README with failure table.

If a change would alter the record schema, it's the wrong change — extend the
read model instead.

---

## 3. What gets generalized: the corpus profile

Today these are hardcoded into read_pass / the data pipeline. Jarvis pulls them
into one declarative profile so a new corpus is *config, not a fork*.

```jsonc
// tools/jarvis/profiles/bhagavata.json   (the existing run, captured as config)
{
  "corpus_id": "bhagavata",
  "display_name": "Bhagavata Purana",
  "source_chunks": "data/chunks/bhagavata.jsonl",

  "segmentation": {
    "strategy": "contiguous_chapter_runs",   // group.py's current algorithm
    "key_field": "chapter",                   // the field whose contiguous runs = one window
    "order_field": "seq"                      // monotonic global sequence
  },

  "cite_marker": {
    "pattern": "bhp_\\d{2}\\.\\d{2}\\.\\d{3}",  // verify.py checks these exist in the window
    "label_field": "verse_range"
  },

  "lens": {
    "id": "sharma_kriya_yoga",
    "texts": "data/chunks/sharma_texts.jsonl",  // optional; null = literal comprehension, no lens
    "applies_when": "spiritual"                  // lens_note left empty when lens doesn't apply
  },

  "reading_order": "seq"   // how the storyteller walks the corpus front-to-back
}
```

**Generic vs corpus-specific, made explicit:**

| Knob | Generic (engine) | Per-profile |
|------|------------------|-------------|
| Window algorithm | yes (`group.py`) | which field defines a segment |
| LLM comprehension prompt | yes (`comprehend.py`) | the lens text + whether a lens applies |
| Cite verification | yes (`verify.py`) | the cite-marker regex |
| Resumable JSONL loop | yes (`run.py`) | output tag / paths |
| Reading order | yes | which field is the spine |

A non-Sanskrit book (no `bhp_` markers, no Sharma lens) becomes: a different
`cite_marker.pattern`, `lens: null`, and a `segmentation.strategy` suited to its
structure. **Zero engine code changes** is the bar. If a new corpus needs an
engine change, that change is a new generic capability, gated by the profile.

> **Migration note:** the *first* PR just lifts today's hardcoded Bhagavata
> behavior into `profiles/bhagavata.json` and proves the run is byte-identical
> against the 97 existing records as a fixture. No new corpus until that passes.

---

## 4. The read model — `build_read_model` (new tool)

The per-segment JSONL is write-optimized (one record per chapter, append-only,
resumable). It is **not** queryable: "who is Narada" is scattered across N
chapters; "why did Daksha curse" needs relationships joined across segments.

`tools/jarvis/build_read_model/` folds the JSONL into a queryable graph. Pure
deterministic transform → testable → Rule-0 script, **no LLM**.

```jsonc
// output: comprehension graph (one per corpus)
{
  "corpus_id": "bhagavata",
  "entities": [
    {
      "id": "narada",                    // slug, stable across the corpus
      "name": "Narada",
      "kind": "sage",
      "aliases": ["Narada Muni", "Devarshi Narada"],
      "first_seen": { "segment": 1, "order": 12 },   // for spoiler-gating
      "appearances": [                   // every segment + verse_ranges it shows in
        { "segment": 1, "verse_ranges": ["bhp_01.05.001", ...] },
        { "segment": 7, "verse_ranges": [...] }
      ]
    }
  ],
  "relationships": [
    { "src": "narada", "rel": "teaches", "dst": "vyasa",
      "first_seen": { "segment": 1, "order": 30 },
      "evidence": [{ "segment": 1, "verse_ranges": ["bhp_01.05.021"] }] }
  ],
  "arcs": [                              // story{} records, in reading order
    { "segment": 1, "title": "The Sages' Inquiry", "arc": "...",
      "characters": ["suta", "saunaka"], "timeline_note": "..." }
  ],
  "teachings": [
    { "id": "t_0001", "segment": 1, "teaching": "...", "lens_note": "...",
      "verse_ranges": ["bhp_01.03.001"] }
  ],
  "_meta": { "segments": 97, "entities": 412, "built_from": "bhagavata_v2.records.jsonl" }
}
```

**The two design decisions that matter here:**

- **Entity dedup is by `name` + `aliases`, case/diacritic-normalized — NOT by an
  LLM.** read_pass already emits aliases per chapter; we union them. Conflicts
  (two real entities sharing a name) are *surfaced in the envelope's `metadata`*,
  not silently merged. (Same lesson as `sse_contract_check/FINDINGS.md`: a clean
  envelope around a wrong merge is still wrong — so dedup is tested against real
  captured records as fixtures, and ambiguous merges are reported, not buried.)
- **`first_seen` on every node is the spoiler spine.** It's what lets the
  storyteller answer "who is this" using only what's been revealed *up to the
  current position*. Without it, every answer is a potential spoiler.

This is the node that becomes Phase 4's `{knowledge_context}` — the read model
is corpus-wide, and at query time we slice it to the entities/relationships
relevant to the retrieved passages, then inject alongside `{context}`.

---

## 5. The Storyteller — the hard part is state, not narration

LLMs narrate fine. What makes "start the Ramayana… wait, who is this… where are
we" work is a **session state machine over the read model**. State lives in the
existing `chat_sessions` table — we reuse `messages` JSONB and add a
`narrative_state` JSONB column (additive, doesn't disturb the chatbot).

```jsonc
// chat_sessions.narrative_state
{
  "corpus_id": "ramayana",
  "cursor": { "segment": 14, "order": 318 },   // where narration has reached
  "told": [1,2,3, ... ,14],                     // segments already narrated
  "revealed_entities": ["rama","sita","dasharatha", ...],  // for spoiler-gating
  "revealed_facts": ["t_0001","t_0007"],        // teachings/relationships surfaced so far
  "mode": "narrating",                          // narrating | paused | answering_aside
  "last_position_summary": "Rama has just been exiled; the cursor sits at the start of the forest years."
}
```

### The interrupt resolver (the core loop)

When the listener interrupts, we **classify the intent deterministically**
(keyword + light intent match — a decision tree, so a Rule-0 script, not a
sub-agent), then resolve against the read model *clamped to the cursor*:

| Interrupt | Resolution (all spoiler-gated by `cursor` + `first_seen`) |
|-----------|-----------------------------------------------------------|
| "where are we / refresh me" | Return `last_position_summary` + a recap synthesized from `told[]` arcs **only**. No look-ahead. |
| "who is X" | Look up entity `X`; answer using appearances with `first_seen ≤ cursor`. If `first_seen > cursor` → "they haven't entered the story yet" (don't spoil). |
| "why did X do Y" | Walk relationships into/out of `X` with `first_seen ≤ cursor`; cite `verse_ranges`. If the cause is ahead → say it's not yet revealed. |
| "go back / retell" | Move cursor back; keep `told[]` (so future answers still know it). |
| "continue" | Resume narration from `cursor`. |

**The spoiler gate is the whole product.** A storyteller that answers "who is
this" by dumping the character's entire arc — including their death three books
later — is worse than no storyteller. Every resolver clamps to
`first_seen ≤ cursor`. This is tested with fixture states: cursor at segment 5,
ask about an entity introduced at segment 30 → must refuse to reveal.

### Why this rides on the existing chat infra

- **Narration & answers go through the same `/api/chat` SSE path** (`event_gen`
  in `main.py`) — same streaming, same auth, same `ChatEvent` union the frontend
  already parses. The storyteller is a *prompt + injected `narrative_state` +
  read-model slice*, not a new transport.
- **Session persistence is already solved** by `session_manager.py`
  (`get_session`/`save_message`). We add `narrative_state` read/write helpers
  beside them.
- A new `QueryMode` (`"storyteller"`) joins `guide`/`research` — and per the
  cross-app rule, it must be added in **both** `api.ts`'s `QueryMode` and
  `main.py`'s `PROMPTS` registry, in sync.

---

## 6. Build order (each phase ships green before the next)

| Phase | Deliverable | Gate |
|-------|-------------|------|
| **J0** | `profiles/bhagavata.json` + engine reads profile instead of hardcoded knobs | Re-run reproduces the 97 existing records byte-identical (fixture test) |
| **J1** | `build_read_model` tool | Tested against captured real records; dedup + `first_seen` correct; ambiguous merges reported not buried |
| **J2** | Storyteller state machine + interrupt resolver (offline, no UI) | Fixture-state tests incl. the spoiler-gate refusal case |
| **J3** | `storyteller` QueryMode wired into `/api/chat`; `narrative_state` column | `sse_contract_check` green; `npx tsc --noEmit` clean; modes in sync across apps |
| **J4** | Frontend storyteller UI (narrate / interrupt / resume) | Verified in preview |
| **(later)** | Second corpus (Ramayana) — proves corpus-agnosticism | New profile only, zero engine change |

Each Jarvis tool follows the existing convention: `cp -r tools/_template
tools/jarvis/<name>`, JSON envelope, tests-first with **real captured records as
fixtures** (not synthetic — that's the read_pass lesson).

---

## 7. Decisions (locked)

1. **Spoiler default: HARD-GATE.** The storyteller never reveals anything ahead
   of the cursor. Answers clamp to `first_seen ≤ cursor`; when the answer is
   ahead, it says "they haven't entered the story yet" and offers nothing more.
   No "want me to spoil?" prompt — that breaks the spell. This is *the* product
   decision; the spoiler-gate refusal case is a required test at J2.
2. **Read model storage: JSON ARTIFACT for J1.** A JSON/JSONL file beside the
   read_pass records — matches convention, no DB dependency. Migrate to
   `purangpt-pgvector` at **J3**, when `{knowledge_context}` goes live and needs
   to join with vector search. (The build_read_model tool's output is the same
   shape either way, so the migration is a sink swap, not a rewrite.)

### Still open (decide before that phase, not now)

- **Segmentation for non-chapter corpora** (a regular novel): add a second
  `segmentation.strategy` only when a real non-Purana corpus arrives.
  *(Recommendation: stay chapter-shaped; YAGNI — revisit at the "second corpus"
  phase, not before.)*
