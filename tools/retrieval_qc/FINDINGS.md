# retrieval_qc — baseline findings (2026-06-21)

Built to answer the user's report: *"I see Agni Purana in sources a lot… the
retrieval order is being affected alphabetically… asses its efficacy so we know
the richness of the source is explored… QC the sources… and do we need Guruji's
text in a different DB?"*

Ran the tool against **production** (20 diverse queries through the live stack).
Verdict: **HEALTHY: False** — 4 of 8 gating checks failed. The captured payload is
committed as `fixture_prod_baseline.json` so these numbers are reproducible offline.

## What we found (measured, not assumed)

| Check | Result | Meaning |
|-------|--------|---------|
| `distribution_hybrid` | top sources ALL "Shailendra Sharma Darshan — …" fragments | Guruji's darshans crowd out scripture in the main semantic path |
| `known_item_recall` | **33%** | "nature of Vishnu" → no Vishnu Purana; "Durga" → no Markandeya. Scripture doesn't surface |
| `coverage` | **18.9%** | only 82 of 434 sources EVER appear over 20 queries; Agni, Upanishads, Panini never reached |
| `metadata_quality` | **303 / 434** names polluted | per-file ids (`darshans202018-2`, `compilation6-2`) fragment one corpus into hundreds of "sources", defeating MMR diversity |
| `corpus_separation` (advisory) | vol **3.9%**, names **89.4%**, **frag index 22.7** | **SEPARATE/FLAG STRONGLY** — Guruji material is 4% of content but 89% of source-names |

## The two distinct problems (don't conflate them)

1. **The Agni-Purana symptom the user saw = the GRETIL path.** `search_sanskrit`
   (`backend/main.py`) iterates the corpus in **alphabetical insertion order**
   (loaded via `sorted()` in `load_gretil_corpus`) and returns the first
   `max_results` matches, stopping early. A-named texts (Agni, Atharvaveda,
   Amarakosha) systematically win slots. Pure positional bias. *(In this run the
   GRETIL probe returned 0 rows for the English test queries, so the bias shows up
   only on Sanskrit/IAST-term queries — but the mechanism is confirmed in code.)*

2. **The bigger, measured problem = Guruji's darshans dominate the SEMANTIC path
   and bury scripture.** This is what tanks known-item recall and coverage. Root
   cause: Guruji material lives in the SAME vector space as citable scripture, with
   fragmented metadata, and `sharma_weighting` actively multiplies its score (×1.6
   for `yogic-commentary`/`yogic-discourse`).

## Scope caveat (learned from sse_contract_check/FINDINGS.md)

A correct envelope around the wrong measurement is still wrong. Two scope notes:
- `hybrid_contribution` is **skipped** here — the SQL fuses FTS internally so the
  Python layer can't see per-result `fts_hit`. Measuring it needs a SQL-level probe
  (separate component scores), which the earlier raw-SQL diagnostic did show:
  `kw_sim = 0.000` on every top result → FTS is effectively dead for this corpus.
- `coverage`/`metadata` count the polluted Sharma names in the denominator (434),
  which inflates "missing" counts. That's intentional — the pollution IS the finding.

## Recommended fix order (informed by the data)

1. **Separate Guruji corpus from scripture.** Tag every chunk with a clean
   `corpus_type` (`scripture` | `guruji`) and a clean canonical `source` name.
   Query scripture and Guruji on **separate channels** (Guruji → voice/cognition
   context; scripture → citable sources), instead of one ranked pool. A physically
   separate table/DB is optional; a clean `corpus_type` + filtered queries achieves
   the same and is far cheaper. (frag index 22.7 ⇒ this is the highest-leverage fix.)
2. **Fix GRETIL ranking** — score matches and sample across texts; stop returning
   alphabetical-first.
3. **Make FTS Sanskrit-aware** (`simple` config, not `english`) or drop the dead
   keyword half and own it as semantic-only.
4. Re-run this tool after each change — `healthy: true` is the acceptance gate.
