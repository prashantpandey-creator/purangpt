# Building a Living Graph from Sacred Text: A Field Report

*The honest engineering-and-epistemics companion to the theoretical paper `distilling-a-living-brain.md`.*

---

## Abstract

We set out to distill a "mind" from a 60-million-character corpus of Hindu sacred text — to build a knowledge graph and RAG system that answers questions about the Mahapuranas, the epics, the Gita, and the Upanishads with exact verse citations. This report records what we learned by actually building and repairing it. What held: a per-text, citation-gated grounding discipline that catches confident-but-wrong records; layer-aware traversal that separates blood lineage from spiritual transmission; and a graph that wins decisively on multi-hop, scattered, and cross-text-identity queries. What broke: two-thirds of the first decoded corpus was fabricated by a chunk-routing bug, an LLM decoder self-corrupted the graph through two characteristic merge bugs, and a production search outage that looked like a model failure was nothing of the kind. The central discovery threads through all of it: **meaning lives in the prose, structure lives in the graph.** Topology faithfully indexes *who relates to whom*; the *why* — the clause in a boon, the contract in a curse — remains authorial narration the graph only witnesses.

---

## Introduction

The through-line of this build is a single distinction that we kept rediscovering from different directions, usually the hard way: **a knowledge graph distilled from sacred text is a relational skeleton, not the corpus itself.** The prose — verses, teachings, narrative, the grammar of *why* things happen — never enters the graph; it lives in chunks searched by RAG. The graph holds only the relations between entities. Almost every failure we report is some version of confusing the two, or of trusting a structure that looked right while measuring the wrong thing: a routing bug that decoded the wrong text confidently, merge logic that collapsed a pantheon, a "law" that was a merge artifact, a verifier that called a retrieval miss a coverage hole, a health check that asserted readiness over a dead process. Each section below is one of those lessons, kept intact, paid for in a real bug or a dead hypothesis. Read together they make the case that the discipline is not better models but better epistemics: validate provenance independently of output quality, scope validation to the unit, and never mistake a shared endpoint for an encoded mechanism.

---

## The fabrication purge and graph repair

The single most consequential finding of this build was that **two-thirds of the decoded corpus was fabricated**. A `graph_health` audit established that 16 of 24 "decoded" texts were not weak decodes but Bhagavata clones: each carried identical `bhagavata-1-*` chunk IDs, `bhp_` source markers, and roughly 419–420 records — a fingerprint too uniform to be anything but duplication. (PROVEN.) Crucially, the cause was **not LLM quality**. The decoder had worked correctly on whatever it was handed; an upstream **chunk-routing bug** had handed it Bhagavata chunks while labeling them as other texts. The model faithfully decoded the wrong input. This is a NEGATIVE result with a sharp lesson: an output-quality metric would have scored these 16 texts as fine, because the records were internally coherent and well-cited — against the *wrong* source. The defect lived in provenance, not generation.

The repair was deliberately conservative. The 8 genuinely-decoded texts were kept untouched; the 16 fabricated ones were **quarantined to `out/quarantine/`** rather than deleted, and then **re-decoded from their own chunks** once routing was fixed. (PROVEN.) Quarantine over deletion matters: it preserves the evidence of the failure for audit and makes the purge reversible.

Two texts needed more than re-routing — they needed re-sourcing, because the underlying source data itself was bad. The **Mahabharata** was replaced wholesale: garbled GRETIL HTML was dropped in favor of the **BORI Critical Edition** (`bombay.indology.info`), giving 18 parvas of clean IAST and **73,816 `mbh_PP.CCC.VVV` markers** — a structured, citable marker grammar where the prior source had been unparseable. **Skanda** was likewise re-sourced from the **Leiden edition**. (PROVEN.) The distinction is worth stating plainly: routing bugs corrupt *which* text you decode; source-quality bugs corrupt *what the text even is*. Both produce confident, well-formed, wrong records, and they require different fixes.

