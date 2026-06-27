# retrieval_qc

Measures **retrieval efficacy and source quality** of PuranGPT search, so we know
the corpus richness is actually explored and the sources are clean. Built to
diagnose a real report ("Agni Purana appears too often / alphabetic bias / are
Guruji's texts in the wrong place?"). See `FINDINGS.md` for the production baseline.

Two halves (intentionally split so the decision logic is DB-free and testable):
- `analyze.py` + `check.py` — **pure** analysis over a collected payload, fixture-tested.
- `collect.py` — **live** query battery against the real stack (run in the backend container).

## What it checks

| Check | Pass criterion | Catches |
|-------|----------------|---------|
| `distribution` | no source > 15% of slots; ≥ 15 distinct sources | one text dominating |
| `alphabetic_bias` | \|rank-correlation\| ≤ 0.30 | GRETIL alphabetical positional bias (the Agni symptom) |
| `metadata_quality` | 0 source names look like file-ids | fragmented names that defeat MMR diversity |
| `known_item_recall` | expected source in top-k for every curated pair | scripture not surfacing |
| `hybrid_contribution` | FTS fires on ≥ 30% of queries | dead keyword half (`kw_sim = 0`) |
| `coverage` | ≥ 60% of corpus sources reachable | unexplored corpus richness |
| `corpus_separation` | *advisory* (never gates) | whether Guruji material should be a separate corpus |

`healthy: true` iff every **gating** check passes (`corpus_separation` is advisory).

## Run it

```bash
# 1) Collect a live payload (inside the backend container, where the DB is reachable):
docker exec purangpt_backend bash -c "cd /app && python -m tools.retrieval_qc.collect > /tmp/run.json"

# 2) Analyze it (anywhere — pure, no DB):
venv/bin/python -m tools.retrieval_qc.check --payload /tmp/run.json --json   # {success,data,...} envelope
venv/bin/python -m tools.retrieval_qc.check --payload /tmp/run.json          # human summary

# Self-check on the committed production-baseline fixture:
venv/bin/python -m tools.retrieval_qc.check --payload tools/retrieval_qc/fixture_prod_baseline.json --json

# Tests (must exit 0):
venv/bin/python -m tools.retrieval_qc.test_check
```

Exit codes: `0` healthy · `1` issues found · `2` error.

## Failure modes

| Symptom | Cause | Handling |
|---------|-------|----------|
| `success:false code=empty_payload` | payload has no `queries` | collect.py produced nothing — check DB reachability / `index_ready` |
| `success:false code=no_payload` | `run()` called without a dict | pass a payload or `--payload <file>` |
| `coverage`/`metadata` skipped | payload lacks a `corpus` block | run `collect.py` where `VECTOR_DB_URL` is set, or accept partial analysis |
| `hybrid_contribution` skipped | no `fts_hit` per result | expected — the SQL fuses FTS internally; needs a SQL-level probe to measure |
| `distribution_gretil` total_slots 0 | GRETIL matched nothing for the English battery | expected for non-IAST queries; the alphabetic bias shows on Sanskrit-term queries |

## Input/output contract

`run(payload, expectations=None) -> {success, data, metadata, errors}`.
`payload` and the `data` shape are documented at the top of `analyze.py`.
`data` = `{healthy, failed_checks, checks{<name>: {check, pass, …}}}`.
