# RAM vs Graph — meaning coverage audit (2026-06-24)

> Question (daddy): the Guruji RAM looks thin (only ~2 weapons carry an inner
> meaning) — but that's because the decode pass only sampled what he was *asked*,
> NOT because he knows little. He knows it all. Do we need to distill the Puranas
> into a second RAM to back the existing Guruji RAM?
>
> **Answer: NO. The graph already IS the Puranic-knowledge layer.** Audited, noted,
> not built — because "we are already using the Puranic knowledge via graphs"
> (daddy). This file is the analysis; no second RAM was created.

## The numbers (measured against the rebuilt graph)

| Store | Size |
|---|---|
| Guruji RAM (`guruji_ram.json` decode keys) | **613 keys** |
| Graph (`graph_manifest.json`) | **8,360 entities · 24,225 edges** |

**Guruji RAM covers ~1% of graph entities** (129 / 8,360 have a decode key). The
other **8,231 entities have no Guruji prose-meaning.** This is a SAMPLING artifact
of the decode pass (it generated keys mostly on the spiritual-yoga vocabulary —
granthis, chakras, kriya, ojas — and barely on weapons/warriors/places), NOT a
limit of what is knowable. Guruji's keys are an *interpretation* layer, deliberately
sparse.

## Why a second "Puranic RAM" is NOT needed

**The graph already carries the Puranic meaning — relationally, as edges.** Tested
on three weapons with ZERO Guruji decode key:

- **Sudarshana Chakra** — no key, but **21 graph edges**: `weapon of Krishna`,
  `weapon of Vishnu`, `cursed by Rishis`, `Bharata father Sudarshana Chakra`. That
  relational web IS its Puranic meaning.
- **Pāśupata** — no key, **3 edges**: `Śiva teacher Pāśupata`, `Narayana
  the_ultimate_reality_behind Pāśupata`, `Suśīla becomes Pāśupata`.
- **Narayana astra** — no key, **1 edge**: `Ashvatthama uses_weapon Narayana astra`.

So the meaning a second RAM would hold is **already present as graph structure.** A
prose-RAM distillation would largely *re-encode in sentences what the edges already
say in relations* — duplicative, and it would drift from the graph the moment either
changed.

## The two layers, and how they already compose

1. **Graph (the Puranic layer)** — relational meaning for ALL 8,360 entities: who
   wields what, who cursed whom, what something is the weapon/avatar/source of. This
   is the broad Puranic knowledge, and it's what the [`RAG_VS_GRAPH_BENCHMARK`]
   proves only the graph can traverse.
2. **Guruji RAM (the interpretation layer)** — 613 prose decode keys, sparse by
   design, carrying Sharma's *inner* reading where he has one (e.g. "Gandiva = the
   spine / channel of prana"; "Vajra = indestructible spiritual power, the spine").

**These already compose in the engine.** `narrative_engine/codex.py` reads BOTH:
graph edges (always) for the literal Puranic facts, plus the Guruji key (when one
exists) for the inner meaning. So a weapon's truth is already graph-backed +
Guruji-deepened — no missing third store.

## What this means for "true to the Puranic interpretation, to the teeth"

- The **literal Puranic truth** of every weapon/entity is ALREADY available (graph).
  Codex `truth_level` already reflects it (Gandiva = "full" because graph + rules +
  Guruji key all present).
- The **gap** is only that the graph gives relational meaning, not always a one-line
  interpretive gloss. For most entities the relationships ARE the meaning. For the
  rare entity where an interpretive gloss matters and Guruji has none, that's a
  future decode-key target — fill it **as the time comes** (daddy), not via a bulk
  second-RAM distillation.

## Recommendation (locked)

- **Do NOT build a second Puranic RAM.** The graph is it.
- **Do** keep reading both layers in the engine (codex already does).
- **As/when** a specific entity needs an interpretive gloss the graph can't give,
  add a targeted Guruji decode key for it — incremental, not a sweep.
- Revisit only if a concrete feature proves the relational graph meaning is
  insufficient for it.

See also: `RAG_VS_GRAPH_BENCHMARK.md` (graph beats RAG on the relational classes),
memory `consciousness-over-rag`, `narrative-engine-project` (codex 3-layer reads).