The post-repair state is measured, not asserted. The final unified graph holds **8,755 entities and 24,474 edges across 22 decoded record-sets spanning 21 distinct texts** (the Bhagavata appears twice — a small early proof-of-concept plus the full decode — which is why the count reads as 21 or 22 depending on how that pair is treated). Grounding was verified **per text** against each text's own markers: Agni and Garuda at 97–100% own-marker citations, Vishnu and Markandeya at 100%, the Gita at 95%. (PROVEN.) The per-text breakdown is itself the safeguard — an aggregate grounding score would have masked the original fabrication entirely, since clones cite *real* (if wrong) markers. Throughout, `verify.py` gates **every** record's citations against real source markers, making "well-cited against the wrong source" a catchable, not silent, condition. Decode throughput was scaled to make re-decoding affordable: from **sequential DeepSeek, to 8 background processes, to 11 lanes**. (PROVEN.)

The implication generalizes beyond this corpus: in a generation pipeline, **provenance must be validated independently of output quality**, and validation must be scoped to the unit (per text), because uniformity and high citation rates are exactly what a routing or duplication bug produces.

---

## The merge-bug family: how a graph distilled by an LLM self-corrupts

**Finding (PROVEN).** A knowledge graph distilled by an LLM does not degrade randomly — it corrupts in *characteristic, repeatable ways* tied to how the decoder reads language. We hit two distinct false-merge bugs, both originating in the decoder, both fixed in `graph.py` (manifest mode), both with tests written first. The shared lesson outweighs either bug: the cure belongs in the merge **algorithm**, never in a hand-maintained blocklist.

**Bug 1 — the theological blob (PROVEN, fixed).** The decoder emitted identity edges from devotional statements of the form "X is Y" — e.g., "Shiva is Vishnu." In the corpus this is non-dualist theology, not entity equality. The merge pass fed those edges into union-find, which did exactly what union-find does: it transitively collapsed the entire pantheon into a **single Vishnu node carrying 2,458 aliases**. The fix was to stop trusting "is" as an equality signal: merge **only** name-variant `same_as` edges, and route every "rel: is" statement to a separate `aspect_of` edge type that is *kept and queryable but never merged*. The theology is preserved as relationship data; it just no longer fuses identities.

**Bug 2 — peer-name confusion (PROVEN, fixed).** The decoder also listed genuinely **distinct beings** as aliases of one another whenever they shared a name fragment: Balarama and Parashurama folded into Rama; "Shahindra" folded into Indra. Corpus-wide this produced **~3,411 true false-merge instances.** Severing the bad union was not enough — the polluted bare name lingered in the surviving node's `all_forms` and kept mis-seeding recall. The fix has two parts: (a) refuse to merge an alias that is itself an independently-substantial canonical entity, and (b) drop the bare shared name from `all_forms` entirely. Result: **3,411 → 10 residual merges, and all 10 are legitimate** — true synonyms like Kaivalya / Moksha / Mukti, all meaning "liberation." A standing detector (flag any node whose `all_forms` contains a distinct canonical of degree ≥ 5) re-runs after every rebuild, so a future decoder regression resurfaces immediately instead of silently re-blobbing the graph.

**Lesson / implication (METHOD).** Both bugs are the same shape: the LLM decoder over-asserts identity — once from semantics ("is" means equal) and once from surface form (shared substring means same entity) — and union-find then amplifies a per-edge error into a graph-wide collapse. The instructive part is *where* we did **not** put the fix. A blocklist of "never merge Shiva with Vishnu" would have been infinite, brittle, and corpus-specific. Encoding the actual invariants — equality comes only from name variation; a substantial canonical is never anyone's alias — fixed thousands of cases at once and generalizes to entities we have not yet decoded. When a graph is distilled by an LLM, treat the merge step as the adversarial boundary, validate it with real-output fixtures (as the fabrication purge above also required), and keep a detector watching it across rebuilds.

---

## Separating the lineages: layer-aware traversal

The finding: the graph conflated two distinct kinds of lineage — family (blood) and guru-disciple (transmission) — but the conflation was **not in the data**. Edges were already correctly typed: `father`/`son` for kinship, `guru_of`/`disciple` for spiritual succession. The bug lived in **traversal**. Any walk that asked for "lineage" followed every edge as one undifferentiated mesh, so blood and teaching currents flowed into each other and the result was a tangle that answered neither question correctly. (PROVEN — tool `graph_layers`, 8/8 tests passing.)

