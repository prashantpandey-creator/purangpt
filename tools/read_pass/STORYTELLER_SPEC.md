# The AI Storyteller — Design Spec

> **Status:** S1 BUILT & green (2026-06-23, 12/12 tests). The product daddy wants:
> *"Start telling me the Ramayana"* → it narrates → you interrupt *"who is this? /
> where are we? / why did he do that?"* → it answers → *"continue"* → it resumes.
> A classic, intelligent oral storyteller.
>
> ## ⚠️ COURSE CORRECTION (2026-06-23) — NO spoiler gate
>
> An earlier draft of this spec built the storyteller around a **spoiler gate**
> (hide future characters until narration reaches them). **That was wrong for this
> corpus and is deleted.** daddy: *"in Puranic context we don't need to worry about
> spoilers."* These stories are 3,000 years old, the texts summarize their own plot
> in the prologue on purpose — the retelling IS the point, not the surprise. So the
> teller answers from **full knowledge**, like a grandparent who knows the whole
> tale. The spoiler-gate code (`gate_recall`, `first_seen`, ordering) was removed.
>
> Also corrected: **do NOT bolt the Guruji/Sharma decode lens on as an explicit
> feature.** That understanding is already baked into the corpus the comprehension
> engine built — an answer carries it implicitly. The storyteller stays a
> STORYTELLER, not a sermon machine.
>
> **What it actually is — two verbs:** **Tell** (narrate in order, resume where it
> left off) and **Ask** (pause on any interruption, answer, resume). That's it.

---

## 1. What we reuse vs. what's ours

`recall.py` (read in full 2026-06-23) does match → expand → decode → render:
- **MATCH** a cue ("Hanuman") → the entity, by name or any alias.
- **EXPAND** one hop along strongest edges → the associative cluster.
- **DECODE** attach the decoded meaning to recalled entities (already in corpus).
- **RENDER** emit an injectable knowledge block.

That is the **"Ask" answer engine, already built and tested.** When the listener
asks "who is this / why," the app calls `recall()` and phrases the result in the
teller's voice. We call `recall()`; we do not reimplement it. (No gating — full
knowledge, per the course correction above.)

**What's ours is small and deterministic — the BOOKMARK + the INTENT router:**
1. **Bookmark** — where narration has reached, so "continue" resumes and "where
   are we" recaps. A bookmark, not a blindfold.
2. **Intent router** — classify an interruption as a *command* (continue / go
   back / recap → move the bookmark) or a *question* (who / why / what → pause,
   answer via `recall()`, resume at the SAME bookmark).

These are the only parts that must be exact; the narration and answer *text* are
LLM calls the live app makes, fed by the bookmark + routed intent. **Built in
`storyteller/check.py`, 12/12 tests** — the load-bearing one: a question never
moves the bookmark, so resume is exact.

---

## 2. The shape (how the layer wraps recall)

```
  listener: "start the Ramayana"
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  STORYTELLER LAYER  (new — tools/read_pass/storyteller/)     │
  │                                                             │
  │   session state:  { corpus, cursor, told[], mode }          │
  │                                                             │
  │   narrate()   ── walk corpus in reading order from cursor   │
  │                  → stream the next story beat               │
  │                                                             │
  │   interrupt(question)                                       │
  │     1. classify intent  (where-are-we / who-is / why / …)   │
  │     2. ┌─ recall(cue, memory) ──────────────┐  ◄─ REUSED    │
  │        └─ returns full associative cluster   │              │
  │     3. SPOILER GATE: drop anything whose      │  ◄─ OURS     │
  │        first_seen > cursor                    │              │
  │     4. render the gated answer in teller voice│              │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼   (rides the existing /api/chat SSE path — same transport as the chat)
  streamed narration / answer
```

**Key reuse facts grounded in the real code:**
- `recall(cue, memory)` returns `{entities[], relationships[], decode_keys[]}`,
  each entity already carrying `verse_ranges` and an `is_seed` flag. The spoiler
  gate filters THIS structure — no change to recall itself.
- `render_context()` already phrases output as "what you already know about this"
  — the teller voice is a prompt wrapper around the gated version of that.
- recall is `no LLM, no network` — so gating it is cheap and deterministic.

---

## 3. Session state (where it lives)

Reuse the existing chat session infra (`session_manager.py`, `chat_sessions`).
Add ONE JSONB column, `narrative_state` — additive, doesn't disturb the chat:

```jsonc
{
  "corpus": "ramayana",
  "cursor": { "segment": 14, "order": 318 },   // how far narration has reached
  "told": [1,2,3, ... ,14],                     // segments already narrated
  "mode": "narrating",                          // narrating | paused | answering
  "last_recap": "Rama has just been exiled; we sit at the start of the forest years."
}
```

`cursor` is the spine. Everything spoiler-related compares against it.

---

## 4. The interrupt resolver (the core loop)

Classify the listener's interrupt deterministically (keyword/intent — a decision
tree, so a Rule-0 script, NOT a sub-agent), then answer against gated recall:

