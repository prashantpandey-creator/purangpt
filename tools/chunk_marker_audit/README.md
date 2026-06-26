# chunk_marker_audit

**Which chunk files are decodable, and which are ungroundable junk** — for $0, before any LLM decode.

Pure Rule-0 decision tree: read each `data/chunks/*.jsonl` → group into chapter
windows → sample the first N → count verse markers with **the same regex the
verify-gate uses** (`verify._MARKER_RE`) → branch. No LLM, no network.

## Why this exists

The verify-gate on the corpus write path (`tools/read_pass/run.py`, commit
`eed9bfa`) **prunes any decoded node whose cite isn't literally in its source
window**. So a decode is only as good as the chunk file's verse markers. We
discovered `decode_audit` was counting `mahabharata.jsonl` — HTML-entity junk
with **zero** markers, which the gate husks 100% — as "pending", while the clean
BORI critical edition (`mahabharata_bori_chunks.jsonl`, `mbh_PP.CCC.VVV` markers
across all 1995 chapters) was never in the count. And it's systemic:
**20 of 51 chunk files carry 0 markers.**

This tool finds them all up front, so we never fan out an expensive decode onto a
file the gate would silently empty. **It must use the gate's exact marker grammar**
(pinned by `test_marker_grammar_matches_the_gate`) — otherwise it could bless a
file the gate then rejects.

## Descriptor

```json
{
  "tool_name": "chunk_marker_audit",
  "input_schema": {
    "files": "List[str] — chunk .jsonl paths (or --scan-all globs data/chunks/)",
    "sample_windows": "int = 3 — how many leading windows to sample per file"
  },
  "output_schema": {
    "files": "[{file, status, windows_total, windows_sampled, markers_found, sample_markers, error?}]",
    "decodable": "List[str]", "needs_normalization": "List[str]",
    "n_files": "int", "n_decodable": "int", "n_needs_normalization": "int",
    "n_missing": "int", "n_empty": "int"
  }
}
```

`status` ∈ `decodable` (markers present) · `needs_normalization` (0 markers → gate
husks) · `missing` · `empty` · `group_failed` (unparseable — isolated, never fatal).

## Usage

```bash
# the whole corpus map, JSON contract
venv/bin/python -m tools.chunk_marker_audit.check --scan-all --json

# one file, human-readable
venv/bin/python -m tools.chunk_marker_audit.check --input data/chunks/skanda.jsonl

# tune the sample depth (more windows = more confident, still cheap)
venv/bin/python -m tools.chunk_marker_audit.check --scan-all --sample 5
```

Exit codes: `0` all clean · **`1` = finding** (≥1 file needs normalization — the
normal corpus state today) · `2` = misuse (empty file list).

## Failure modes

| Situation | What the tool does |
|---|---|
| File has 0 markers in sampled windows | row `status: needs_normalization`, `markers_found: 0` — flagged, NOT decoded |
| File missing on disk | row `status: missing`; whole run still `success: true` |
| `group.run` raises on malformed chunk-ids (e.g. ids without the `-N` suffix) | caught per-file → `status: group_failed` with the exception text; one bad file never blinds the scan (pinned by `test_malformed_file_is_isolated_not_fatal`) |
| Empty `files` list | `success: false`, `errors: [{code: no_files}]` |
| Sparse markers (1–2 per window) | classed `decodable` but expect a **lower grounded_rate** — eyeball `markers_found` before a big run |

## Tests

```bash
venv/bin/python -m tools.chunk_marker_audit.test_check   # 9 tests, exit 0
```

Oracle is frozen real output (`fixtures/known_files.json`): BORI first window =
211 markers → decodable; `mahabharata.jsonl` first window = 0 → needs_normalization.

## The frozen finding (captured 2026-06-26)

`out_scan.json` is the full `--scan-all` envelope at audit time: **30 decodable,
20 need normalization, 1 unparseable (`sharma_texts.jsonl`).** Headline decodable
target: `mahabharata_bori_chunks.jsonl` (1995 ch, dense markers). The 20
zero-marker files (~5,300 ch incl. skanda/padma/brahma_vaivarta and the junk
`mahabharata.jsonl`) are a **separate normalization track** — re-chunk from marked
sources; do not decode blind.