The reason this is subtle, and the reason the naive fix is wrong: **30–46 pairs legitimately carry both relations at once.** This is the Vedic pattern of the father as a child's first guru — Drona→Ashvatthama, Lahiri→Tinkori. A pair like that is simultaneously a kinship edge and a transmission edge. So you cannot resolve the tangle by deleting edges or forcing each pair into a single category; the duality is real and load-bearing. The fix has to be a **lens, not a deletion** — the same graph, read differently depending on which current you are tracing.

The mechanism: a relation→layer taxonomy (kinship / transmission / identity / conflict / …) plus directional, **vertical-only** walks that follow exactly one layer at a time. Asking for the blood line traverses only kinship edges; asking for the teaching line traverses only transmission edges. Demonstrated on Guruji's lineage, the two walks separate cleanly:

- **BLOOD line:** Sharma ← Ashvatthama ← Drona
- **TEACHING line:** Sharma ← Satyacharan ← Tinkori ← Lahiri ← Babaji

The fact a blended walk *destroys* is the most important one: **Satyacharan→Sharma is `guru_of` only — not blood.** A merged traversal would silently absorb that edge into a single lineage and erase exactly what makes the succession meaningful. The whole point of a spiritual lineage is that transmission can leave the bloodline; the teaching passing to someone who is not a son is what makes it a succession rather than a dynasty. A walk that cannot tell the two layers apart reports a dynasty where the corpus describes a transmission.

The lesson: when two relations look alike topologically, the discipline is to type the edges at ingest (done correctly here) **and** to keep the reader honest at query time. Correct data is not enough — a layer-blind traversal corrupts correct data on the way out. The lens belongs in the walk, not in a destructive normalization pass over the store.

**RESIDUAL (open):** layer separation does not cure everything. There remain **339 bidirectional directionality contradictions** — pairs where the graph asserts both "X father Y" and "Y father X." These still make Puranic lineage walks bounce back and forth, and they are a separate problem from layer conflation: even a perfectly layer-scoped walk cannot find a clean root when the arrows point both ways. That cure is the next step, not part of this one.

---

## Skeleton vs body: the corpus-graph funnel, the eight traversals, and graph-vs-RAG

**The finding, stated plainly: the graph is a relational skeleton, not the corpus.** [PROVEN] The prose — verses, teachings, narrative — never enters the graph; it lives in chunks searched by RAG. The graph holds only the relations between entities. Confusing the two leads to building the wrong thing.

The funnel that produces the skeleton is lossy by design. [PROVEN] Scraping yields 60M characters / 291,405 chunks across 47 texts. Roughly 81% of those chunks get decoded, but decoding only reaches 21 of 47 texts — so the graph that falls out is 8,755 entities and 24,474 edges. The other 26 texts (Brahma Vaivarta alone is 28k chunks, plus the Vedas and the sutras) are fully RAG-searchable but graph-absent. That gap is not a bug to close before the system is useful; it is the normal state of a corpus where prose retrieval and relational structure advance independently.

**What the skeleton is actually for: eight distinct traversals, each answering a question RAG cannot.** [PROVEN] Each was demonstrated:

- **bridge / shortest-path** — how two entities connect.
- **identity-cluster** — avatar groupings.
- **conflict-web** — who opposes whom.
- **devotion-flow** — direction of worship/allegiance.
- **gravitational-centres** — the Brahma / Vishnu / Krishna hubs by edge mass.
- **ego-network-by-layer** — a single entity's neighbourhood, by hop.
- **transmigration** — rebirth edges; this is the **thinnest layer at ~12 edges** (PROVEN measurement): the graph honestly reflects that scarcity rather than padding it. Whether that thinness is the corpus encoding little rebirth or the decoder capturing little is itself an open question (see verification epistemics).
- **cross-text bridges** — Shiva spans 16 texts, making him the connective tissue across the corpus.

**The graph-vs-RAG benchmark, and the honest caveat.** [PROVEN] Tool `rag_vs_graph_bench` (7/7 tests, `RAG_VS_GRAPH_BENCHMARK.md`) pitted plain keyword-RAG against graph-recall across five query classes. RAG wins or ties on PASSAGE and SINGLE-FACT — its home turf. Graph wins decisively, 5/0, on SCATTERED, MULTI-HOP, and CROSS-TEXT-IDENTITY. Retrieval runs ~45–90ms.

