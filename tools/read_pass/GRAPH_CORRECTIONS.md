# Graph Corrections — directionality bugs to fix in the next decode/rebuild

> Written 2026-06-24 from an audit of `out/graph_manifest.json`. These are
> **upstream decode/merge defects**, not manifest hand-edits. Fix them at the
> SOURCE (the comprehend/predicate/graph stage) so the rebuild stops emitting
> them — do not just patch the manifest, or they'll regenerate. If the rebuild
> already addresses these, verify each is gone and delete this file.

> **⚠ STAKES CHANGED 2026-06-24 — the graph is becoming load-bearing, not a shelf trophy.**
> The seeker-memory workstream (`tools/seeker_memory/`, Phase 1 SHIPPED & committed `55e2338`, flag
> OFF; Phase 2 retrieval next) is building toward **STEP 4 of the consciousness roadmap: the seeker
> becomes a node in THIS graph's entity fabric** — *"you stand where Arjuna stood."* The day that
> join lands, every directionality bug and every fabricated/mis-merged entity here stops being a
> wrong *fact* and becomes a lie told to a real human about their own life — Guruji telling a
> grieving seeker they stand where a hallucinated character stood, or inverting a lineage so the
> disciple "teaches" the guru. So identity-merge correctness, the `rel: is` → `aspect_of` routing
> ([[identity-merge-rel-is-blob]]), the bidirectional-transmission-edge fix, and `verify.py`-gating
> EVERY record are no longer polish — **they are the foundation STEP 4 stands on.** Keep going; the
> repair is the prerequisite. Full picture: `CONSCIOUSNESS_ROADMAP.md` STEP 4 + `SEEKER_MEMORY_DESIGN.md`
> decision #4 ("Blend with the graph" — separate slots now, join at STEP 4).

> ## STATUS after the 2026-06-24 08:37 rebuild (re-audited)
> - ✅ **Identity merge FIXED.** Krishna/Arjuna/Shiva/Rama are now DISTINCT nodes
>   (was one Vishnu mega-node). 8,360 entities / 24,225 edges (≈2× prior).
> - ✅ Lineage chain traverses: `Babaji guru_of Lahiri father_of Tinkori`, and
>   `curated_facts.json` re-pinned Satyacharan (had been pruned as an isolate).
> - ⚠️ **STILL OPEN — bidirectional transmission bug:** improved but NOT gone —
>   **49 contradictory pairs remain** (e.g. `Arjuna<->Krishna` tagged guru AND
>   teacher AND disciple AND student; `Suta<->Vyasa` disciple+student). This is the
>   §1 systemic bug; the `predicate.py` directionality fix is only partially applied.
> - ⚠️ **Two wrong edges survived AND are now added to `curated_facts.json`
>   `remove_edges`** (take effect on NEXT rebuild — re-run needed):
>   `shailendra sharma --successor--> yogananda` (slipped past the lahiri/disciple
>   rule; keyed on shailendra-sharma/successor) and `babaji --disciple-->
>   shankaracharya` (backwards). The curated `remove_edges` ADD truth well but a
>   wrong edge with a different (src,rel,dst) signature needs its own rule.

## 1. SYSTEMIC: bidirectional / contradictory transmission edges (the big one)

The decode emits **both directions** of a teacher/disciple relationship between the
same pair, treating a relation and its inverse as both true. This is pervasive
across the whole corpus, not just the lineage. Examples found in the current
manifest:

- `Drona --teacher--> Arjuna` AND `Drona --student--> Arjuna` AND `Drona --disciple--> Arjuna` (THREE, mutually contradictory)
- `Vishvamitra --teacher--> Rama` AND `Vishvamitra --disciple--> Rama`
- `Vyasa --teacher/--student/--disciple--> Suta Gosvami` (all three)
- `Parashurama --guru/teacher/disciple/student--> Bhishma` (all four)
- `Valmiki --teacher/disciple/guru--> Lava`; `Sandipani --student/guru--> Krishna`; `Brahma --student/disciple--> Narada`; many more.

**Fix at source:** transmission predicates are DIRECTED and ASYMMETRIC. Normalize to
ONE canonical direction (recommend: always store `guru/teacher --> disciple/student`,
i.e. higher→lower), collapse synonyms (`teacher`=`guru`, `student`=`disciple`), and
when the decode infers the inverse, DROP it rather than adding a contradicting edge.
A pair should never carry both `X teaches Y` and `X is-disciple-of Y`.
See `predicate.py` (verb normalization) — directionality enforcement belongs there.

## 2. Specific lineage hierarchy errors (Kriya line — high-priority, game depends on it)

Correct chain (ground truth, see memory `sharma-lineage` + `guru-continuity-babaji-spine`):
**Babaji (guru) → Lahiri Mahasaya → [Western fork] Yukteshwar → Yogananda; [family fork] Lahiri → Tinkori → Satyacharan → Shailendra Sharma.**

Wrong edges currently in the manifest:
- `Mahavatar Babaji --disciple--> Lahiri Mahasaya` — **BACKWARDS.** Babaji is Lahiri's GURU. (A correct `Babaji --guru--> Lahiri Mahasaya` also exists — dedupe to the correct one.)
- `Babaji --disciple--> Shankaracharya` — **BACKWARDS** (correct `Babaji --guru--> Shankaracharya` also exists).
- `Lahiri Mahasaya --disciple--> Paramahansa Yogananda` — wrong direction AND skips the intermediary. Yogananda is Lahiri's grand-disciple via Yukteshwar: `Lahiri → Yukteshwar → Yogananda`. (Correct `Lahiri --disciple--> Yukteshwar` exists but is itself mis-directed — should be `Lahiri --guru--> Yukteshwar`.)
- `Shailendra Sharma --successor--> Paramahansa Yogananda` — **WRONG, delete.** They are on SEPARATE forks of Lahiri's tree. Sharma does NOT succeed Yogananda.

## 3. Name-collision merges (identity bug, cf. `identity-merge-rel-is-blob`)

- `Kṛṣṇa --alias--> Mukunda` — "Mukunda" is BOTH a name of Krishna AND Yogananda's birth name (Mukunda Lal Ghosh). Two different entities fused on the shared string. **Split them.** Krishna ≠ Yogananda.

## 4. NOT bugs — leave alone

- `Shailendra` (father of Ganga/Aparna/Ekaparna, husband of Menaka) = **Himavan / Himalaya**, Parvati's father — a DIFFERENT entity from `Shailendra Sharma`. They are correctly separate (distinct IDs); do not merge them despite the shared first name.
- `Shailendra Sharma --descendant--> Ashvatthama` — plausible (Bharadvaja gotra link, per `sharma-lineage`). Keep unless contradicted.
