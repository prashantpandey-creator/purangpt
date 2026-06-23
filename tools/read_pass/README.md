# read_pass

Proactive comprehension of the Puranas — **read once, emit three** (consciousness
graph + story corpus + distilled teachings), each citing back to source verses.
Full design rationale: [ARCHITECTURE.md](ARCHITECTURE.md).

Built so far:
- `group.py` — deterministic chapter grouper (verse-chunks → chapter windows). The spine.
- `schema.py` — the per-chapter output schema (graph+story+teachings) + validator.
- `comprehend.py` — reads one window through the Sharma lens via **Gemini**
  (`gemini-3.5-flash`), returns the validated record. Network call is injectable for tests.
- `run.py` — resumable orchestrator: slice → comprehend each → append to `out/*.jsonl`.

### Run the read-pass (needs `GEMINI_API_KEY`)

```bash
GEMINI_API_KEY=... venv/bin/python -m tools.read_pass.run \
  --input data/chunks/bhagavata.jsonl --tag bhagavata_c10 --start 20000 --limit 30 --json
```
Resumable: re-running skips windows already in `out/<tag>.progress.jsonl`. Outputs
`out/<tag>.records.jsonl` (full records). Proven: 8 Bhagavata chapters →
120 entities / 50 relationships / 30 lens-decoded teachings, ~27s/chapter on Flash.

**The grouper (`group.py`) details below — it's the part that silently corrupts
everything if wrong.**

## Descriptor

```json
{
  "tool_name": "read_pass.group",
  "input_schema": { "jsonl_path": "string (path to a *.jsonl chunk file)" },
  "output_schema": {
    "windows": [{
      "purana": "string", "chapter_label": "string",
      "seq_start": "int", "seq_end": "int", "n_chunks": "int",
      "chunk_ids": "string[]", "verse_ranges": "any[]", "text": "string"
    }]
  }
}
```

## Usage

```bash
# from purangpt/ repo root (so package imports resolve)
venv/bin/python -m tools.read_pass.group --input data/chunks/bhagavata.jsonl --json
venv/bin/python -m tools.read_pass.group --input data/chunks/bhagavata.jsonl   # human summary

# tests (must exit 0)
venv/bin/python -m tools.read_pass.test_group
```

## Failure modes

| Condition | Envelope | code |
|-----------|----------|------|
| Path does not exist | `success:false`, `data:null` | `no_file` |
| File unreadable / bad JSON line | `success:false`, `data:null` | `read_error` |
| File has zero chunks | `success:false`, `data:null` | `empty` |
| OK | `success:true`, `data.windows[]` | — |

## Why grouping is by contiguous run, not by `chapter` value

Chunk ids are `<purana>-<chapterField>-<globalSeq>`. The `chapter` field is not
canto-aware and the same value recurs in different cantos; the trailing
`globalSeq` is monotonic. A chapter window is therefore a **contiguous run of
identical `chapter` value in global-seq order** — bucketing by `chapter` value
would merge unrelated chapters from different cantos. Verified on the real
Bhagavata: 21,884 chunks → 338 windows (median 64 chunks / 977 words each).
`test_group.py` locks this against a captured real fixture
(`fixture_bhagavata_head.jsonl`).
