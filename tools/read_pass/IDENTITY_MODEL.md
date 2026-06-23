# The Identity Model — Two-Layer Graph (inspired by Sharma's metaphysics)

## The problem we hit

A single-layer alias-union-find graph over the Puranas does the worst of both
worlds on cross-text data:
- **Over-merges the deities**: Buddha→Vishnu→Hari→Brahma all chain into one
  mega-node (648 forms) because Puranic theology *deliberately* shares hundreds
  of epithets across the supreme deities.
- **Under-merges the tail**: 11,313 raw names → 11,440 nodes (1.0x compression);
  Rāma/Rāma/rama spelling variants stay split in the long tail.

The instinct to "just merge harder" or "never merge" are both wrong. The answer
came from reading Guruji (Shailendra Sharma) on the nature of identity.

## The inspiration (Sharma, Gita commentary)

> "It is the truth of the **Time Itself** that appears as if It is **divided**
> because of Its manifestation in the form of this creation... despite being
> **standstill**. It is the Time Itself that is the creator, fosterer and
> destroyer."

> "That ultimate truth, whether you name it imperishable Brahma or Parameshwar
> or Ishwar or the Time, when It appears in the form of a human being... It does
> so on the support of [bodies]."

Sharma's metaphysics is **literally a graph topology**:
1. There is **ONE ground** (Kāla / Kūṭastha / the witnessing Self) — undivided,
   standstill, beyond the gunas.
2. It **APPEARS as many** — divided, progressional, differently-named (Brahma,
   Vishnu, Ishwar) — *because of manifestation*, not because it is actually many.
3. The epithets (Madhusūdana, Keśava, Hṛṣīkeśa) are the **same One** seen through
   different acts.

## The model: two layers that mirror the two-layer reality

### Manifest layer (nodes)
Every distinct **appearance** is its own node:
- `krishna@bhagavata`, `buddha@avatar`, `rama@ayodhya`
- This is the "divided, progressional" forms. Nothing collapses; we keep the
  charioteer-Krishna distinct from the teacher-Krishna distinct from the
  Buddha-avatar.

### Ground layer (edges)
Identity is an **edge, never a merge**:
- `same_as` — same manifest entity, different spelling/text (Rāma = rama)
- `avatar_of` — distinct manifestation of a deeper source (Buddha → Vishnu)
- `aspect_of` — a named aspect/expansion (Saṅkarṣaṇa → Vishnu)
- `epithet_of` — a pure name that resolves to a manifest entity (Madhusūdana → Krishna)

The non-duality becomes **navigable**, not collapsed. Two query directions:
- "Krishna as he appears across all texts" → manifest-layer view
- "everything that is ultimately Vishnu" → traverse ground-layer `avatar_of`/`aspect_of`

Nothing is lost. The graph faithfully encodes Sharma's "One appearing as many."

## How identity edges get drawn (the tiered pipeline)

Identity is decided in three tiers, cheapest first (Rule 0 escalation ladder):

1. **Deterministic same_as** (code, free):
   - exact normalized-name match + compatible `kind` → `same_as`
   - macron-aware (Kṛṣṇa ≠ Kṛṣṇā), so gender survives.
   This handles spelling variants. NO alias-driven merging at all.

2. **Deterministic structural edges** (code, free):
   - aliases that literally say "avatar of X" / "incarnation of X" become
     `avatar_of` edges to X (we were stripping these; now we USE them).
   - explicit `same_as`/`is` relationships the LLM already emitted.

3. **Reasoner adjudication** (deepseek-v4-pro, paid — ONLY where it matters):
   - run ONLY on high-overlap pairs (≥ N shared aliases) and mega-clusters,
     NOT all 22K overlap pairs.
   - returns the typed edge: same_entity / avatar_relation / aspect / coincidental.
   - **Cost reality (measured 2026-06-23):** a 3-pair call = 32K prompt tokens,
     ~$0.06, because `build_prompt` dumps every form. Full 22K-pair run ≈ **$450**
     (NOT the $6.70 I first guessed — prompt bloat dominates). So we MUST:
     (a) cap to the worst ~200–400 pairs, and (b) trim the prompt to send only
     a sample of forms + kinds + chapters, not the whole 648-form dump.
     Capped run ≈ **$2–4**, which is fine.

## Why this is correct (not just convenient)

- It is **faithful to the source's own metaphysics** — the graph's shape is the
  doctrine, per daddy's instruction to find the model IN the text.
- It is **lossless** — every manifestation and every identity claim is preserved
  and queryable. We never destroy "Krishna-as-charioteer ≠ Krishna-as-Brahman."
- It is **honest about uncertainty** — a `coincidental` verdict (Kṛṣṇā=Draupadī)
  is recorded as the absence of an identity edge, not a silent merge.
- It **separates extraction from judgment** — the cheap model extracts
  manifestations; the reasoner only draws the hard identity edges.

## Status
- IDEA + measured cost. Implementation: `identity.py` (next), replacing the
  alias-union-find merge in `graph.py` with same_as/avatar_of edge construction.
- Tests-first per Rule 0 precond A.