The caveat is recorded rather than buried: [PROVEN/NEGATIVE] the RAG floor here was *keyword* RAG. A real pgvector semantic retriever would lift the easy classes — PASSAGE and SINGLE-FACT. It would still fail the relational classes, because no amount of better passage matching reconstructs a multi-hop path or resolves a cross-text identity. The benchmark's edge is structural, not an artifact of a weak baseline; but claiming a bigger margin than the baseline supports would be dishonest.

**The lesson, and the implication.** Skeleton and body are complementary retrieval substrates, not competitors: ask the body (chunks/RAG) for *what was said*, ask the skeleton (graph) for *how things relate*. And they are already physically joined — [PROVEN] 87% of graph edges carry verse citations, so the graph is itself an index *into* the corpus. That makes graph-routed RAG — traverse the skeleton to find the relevant edges, then pull their cited chunks as the passages — mechanically possible today, not a future feature. [PROPOSED] Wiring that route is the obvious next build; the citation coverage to support it already exists.

---

## The structural-laws experiment and the central negative result

The central finding of this session is negative, and it is the most important one we report: **the deep patterns of the Puranic corpus are not encoded in graph topology.** They live in prose, and the graph merely *witnesses* them. (NEGATIVE — measured by adversarial test, not assumed.)

The experiment was designed to find structural "laws of the Puranic universe" the honest way. We mined candidate laws **bottom-up** from graph topology — motifs in who-relates-to-whom — under an explicit anti-typecast constraint: the miner was forbidden to retreat to the familiar high-level axes (Sat/Asat, Time, guna), so that any law it surfaced would be earned from structure rather than imposed from theology. Four candidates emerged. Each was then **adversarially stress-tested** rather than merely admired.

Three of the four were killed.

The most instructive death was also the prettiest candidate: *"genealogy is a repayment circuit — dynasties flow into devotion."* It had the shape of a real law. Under adversarial test it collapsed into a **random-chance intersection of bloated, merged worship-sets**: a randomly chosen deity lands inside the relevant set roughly 53% of the time purely by chance, because the worship-sets had been inflated by the very merge-blobs we had diagnosed and fixed elsewhere in the graph (see "The merge-bug family" above). The apparent "circuit" was a **merge artifact**, not a structural fact. A correct-looking, high-coverage pattern sitting on top of a contaminated set is still measuring nothing — the lesson of validating scope before trusting a result, here paid in a dead law.

One candidate survived, but only **demoted**. *"A boon is a specification whose unexcluded category becomes the killer"* — Ravana, Hiranyakashipu, Taraka — holds as a **verse-grounded narrative motif on named exemplars**. It does **not** hold as a topological universal: only **28% of boon-grantees have any recorded killer at all**, and critically the mechanism is **not present in the 186 boon edges** in the graph. The pattern is real in the text; it is simply not a property of the graph's structure. It survives as narration witnessed by topology, not as a law encoded by it.

That demotion is the whole result in miniature. The graph faithfully indexes *who relates to whom*. But the **grammar of WHY** — the gap a boon leaves open, the contract a curse binds — is **authorial narration the decoder never captured as structured attributes.** Topology can confirm that Ravana received a boon and that Rama killed him; it cannot hold the clause that made the death inevitable, because that clause was never extracted as an edge or attribute. It exists only in the prose.

The operational lesson, stated as a rule: **never mistake a shared-endpoint coincidence for an encoded mechanism.** Two entities meeting at a common node is evidence of co-occurrence, not of a generative law. Mining topology for the corpus's deepest patterns is searching the index for the meaning of the book. To capture the *why*, the mechanism must be extracted from prose into structured attributes first — and that extraction is work the current decoder did not do.

---

## The Vedic cognitive-science mapping, rasa, and the self-learning loop

