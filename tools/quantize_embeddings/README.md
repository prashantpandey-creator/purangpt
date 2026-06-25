# quantize_embeddings

Shrink the float32 `embeddings` table in `data/offline/corpus.db` to a 4x-smaller
int8 `embeddings_i8` table so the offline app downloads ~123 MiB of vectors
instead of ~482 MiB, with no meaningful loss in semantic-search quality.

One-line purpose: _replaces the "should I quantize, and is recall still OK?"
decision tree with a deterministic, self-checking transform that proves its own
recall@10 in the envelope._

## Tool descriptor

```json
{
  "tool_name": "quantize_embeddings",
  "input_schema": {
    "type": "object",
    "properties": { "db_path": { "type": "string" } },
    "required": []
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "rows_quantized": { "type": "integer" },
      "int8_bytes":     { "type": "integer" },
      "float32_bytes":  { "type": "integer" },
      "ratio":          { "type": "number" },
      "recall_at_10":   { "type": "number" }
    },
    "required": ["rows_quantized", "int8_bytes", "float32_bytes", "ratio", "recall_at_10"]
  }
}
```

## Output envelope

```json
{ "success": true,
  "data": { "rows_quantized": 329057, "int8_bytes": 128990344,
            "float32_bytes": 505431552, "ratio": 0.2552, "recall_at_10": 0.946 },
  "metadata": { "db_path": "...", "dim": 384 }, "errors": [] }
```

Storage layout: `embeddings_i8(chunk_id TEXT PK, vec BLOB, scale REAL)`. Each `vec`
is 384 symmetric-int8 bytes; dequant is `int8 * scale` where `scale = max|v|/127`
per vector. The frontend reads `embeddings_i8` and dequantizes in JS before the
cosine scan. The source `embeddings` table is left intact (drop it separately when
building the shippable corpus).

## Usage

```bash
# from purangpt/ repo root
venv/bin/python -m tools.quantize_embeddings.check          # human summary, default db
venv/bin/python -m tools.quantize_embeddings.check --json   # JSON envelope
venv/bin/python -m tools.quantize_embeddings.check --db /path/to/corpus.db --json
```

As a library:

```python
from tools.quantize_embeddings.check import run
env = run("data/offline/corpus.db")
assert env["success"] and env["data"]["recall_at_10"] > 0.9
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `db_path` does not exist | `success=false`, `errors=[{code:"missing_db"}]`, exit 2 |
| no `embeddings` table, or it is empty | `success=false`, `errors=[{code:"missing_embeddings"}]`, exit 2 |
| Normal | `success=true`, writes `embeddings_i8`, exit 0 |

`recall_at_10` is a self-check: 50 random stored vectors are used as queries and
their int8 top-10 neighbours are compared to the float32 ground truth. On the real
corpus it reports ~0.95; if a future model/dim makes int8 lossy this number drops
and you'll see it in the envelope before shipping.

## Tests

`venv/bin/python -m tools.quantize_embeddings.test_check` — builds a real tiny
SQLite corpus, quantizes it, and asserts envelope shape, the int8 table layout,
per-vector cosine > 0.99, recall@10 ≥ 0.80, ratio < 0.35, and both error paths.
