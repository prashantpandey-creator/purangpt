# rag_vs_graph_bench

Re-runnable benchmark of **plain keyword-RAG (the floor)** vs **the real graph
recall** across 5 query classes, so "does the graph beat plain RAG?" studies can
REPRODUCE the baseline instead of citing a static, un-rerunnable JSON.

The keyword-RAG is the deliberate FLOOR — same retrieval SHAPE as pgvector (top-k
by relevance) but the crudest signal (normalized term overlap). Its slowness over
the full 291k-chunk corpus (~7s/query) is the point: it's the cost a dense
retriever also pays. `--quick` STRIDES the corpus (not a head slice) to a fast
sample while keeping every text represented.

## Tool descriptor

```json
{
  "tool_name": "rag_vs_graph_bench",
  "input_schema": {
    "type": "object",
    "properties": {
      "quick":       { "type": "boolean", "description": "stride-sample the corpus for speed" },
      "k":           { "type": "integer", "description": "top-k for the RAG floor (default 5)" },
      "corpus_path": { "type": "string" },
      "graph_path":  { "type": "string" },
      "ram_path":    { "type": "string" }
    },
    "required": []
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "classes": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "class":         { "type": "string" },
            "query":         { "type": "string" },
            "rag_ms":        { "type": "number" },
            "rag_correct":   { "type": "boolean" },
            "rag_top":       { "type": ["string", "null"] },
            "graph_ms":      { "type": "number" },
            "graph_correct": { "type": "boolean" },
            "graph_seeds":   { "type": "array", "items": { "type": "string" } },
            "verdict":       { "type": "string", "enum": ["both","graph_only","rag_only","neither"] }
          },
          "required": ["class","query","rag_ms","rag_correct","rag_top","graph_ms","graph_correct","graph_seeds","verdict"]
        }
      },
      "summary": {
        "type": "object",
        "properties": {
          "rag_score":   { "type": "integer" },
          "graph_score": { "type": "integer" },
          "n_classes":   { "type": "integer" },
          "speedup":     { "type": ["number","null"] }
        },
        "required": ["rag_score","graph_score","n_classes","speedup"]
      }
    },
    "required": ["classes","summary"]
  }
}
```

## The 5 query classes (hardcoded queries + expected-answer signatures)

| class | what it probes | graph must surface |
|-------|----------------|--------------------|
| PASSAGE | retrieve a narrative episode (churning of the ocean) | entities `samudra`, `amrita` |
| SINGLE-FACT | one atomic relation ("brother of Krishna") | `krishna` + a `brother` edge |
| SCATTERED | a scene whose facts are spread across verses | `krishna` + `arjuna` |
| MULTI-HOP | a relation needing one hop (Krishna→Vishnu avatars) | `krishna`,`vishnu` + an `avatar` edge |
| CROSS-TEXT-ID | identity fused across texts (lineage) | `babaji`,`lahiri` + a `guru` edge |

`rag_correct` = did the top keyword hit come from the expected text namespace.
`graph_correct` = did recall surface the expected entities **and** the required edge.

## Usage

```bash
# from purangpt/ repo root (so tools.read_pass.recall + data/ paths resolve)
venv/bin/python -m tools.rag_vs_graph_bench.check --quick           # fast human table
venv/bin/python -m tools.rag_vs_graph_bench.check --quick --json    # JSON envelope
venv/bin/python -m tools.rag_vs_graph_bench.check --json            # FULL 291k-chunk floor (~35s); the real baseline
```

As a library (tool-to-tool):

```python
from tools.rag_vs_graph_bench.check import run
env = run(quick=True)
assert env["success"]
env["data"]["summary"]   # {'rag_score': ..., 'graph_score': ..., 'speedup': ...}
```

## Output envelope

```json
{ "success": true,
  "data": { "classes": [ ... ], "summary": { "rag_score": 0, "graph_score": 5, "speedup": 6.2 } },
  "metadata": { "quick": true, "corpus_rows": 41630, "quick_stride": 7, "graph_entities": 4262 },
  "errors": [] }
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `graph_manifest.json` or `guruji_ram.json` absent | `success=false`, `errors=[{code:"graph_missing"}]`, exit 2 — does NOT scan the corpus first |
| `all_chunks.jsonl` absent | `success=false`, `errors=[{code:"corpus_missing"}]`, exit 2 |
| `tools.read_pass.recall` import fails (not run from repo root) | `success=false`, `errors=[{code:"recall_import_failed"}]`, exit 2 |
| graph file malformed | `success=false`, `errors=[{code:"graph_load_failed"}]`, exit 2 |
| Normal | `success=true`, exit 0 |

## Interpreting the floor (a real finding, not a bug)

The crude floor normalizes overlap by **query** length, so short generic chunks
(a thesaurus gloss in `amarakosha`, a one-line `brahmasutras` sutra) outrank dense
narrative passages that actually answer the question — which is precisely the
weakness graph recall removes. A typical `--quick` run is **RAG 0/5, GRAPH 5/5,
graph ~6x faster**. The 0/5 and 5/5 scores are stable and reproducible; the
`speedup` and `*_ms` fields are wall-clock and float run-to-run (≈6.2–6.4 in
`--quick`) — a small delta there is noise, not drift. Don't "fix" the floor to score higher; raising the floor would
defeat its purpose as the pgvector baseline. **Validate scope, not just the
envelope:** `--quick` strides so every text is in the sample — a head slice would
make RAG lose only because the expected text was absent (the
`sse_contract_check/FINDINGS.md` failure class). `metadata.quick_stride` lets you
confirm the spread.

## Tests

`venv/bin/python -m tools.rag_vs_graph_bench.test_check` — asserts the keyword-RAG
scorer on a tiny DETERMINISTIC synthetic corpus (right chunk ranked first,
normalized 0..1, honest on no-overlap), the verdict logic is total, the
missing-graph failure path, and the envelope/data schema on a real-artifact run.
Exits 0.