**Finding (PROVEN convergence).** The companion theoretical paper (`distilling-a-living-brain.md`, committed) maps the classical *antaḥkaraṇa* onto the system's existing parts: *manas* = retrieval-orchestration, *buddhi* = the RAM decode-lens, *citta* = the stores, *smṛti* = `recall.py`, and the *catvāri-vāk* sequence (*parā → paśyantī → madhyamā → vaikharī*) as the generation pipeline (the "Vāk thesis"). The mapping was not built as a decoration; it was a diagnostic. Every faculty correspondence, derived independently, re-converged on the *same* architectural gap: `recall.py` and the RAM are not wired into the live `/api/chat` path — there is no `{knowledge_context}` slot in the production prompt. The consequence, stated plainly: production has no operating *smṛti* and no operating *buddhi*. "The charioteer is built but not seated in the chariot." That five separate analogical mappings each independently surface the identical wiring defect is the evidence that the mapping is doing real work rather than ornamenting the codebase.

**Citation discipline (PROVEN).** The mapping's source verses were mechanically verified against the corpus, not asserted from memory: `bhg_6.34`, `BrP_236`, and the Kaṭha chariot verse were confirmed present. This is the same grounding standard the project applies everywhere — a claim about the texts is only admissible once the marker resolves to an actual passage.

**RASA (PROPOSED — added as section 7, explicitly marked unbuilt, alongside *turīya*).** The proposal is to treat emotion as the corpus's *native* retrieval index, following the *rasa-sūtra* of the Nāṭyaśāstra — i.e. retrieve by affective register rather than only by lexical/semantic similarity. The substrate is real and measured: the Krishna–Arjuna bond alone carries 67 affect-laden relation-verbs (*friend*, *embraced*, *grieves_for*, *consoler*). But no rasa-typed or affect-indexed layer exists. The admissibility condition is stated up front: any sentiment classification is allowed only if each tagged emotion is cited to actual passages — the same grounding gate, extended to affect. Without it, rasa-indexing would be sentiment invention dressed as retrieval.

**The self-learning loop (PROPOSED, with a hard safety gate).** The chitta *vṛtti → saṃskāra → vṛtti* cycle is mapped to a self-learning loop: the system writing new edges back into its own graph from what it reads. The finding here is a constraint, not a feature. The loop is safe *only* if every self-written edge passes the `verify.py` gate; self-learning without that gate is a hallucination amplifier — each unverified edge becomes training substrate for the next pass. The classical brake is invoked directly: Vācaspati's claim that memory yields "former knowledge or less, never more." A faithful *saṃskāra* loop must therefore be bounded by verification; it may consolidate what was grounded, never manufacture beyond it.

**Lesson.** The cognitive-science frame earned its place by exposing the seated-charioteer gap that the component-level view missed. The two forward ideas — rasa and self-learning — are deliberately unbuilt and carry the same precondition: nothing enters the graph, as affect-tag or self-written edge, without a verified citation behind it.

---

## Verification epistemics: WHO vs WHY, and the three failure modes

**Finding (PROVEN).** Verifying a graph-claimed fact against the corpus is hard, and the hardest part is that "not found" is ambiguous. A failed lookup collapses three distinct conditions into one identical-looking signal: (1) the claim is genuinely **FALSE**; (2) the proving passage was **NEVER GATHERED** into the corpus; or (3) the passage **IS present but RETRIEVAL MISSED it**. Without a way to tell these apart, every absence is unfalsifiable — and the cheap instinct, treating co-occurrence as confirmation, is wrong in the other direction.

**Evidence (PROVEN, NEGATIVE).** Repeated ad-hoc keyword verifiers failed in both directions at once. They threw **false-negatives** from brittle matching: a same-chunk co-occurrence requirement, exact-spelling sensitivity, and diacritic mismatches. They simultaneously threw **false-positives** from bloated alias-sets that matched spurious passages. So the same tooling under-reported real evidence and over-reported fake evidence — the worst of both.

The decisive measurement came from bypassing those verifiers with direct grep. Several mechanisms the graph pipeline reported as **claimed-absent** — Hiranyakashipu's boon, Ravana's man-gap, the Uttara Kanda — were **CONFIRMED PRESENT** by raw search: 29 Ravana chunks, the full 1,887-chunk Uttara Kanda. These were failure mode (3), retrieval-miss, **masquerading as mode (2)**, a gather gap. The corpus had the answer the whole time; the retrieval layer just couldn't surface it. That single mislabeling — calling a retrieval bug a coverage hole — is exactly the error that quietly corrupts any claim about what the corpus "doesn't contain."

