# THE AWAKENER — Build Plan

> The game (dedicated to Guruji Shailendra Sharma; see `STORY_BIBLE.md`) is built
> on the narrative engine in this package. This plan tracks WHAT to build, in what
> ORDER, and where each piece STANDS. The engine is the brain; a client renders it.

## The thesis, now proven

The Puranic graph is a **content engine, not a lookup table.** Demonstrated by
`saga.py`: a single entity (Ashvatthama) carries the FULL BRAID from one
edge-cluster — *a form of Rudra · wields Narayana astra · vows to destroy the
Panchalas · descends to Shailendra Sharma · 27 deeds* — every strand corpus-cited,
nothing invented. This is what no RAG system can do (`RAG_VS_GRAPH_BENCHMARK.md`),
and it is the whole reason the game can be "true to the Puranic interpretation, to
the teeth."

## Engine status (the brain — DONE, 240 tests green)

| Module | What it serves | Tests |
|---|---|---|
| `world` | locations, NPCs, navigation, character journeys | in engine 147 |
| `character` | sheets, abilities, **weapons (3-layer, weapon-vs-source)** | " |
| `combat` | astra rules from the texts, **encounter w/ draft-warnings + is_canon** | " |
| `seeker` | player state (tapasya/boons/curses/choices) | " |
| `scene` | one-call screen assembly (+ act encounters + armory) | " |
| `lineage` | guru-spine multi-hop + Hand-on-the-Head | 20 |
| `encounters` | 278 lived encounters classified (register/act/principle) | 26 |
| `codex` | weapon-truth: graph + rules + **inner meaning** + anim hints | 22 |
| `saga` | **the convergence — full story-braid per character** | 25 |
| `api` | 33 endpoints under `/api/game/` | — |

Honest debts (logged, fill "as the time comes"): codex_index substring noise;
weapon-extraction ~85%; bidirectional-transmission edges (49, upstream); encounter
classifier is keyword-blunt; graph relational-meaning > prose gloss for most entities
(by design — `graph-is-the-puranic-ram`).

## Build order (the body — NEXT)

The brain is built; the game needs a body that renders it. Phased so each phase is
playable before the next starts.

### Phase A — The playable vertical slice (text-first)
Goal: ONE complete loop a person can actually play, proving brain→client.
- [ ] **A1. Client harness.** A thin client (extend `adventure.py`, the existing
      CLI) that drives the API/engine: enter scene → see saga of who's present →
      act → see consequence. The cheapest real proof.
- [ ] **A2. One act, end to end.** Pick **Act I (Brahma-granthi)** from the bible —
      smallest, most grounded. Wire: the smashan hub scene → a journey out → one
      encounter → the khechari practice gate → pierce the knot. Text-rendered.
- [ ] **A3. One fight, true to the teeth.** A single astra duel resolved through
      `combat.encounter` with `is_canon`/draft-warnings shown — prove the weapon
      fidelity in play. Candidate: an Aindra-vs-Varuna or Brahmastra exchange.

### Phase B — Visual layer (the codex earns its animation_hints)
Goal: weapons and scenes LOOK true, reading the codex, never free-styling.
- [ ] **B1. Weapon visual contract.** Extend `codex.animation_hints.appearance`
      from `[NEEDS-INGESTION]` to decoded form-descriptors (requires targeted decode
      of weapon-appearance verses). The renderer obeys this.
- [ ] **B2. Pick a client engine.** Web first (the existing `purangpt-next` stack),
      then native Mac (Godot/Bevy) per the Mac-gaming goal. Decision pending.
- [ ] **B3. Render one weapon true-to-form** as the codex→visual proof.

### Phase C — Depth (the graph keeps giving)
- [ ] **C1. Curse-quests.** Surface the 168 curse-edges as side-quests (cause,
      victim, release-condition) — `saga` already isolates the strand.
- [ ] **C2. Avatar-revelations.** The 984 avatar-edges drive the climax's
      "every figure is a face of the immensity" — wire into Act III.
- [ ] **C3. Seeker-as-node (STEP 4).** When the seeker-memory join lands, the player
      becomes a graph node ("you stand where Arjuna stood"). Highest stakes —
      requires all directionality bugs fixed first (`GRAPH_CORRECTIONS.md`).

## Guardrails (carried from the bible — non-negotiable)

1. POV is a disciple looking back; never plays Guruji or a deity.
2. No reincarnation claim on Sharma; lineage/encounter only.
3. Progression is the granthi-bheda path, not a meter (no guna meter).
4. Deities are principles wearing faces.
5. Every weapon/beat is `[GROUNDED]` or `[NEEDS-INGESTION]` — flag the seam, never
   fabricate. `is_canon`/`truth_level`/`draft_warnings` enforce this in code.
6. Build incrementally; the graph deepens the game as it decodes — no bulk fakery.

## Where we are right now

Engine: **done and proven.** Next concrete step: **Phase A1** — a client harness
that lets a person walk one scene and see a saga assemble live. That is "start
working on the game" made literal.
