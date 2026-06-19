# scripts/ — one-off operational jobs

These are **off-band batch jobs**, not part of the live request path. They are
CPU/memory-heavy and must **not** be run casually on the production box while it
serves traffic — doing so competes with the API workers for RAM and can trigger
the OOM killer.

## embed_pgvector.py — backfill verse embeddings

Generates 384-dim `intfloat/multilingual-e5-small` embeddings for every
`purana_verses` row whose `embedding` column is NULL, and refreshes the `fts`
tsvector. Idempotent and resumable: rerunning only processes rows still missing
an embedding (`WHERE embedding IS NULL`), so a crash/OOM loses no completed work.

```bash
# Dry run — count how many rows still need embedding
python scripts/embed_pgvector.py --dry-run

# Run it (workers default to nproc-1; LOWER this on a memory-tight box)
python scripts/embed_pgvector.py --workers 3
```

### Operational notes (learned the hard way)
- **Each worker loads its own copy of the model (~1GB).** On the 15GB prod box,
  6 workers + the live backend OOM-killed the job at ~14k rows. **3 workers is
  the safe ceiling while the backend is also running**; use more only if the
  backend is scaled down or the job runs on a separate machine.
- Throughput is ~13k rows/hr at 3 workers on the 8-core prod box (~24h for the
  full 314k corpus). It is CPU-bound (no GPU); there is no quick win short of a
  GPU box or a hosted embedding API.
- Prefer running this **off the live box** — e.g. against a copy of the DB, or on
  a temporary larger instance — then the result is just rows in Postgres that the
  live backend reads. The live backend never needs to run this.
- Requires `VECTOR_DB_URL` in the environment (same DSN the backend uses).

### When to run it
- After ingesting new texts that were inserted without embeddings.
- After a corpus re-chunk. Otherwise the live search silently degrades to
  FTS-only for any rows missing an embedding (the semantic branch of
  `hybrid_search` skips `WHERE embedding IS NOT NULL`).