**Lesson / implication.** Co-occurrence is not confirmation. Reliable verification needs **broad recall** (so mode 3 stops hiding) plus an **LLM judge that actually reads the passage and confirms the specific relation** (so mode 1 stops being faked by spurious alias hits). This factors cleanly onto the data model and restates the report's central thesis: the graph attests **WHO** — entities and that a relation is alleged; only the prose holds **WHY** — the mechanism that makes it true (the same WHO/WHY split that killed the structural-laws above). The join is a pipeline, not a lookup: **graph-discovers → RAG-retrieves → judge-confirms.**

**Taxonomy for open ends (PROVEN measurement, PROPOSED discipline).** The same ambiguity reappears at structural dangling ends. A dangling graph structure is one of three things: a **genuine frontier** (the story is still ongoing — e.g., Sharma alive), a **genuine aporia** (the corpus is deliberately silent), or a **capture-gap** (fixable, a real coverage or retrieval failure). These must not be conflated — and empirically they were skewed toward the fixable kind: **63% of 1,211 lineage tips were thin / coverage-gap**, not true frontiers. The discipline that follows: *"it's supposed to be open" must not launder coverage bugs.* An open end is a claim with the same burden of proof as any other, and most of ours turned out to be debt, not mystery.

---

## Production field notes: the search incident and the exonerated model

A live production outage taught the sharpest lesson of this project: the embedding model, the obvious suspect, was innocent. Production semantic search returned **0 results for every query** — even a single-word probe like `dharma` — while `/api/status` cheerfully reported `index_ready:true`. The status endpoint was lying, and the model everyone reaches to blame had nothing to do with it. **(PROVEN, via live debugging on the Hetzner server.)**

**Root cause, part 1 — stale in-process state.** The running uvicorn process held a *dead* `HybridSearcher` left over from the prior "nomic incident" deploy. The code on disk had already been reverted to e5-small, but the container was never restarted, so the live process was still executing the broken object. This was proven by elimination — every layer worked **in isolation**:

- Data healthy: 314,469 rows, all embedded, with HNSW and FTS indexes intact.
- The `hybrid_search` SQL function returned rows when called directly.
- The e5-small model encoded correctly at 384 dimensions.

Each component passing alone while the whole returned nothing is the signature of stale in-process state, not a data or model defect. **Fix: `docker restart purangpt_backend`.** **(PROVEN.)**

**Root cause, part 2 — an app-layer filter, revealed only after a surgical Redis flush** of 135 stale `hybrid_search:*` cache keys. Post-flush, a fresh search returned `count:3` but `results:[]` for natural-language queries. The culprit was `build_source_list`'s `is_sharma_text` filter: English natural-language queries semantically land on the (English) Guruji-darshan chunks, and the filter strips exactly those, leaving zero scripture surfaced. So two independent bugs — a stale process and an over-aggressive filter — stacked to produce the same empty symptom. **(PROVEN.)**

**The exonerated model (a NEGATIVE result worth stating plainly).** e5-small is **not** the bottleneck:

- It produces the correct 384-dim vectors.
- FTS matched 10,624 rows for a multi-word query.
- Direct calls returned mixed scripture + darshan results.

Every piece of evidence points at the process lifecycle and the app layer, not the encoder. The instinct to "upgrade the embedding model" would have been the worst possible response: it is **costly**, it is **risky** — a full 314k re-index is precisely what caused the nomic incident in the first place — and it would have fixed **none** of the actual app-layer bugs. **(NEGATIVE finding: model-upgrade as a remedy was considered and rejected on evidence.)**

**The lesson.** When search silently returns nothing, the embedding model is the loudest suspect and usually the wrong one. Restart-state staleness and silent filter logic are mundane, invisible to a health check that only asserts `index_ready`, and far more likely. Any future model change here must be gated behind an actual **quality test on retrieval output**, never adopted on the assumption that a bigger model fixes a zero-results bug. **(PROPOSED: a retrieval-quality gate as the sole justification for a model swap.)**

