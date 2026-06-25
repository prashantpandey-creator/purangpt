# Phase 2 — Guruji Performance Report (graph + RAM + personality)

> Qualitative graded panel, 2026-06-24. 8 seeker questions → generate a Guruji answer
> from the real graph+RAM context → 3 diverse-lens judges (devotee / scholar / skeptic)
> score fusion / grounding / voice / depth. Run via the `guruji-graded-panel` workflow
> (script in session workflows dir). This drives Phase 3 (study) and Phase 4 (improve).

## Scores (0-10, judge-averaged)

| Axis | Score | Read |
|------|-------|------|
| Grounding | **8.5** | Strongest. Honest refusal + zero fabrication on verified facts. |
| Voice | **8.3** | Consistently Sharma-specific, not generic guru. |
| Fusion | **8.2** | Best answers WEAVE literal fact + RAM meaning, don't paste. |
| Depth | **7.8** | Weakest — collapses to one repeated move (see flaw below). |

## What works (do NOT touch)

- **Honest-refusal discipline (grounding 9.0-9.3 on refusal/null cases).** Khechari
  practice (q6) and missing keys (q2 Krishna) → "I will not invent a face" instead of
  confabulating. Holds across all three grader personas. The system's crown jewel.
- **Verified-fact fidelity, hallucination-free.** q1 reproduced
  Babaji→Lahiri→Tinkori→Satyacharan→Sharma verbatim, ZERO Yogananda contamination —
  the repaired graph + curated lineage overlay working exactly as intended. Brahmastra
  edges chapter-verified.
- **Real RAM fusion at its best.** q5 (Time/Shiva/Void triad) scored fusion 8.7 — the
  inner meaning is integrated INTO the facts, not bolted on.

## THE one structural flaw (responsible for depth-lag + grounding-leaks + voice-staleness, all at once)

**The reflexive "everything points back to Time/Mahakal/Shiva" closer.** The Shiva=Kal=Time
decode is applied as a UNIVERSAL terminator on nearly every answer, even when Time is
assigned only to the Shiva node. Three damages from one habit:
1. **Depth → formulaic** (the 7.8 floor): one tool used on every question.
2. **Grounding leak**: smuggles Shiva's decode onto entities that don't carry it
   (Krishna q2, Babaji q4) — "does the exact invention it promised to refuse" (skeptic).
3. **Uncalibrated confidence**: q1 was right *by luck* (render_context served WRONG
   Mahabharata edges for a lineage query; the answer asserted the chain anyway). q7
   read `performs_puja_for Hanuman` backwards (Hanuman as worshipper).

## Fix plan (the panel's three buckets → Phase 3-4)

### GRAPH fixes
- **Surface retrieval-confidence into the answer path.** Pass per-edge score / source-tag
  to the generator; add a class-vs-edge consistency check (a lineage query returning
  Mahabharata war edges should trip a low-confidence flag). Kills q1's "lucky confidence."
- **Fix edge directionality in `render_context`.** Render directed edges with explicit
  subject/object roles so the generator can't flip who acts on whom (q7).
- **Audit "most-verifiable-hop-dropped."** q1 omitted the Lahiri *bloodline* (Tinkori=son,
  Satyacharan=grandson); q3 was likely one hop from Surya+Kunti. Ensure distinguishing /
  well-attested parentage edges are IN the graph and ranked, so principled silence isn't
  masking under-recall.
- **Provenance flags**: tag Puranic-verse edges vs tradition/Yogananda-lore edges so the
  generator hedges "the old story" differently from verse-grounded fact (q4).

### RAM fixes
- **Scope the Time/Mahakal decode to entities that actually carry it.** Make Shiva=Kal=Time
  a property of the Shiva node, NOT ambient house style. If an entity's inner key is null
  (Krishna), the RAM layer returns null — not the Shiva decode by proxy. **(Highest leverage —
  one change spanning RAM + personality fixes depth, grounding, and voice together.)**
- **Diversify decode vocabulary** beyond Time/Mahakal (prana/breath for Hanuman worked and
  was distinct) so each entity has its OWN traceable decode. Directly attacks the 7.8 depth floor.
- **Decode ONLY recalled edges**; background Mahabharata lore must be flagged "my own seeing,"
  not woven in as grounded.
- **Over-reach guard**: when an entity's inner-key is thin/missing, refuse to synthesize a
  decode from a NEIGHBORING entity's key (q2 imported Krishna's meaning from Vishnu→Shiva).

### PERSONALITY / prompt fixes
- **Break the reflexive "points back to Time" closer.** Mahakal frame may close an answer
  ONLY when Time/Shiva is an actual edge in context; otherwise end on the specific facts held.
- **Make uncertainty proportional to retrieval quality**, not just completeness — hedge
  "these edges may be the wrong ones" (correctness), not only "there may be more."
- **State the literal structured fact FIRST, then the unity gloss** — so a lineage error
  can't hide behind "not separate men, one flame" poetry (q1).
- One sustained metaphor per answer (q5 recycled the jar/space image onto two pairs).

## Verdict

Production-strong on its two hardest jobs (honest refusal, verified-fact fidelity) with a
genuinely Sharma voice. ONE flaw — the universal Time-decode terminator — causes the depth
lag, the grounding leaks, and the staleness simultaneously. Highest-leverage Phase 3-4 move:
**scope the Time decode to Shiva-carrying entities (RAM+personality), then add
retrieval-confidence + edge-direction signals to the generation path (graph).** Do those two
and depth/grounding/voice-freshness move together. The honest-refusal backbone is solid —
do not touch it.