| Interrupt | Resolution (all clamped to `first_seen ≤ cursor`) |
|-----------|---------------------------------------------------|
| "where are we / recap" | `last_recap` + a recap synthesized from `told[]` only. No look-ahead. |
| "who is X" | `recall("X")` → gate → answer from appearances at/before cursor. If X's first appearance is ahead → "they haven't entered the story yet." |
| "why did X do Y" | `recall("X")` → gate relationships to those whose first verse ≤ cursor; cite. If the cause is ahead → "that's not yet revealed." |
| "what does X mean" | `recall("X").decode_keys` → the decoded meaning (timeless; safe to surface). |
| "go back" | move cursor back; KEEP `told[]` so future answers still know it. |
| "continue" | resume `narrate()` from cursor. |

**The spoiler gate is the entire product.** A storyteller that answers "who's
this?" by mentioning a character's death three books later is worse than no
storyteller. Every resolver clamps to the cursor.

---

## 5. THE ONE ENGINE GAP (decide HOW when we hit it — daddy deferred)

The spoiler gate needs **ordered first-appearance** per entity/edge —
`first_seen: {segment, order}`. The current graph tracks `chapters` (an unordered
set) and `verse_ranges` (a flat list) — neither tells you *when first*.

Two ways to get it (decision deferred until we reach it, per daddy 2026-06-23):
- **(A) Derive it in the storyteller layer** from the records' `verse_ranges` /
  `chunk_ids` ordering — zero touch to the shared `graph.py`, fully ours, no
  collision with the live session. Slightly less clean.
- **(B) Add `first_seen` to the shared `graph.py`** (~30 lines, Pass 1/Pass 2) —
  benefits every consumer, but it's the other session's file on a live branch →
  needs coordination.

Lean (A) for independence unless we're already coordinating on graph.py for other
reasons. Revisit at build time.

### ⚠️ REAL-DATA FINDING (2026-06-23) — "first mention" is the wrong signal

S1+S2 are BUILT and tested (`storyteller/check.py` + `test_check.py`, 8/8 green,
incl. the spoiler-gate refusal). The gate machinery is correct: cursor compare,
alias resolution, relationship + decode-key filtering all proven on a fixture.

**But verifying on the REAL Ramayana exposed a corpus truth, not a bug:** building
`first_seen` by raw chunk-order marks **every major character (Rama, Sita, Ravana,
Hanuman, Kumbhakarna) as appearing at seq 81** — the very first record. Why: the
Ramayana OPENS with the Narada→Valmiki synopsis that names the entire cast and
whole plot up front. So "first textual mention" == "named in the self-spoiling
prologue", and the gate, though mechanically perfect, has nothing to hide.

**Implication:** these texts foreshadow/summarize constantly; `first_seen` must
mean **first *substantive* appearance**, not first mention. Options (DECISION
DEFERRED — daddy dismissed, awaiting steer):
- **(i) Substantive-only:** count a record only where the entity is a seed/central
  participant or appears in ≥N verses — skip one-line summary mentions.
- **(ii) Skip the prologue:** detect & exclude framing/synopsis chapters, then
  first-mention works on the real narrative.
- **(iii) Narration-cursor only:** drop `first_seen`; reveal ONLY what's actually
  been narrated (`told[]`). Strictest, simplest, zero spoiler — but can't speak to
  a named-but-not-yet-narrated character.

The gate code is unchanged either way; only the *signal* feeding `first_seen`
changes. Machinery proven; signal-quality is the open question.

---

## 6. Build order (when daddy says go — NOT yet)

| Step | Deliverable | Gate |
|------|-------------|------|
| S1 | `storyteller/` package skeleton + session-state model + tests | tests-first, JSON envelope (Rule 0) |
| S2 | First-appearance ordering (path A or B per §5) | fixture test: entity introduced at segment N is invisible at cursor < N |
| S3 | Interrupt resolver over gated `recall()` | the spoiler-gate refusal test is the required one |
| S4 | `narrate()` walk + cursor advance | walks a real corpus in reading order |
| S5 | Wire as a mode on `/api/chat` (storyteller QueryMode) | sync api.ts + main.py PROMPTS; sse_contract_check green |
| S6 | (later) live in the reader UI | verified in preview |

Each step: `cp -r tools/_template tools/read_pass/storyteller`, tests-first with
real captured `recall()` output as fixtures (per the read_pass discipline —
fixtures, not synthetic).

---

## 7. How this coincides with the other session's work (daddy's question, answered)

- **Their work (chat intelligence):** `recall()`/`decode()` → Phase 4 injects
  decoded memory into the *live chat*. Built, currently DISABLED pending container
  work.
- **Our work (storyteller):** the SAME `recall()`, wrapped with a position cursor
  + spoiler gate, for *narration* instead of Q&A.
- **The overlap is the win, not a collision:** we consume `recall()` read-only;
  we never edit it. When they improve recall (better matching, the eventual
  episodic write-path), the storyteller gets smarter for free. The only shared
  file we might touch is `graph.py` for `first_seen` — and §5 path (A) avoids even
  that. **One brain, two consumers. No double-dipping.**