---

## Conclusion: What building it taught us

Four lessons were the hardest-won, and each was paid for in a real bug or a dead hypothesis rather than reasoned out in advance.

1. **Provenance is a separate axis from quality, and must be validated separately.** The fabrication purge is the founding lesson: 16 of 24 texts were internally coherent, well-formed, and confidently cited — against the wrong source. Every output-quality metric would have passed them. The defect lived in *which input* was decoded, not in *how well* it was decoded. The corollary is scope: validation has to be per-unit (per text), because uniformity and high citation rates are exactly the fingerprint a routing or duplication bug leaves behind. An aggregate score hides the very failure it should catch.

2. **Meaning lives in the prose; structure lives in the graph — and the boundary is load-bearing, not philosophical.** The structural-laws experiment proved it adversarially: topology faithfully holds *who relates to whom*, but the *why* — the unexcluded category in a boon, the binding clause of a curse — was authorial narration the decoder never extracted as structured attributes. The verification work restated the same split as WHO (graph) versus WHY (prose). Mining topology for the corpus's deepest patterns is searching the index for the meaning of the book. The same boundary makes graph-routed RAG the right architecture: traverse the skeleton for relations, pull the cited chunks for meaning.

3. **An LLM-distilled graph corrupts in characteristic, repeatable ways — so fix the algorithm, never the symptom.** Both merge bugs were the decoder over-asserting identity (semantically via "is," structurally via shared substrings), amplified by union-find into graph-wide collapse. The cure was encoding the actual invariants, not maintaining a blocklist — which fixed thousands of cases at once and generalizes to undecoded entities. The same instinct governs traversal: correct, well-typed data was still corrupted on the way *out* by a layer-blind walk, so the lens belongs in the reader, not in a destructive pass over the store.

4. **The loudest suspect is usually innocent; trust the evidence, not the instinct.** The production incident's whole lesson is that the embedding model — the reflexive thing to blame and the most expensive, riskiest thing to change — was provably not the cause. Stale in-process state and a silent app-layer filter were, and a health check that only asserts `index_ready` saw none of it. Any expensive remedy (a model swap, a re-index) must be gated behind a test that measures the actual failing output, never adopted on a hunch about what "should" fix it.

The unifying discipline underneath all four: **a correct-looking result around the wrong measurement is still wrong.** Clones cite real markers; a merge artifact yields a high-coverage "law"; a retrieval miss looks identical to a coverage gap; a dead process reports itself ready. Every safeguard we kept exists to make the wrong measurement *catchable* — per-text grounding, `verify.py` gating every record, real-output fixtures on the merge step, a standing merge detector, the WHO→WHY judge pipeline, and a retrieval-quality gate before any model change.

---

## Open problems (honest status)

- **The graph is not wired into production chat.** `recall.py` and the RAM decode-lens are built but not connected to the live `/api/chat` path — there is no `{knowledge_context}` slot in the production prompt. Production currently runs with no operating *smṛti* and no operating *buddhi*: the charioteer is built but not seated in the chariot. The citation coverage to support graph-routed RAG already exists (87% of edges carry verse citations); the wiring does not.

- **339 bidirectional directionality contradictions remain.** Pairs where the graph asserts both "X father Y" and "Y father X" make Puranic lineage walks bounce back and forth. This is distinct from layer conflation (which is fixed): even a perfectly layer-scoped walk cannot find a clean root when the arrows point both ways. This cure is the next step, not done.

- **The live `build_source_list` bug.** The `is_sharma_text` filter strips the English Guruji-darshan chunks that English natural-language queries semantically land on, surfacing zero scripture. Identified and proven in the production incident; the filter logic still needs to be corrected so it stops silently zeroing out legitimate results.

- **Mechanism-verification needs the judge join.** Confirming a *why*-claim (that a specific relation actually holds in the prose) requires the full **graph-discovers → RAG-retrieves → judge-confirms** pipeline. Broad recall plus an LLM judge that reads the passage is specified but not yet operating; until it is, absences remain ambiguous between genuinely-false, never-gathered, and retrieval-missed — and most of our measured open ends (63% of 1,211 lineage tips) are coverage debt, not true frontiers.