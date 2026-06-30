# reembed

Offline pipeline: normalize 206K IAST-romanized corpus rows to Devanagari and re-embed with `BAAI/bge-m3`. Replaces the ad-hoc "run a model on the server" decision tree — each step is deterministic, tested, and resumable.

## Tool descriptor

```json
{
  "tool_name": "reembed",
  "input_schema": { "step": "export|normalize|embed|import", "input": "file/dir", "out": "file/dir" },
  "output_schema": { "n": "int", "stats": "object", "dim": "int", "sec": "float" }
}
```

## Steps (run in order)

```bash
# 0. Open SSH tunnel (keep running in background)
ssh -i ~/.ssh/purangpt_hetzner -L 5433:localhost:5433 root@204.168.176.229 -N &

# 1. Export full corpus from prod DB (~291K rows, ~5 min)
cd purangpt/
venv/bin/python -m tools.reembed.check --step export --out rows.jsonl --json

# 2. Normalize IAST->Devanagari (~2 min, pure string ops)
venv/bin/python -m tools.reembed.check --step normalize --input rows.jsonl --out norm_rows.jsonl --json

# 3. Embed with bge-m3 on Mac MPS (~75 min, resumable)
venv/bin/python -m tools.reembed.check --step embed --input norm_rows.jsonl --out embed_out/ --json

# 4. Push vectors to prod DB + build HNSW index (~20 min)
venv/bin/python -m tools.reembed.check --step import --input embed_out/ --json

# Dry-run to validate without DB writes
venv/bin/python -m tools.reembed.check --step import --input embed_out/ --dry-run --json
```

## Failure modes

| Code | Cause | Fix |
|------|-------|-----|
| `error` (export) | SSH tunnel not running | Run step 0 above |
| `error` (export) | psycopg2 missing | `venv/bin/pip install psycopg2-binary` |
| `error` (embed) | bge-m3 not yet downloaded | First run downloads ~2.3 GB; ensure disk space |
| `error` (embed) | MPS OOM | Reduce `--batch-size` in embed.py (default 5000) |
| `error` (import) | id/vec count mismatch | Delete embed_out/ and re-run step 3 |
| `error` (import) | HNSW fails | Build index manually via psql |

## Notes

- **Rollback:** old `embedding` column (384-dim, e5-small) is preserved untouched. The cutover (search.py model swap + `embedding_bge` column) is a separate step after eval passes.
- **Resume:** embed step checkpoints each 5K-row batch to `embed_out/batch_{i}/`. Kill mid-run, re-run — completed batches are skipped.
- **Script rules:** IAST detected by diacritics (a macron, underdot, etc.). Devanagari by U+0900-U+097F. Commentary rows (yogic-commentary, yogic-discourse, yoga_commentary, darshan-* IDs) are never transliterated.

## Tests

```bash
venv/bin/python -m tools.reembed.test_check   # 11 tests — normalize core only
```
