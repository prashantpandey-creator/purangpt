# source_reality_check

**Is a corpus file REAL Sanskrit, or web/HTML garbage?** — for $0, before any
re-chunk or decode.

Pure Rule-0 decision tree: read a `data/chunks/*.jsonl` (or a raw `.txt`) → scan
the **whole file** → count IAST diacritics, Devanagari, verse markers, and HTML
boilerplate → branch. No LLM, no network.

## Why this exists

The yoga_vasistha incident (2026-06-28): the raw source under
`data/raw_texts/gretil/yoga_vasistha/` was a saved **archive.org details
webpage** — 233 KB of HTML/JS/sentry boilerplate, **0 Devanagari, 0 IAST**. The
derived chunks were slices of that same HTML, and a decode against them produced
**419 hallucinated records** (quarantined). The lesson: before re-chunking or
decoding, *prove the bytes are scripture*.

This answers a **different axis** than [`chunk_marker_audit`](../chunk_marker_audit/README.md):

| tool | question | how |
|---|---|---|
| `chunk_marker_audit` | is it **decode-ready**? | the gate's exact `verify._MARKER_RE`, head-sampled (first N windows) |
| `source_reality_check` | is it **real Sanskrit, not HTML**? | IAST/Devanagari + markers + HTML signal, **whole file** |

The whole-file scan is deliberate: the chunker drops separator-split parts under
10 chars, so a genuinely-real file's *early* short markers (`MU_1,1.1`) vanish and
a head sample can read 0 markers and misjudge it. Scanning everything defeats that
scope trap (pinned by `test_full_file_scan_defeats_head_sample_scope_trap`).

## Descriptor

```json
{
  "tool_name": "source_reality_check",
  "input_schema": {
    "files": "List[str] — chunk .jsonl or raw .txt paths (positional or --input)"
  },
  "output_schema": {
    "files": "[{file, status, chars, iast, devanagari, markers, html_hits, sample_markers, error?}]",
    "real_sanskrit": "List[str]", "html_garbage": "List[str]",
    "suspect": "List[str]", "other": "List[str]",
    "n_files": "int", "n_real": "int", "n_garbage": "int",
    "n_suspect": "int", "n_other": "int"
  }
}
```

`status` ∈ `real_sanskrit` (IAST/Devanagari ≥50 + ≥1 verse marker + ≤2 stray tags)
· `html_garbage` (web boilerplate dominates, negligible script) · `suspect`
(real-looking script but no markers, or tag-contaminated) · `empty` · `missing` ·
`read_failed` (isolated per-file, never fatal).

## Usage

```bash
# the file at the centre of the incident, JSON contract
venv/bin/python -m tools.source_reality_check.check data/chunks/yoga_vasistha.jsonl --json

# raw source + chunks together, human-readable
venv/bin/python -m tools.source_reality_check.check \
  data/raw_texts/gretil/yoga_vasistha/sa_mokSopAya.txt \
  data/chunks/yoga_vasistha.jsonl
```

Exit codes: `0` all real · **`1` = finding** (≥1 file is garbage/suspect/other) ·
`2` = misuse (empty file list).

## Failure modes

| Situation | What the tool does |
|---|---|
| File is a saved web page (tags dominate, ~0 script) | `status: html_garbage` — flagged, never blessed |
| Real IAST file carrying HTML **entities** (`&amp;`, `&#7779;`) — the GRETIL corpus is entity-encoded | still `real_sanskrit`; entities are NOT a garbage signal (pinned by `test_entity_encoded_real_text_is_still_real` — bhagavata carries 390 real `&amp;`) |
| Real Sanskrit but markers are bare 2-component (`1.1`, like yoga_sutras) | `status: suspect` — markers below the a.b.c bar; eyeball before trusting |
| Real file whose first chunks have no surviving marker | still `real_sanskrit` — whole-file scan, not head sample |
| File missing / unreadable | row `status: missing` / `read_failed`; whole run still `success: true` |
| Empty `files` list | `success: false`, `errors: [{code: no_files}]` |

## Tests

```bash
venv/bin/python -m tools.source_reality_check.test_check   # 11 tests, exit 0
```

Fixtures are real captured output (`fixtures/`): `junk_html.jsonl` (first 3 chunks
of the corrupt yoga_vasistha) → `html_garbage`; `real_bhagavata.jsonl` (first 3
chunks of bhagavata) → `real_sanskrit`.
```
