# decode_audit — the true read_pass comprehension backlog

**Purpose & I/O live in the descriptor (`check.run`).** This file carries only the two
things JSON can't: the failure-mode table and a runnable example (Rule 0, precondition B).

One-line purpose: report, per source text, how many chapter-windows have NO comprehended
chunk — the real work an in-house decode fan-out must do — keyed on the only stable key.

## Why it exists

Hand-counting "how many chapters still need comprehending" gave **three different
answers** (1500, 7061, 2585) in one session, because every obvious key lies:

| naive key | why it lies |
|-----------|-------------|
| filename (`garuda_v1.records.jsonl`) | its first record is actually a **Bhagavata** chapter — files are cross-contaminated |
| `chapter_label` ("Chapter 1") | collides across all 40+ texts; a Bhagavata record falsely marks a Gheranda window done |
| `seq_start` | `group.run` emits different seq values today than at decode time (re-chunking) → phantom gaps |

The one key that is globally unique **and** namespaced by source text is
`_provenance.chunk_ids` (e.g. `bhagavata-1-1`, `gheranda_samhita-0-1`). This tool keys
coverage on that: a chapter-window is **DONE iff any of its chunk_ids appears in any
record on disk**; else **PENDING**. That single change made the count stable and
surfaced the misfiled-records corruption all three hand-counts had masked.

## Output envelope

```json
{ "success": true,
  "data": { "total_pending": 2529, "texts_with_gaps": 43,
            "texts": [ {"text":"garuda","purana":"Garuda Purana","windows":419,"done":0,"pending":419}, ... ],
            "pending_chunk_ids": { "garuda": ["garuda-1-1", ...], ... } },
  "metadata": { "covered_chunks": 190451 }, "errors": [] }
```

`data.pending_chunk_ids` maps each text → the primary chunk_id of every pending chapter;
that's the handoff list the in-house decode fan-out (`tools.read_pass.inhouse`) consumes.

## Usage

```bash
# from purangpt/ repo root
venv/bin/python -m tools.decode_audit.check               # human summary (per-text done/total)
venv/bin/python -m tools.decode_audit.check --json        # JSON envelope
venv/bin/python -m tools.decode_audit.check --min-gap 10  # only texts with >=10 pending
venv/bin/python -m tools.decode_audit.test_check          # fixture tests (exit 0)
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| run from outside `purangpt/` (no `data/chunks/`) | `success=false`, `errors=[{code:"no_chunks"}]`, `data=null`, exit 2 |
| `tools.read_pass.group` import fails | `success=false`, `errors=[{code:"import_failed"}]`, exit 2 |
| a single chunk file won't group | that text skipped, `errors[]` gets `group_failed`, rest still report (partial success) |
| no records on disk yet | `success=true`, every text `done:0` (all pending) — not an error |
| pending work found | `success=true`, exit **1** (a "finding") |
| zero pending | `success=true`, exit 0 |

## Tests

`venv/bin/python -m tools.decode_audit.test_check` — asserts the envelope, the chunk_id
coverage rule, and the **scope test** (a Bhagavata record must NOT mark a Gheranda window
done — the phantom-gap guard). Runs offline against `fixtures.json` (real captured records
+ windows).
