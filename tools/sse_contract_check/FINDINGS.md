# SSE contract findings — why the "drift" events exist & failed

Forensic record from running `sse_contract_check` and tracing git history
(2026-06-21). Kept next to the tool per the Documentation-as-Code rule.

## Summary

The tool's first run reported four "drifting" event types. Investigation shows
**most were false positives caused by a flaw in the tool itself**, plus one
genuinely-removed feature (`guru_pause`). This file records the *why* so the
events aren't mistakenly "fixed" later.

## Event-by-event

| Event | Verdict | Why it exists / why it "failed" |
|-------|---------|--------------------------------|
| `guru_pause` | **Removed (real)** | Was a real feature (commit history); deliberately dropped this session. No longer emitted or handled in either app. |
| `query_translated` | **Not chat drift** | Emitted by `search_gen()` under **`POST /api/sanskrit-search`** (main.py ~1738), a *separate* streaming endpoint from `/api/chat`. The `ChatEvent` union only models `/api/chat`. Introduced in commit `9b9f608` ("PuranGPT v2"); the frontend chat client never consumed it because it was never meant to — it's a different endpoint. |
| `search_complete` | **Not chat drift** | Same: `/api/sanskrit-search` (main.py ~1756). Never referenced in frontend chat files (0 commits ever). |
| `translation_ready` | **Not chat drift** | Same: `/api/sanskrit-search` (main.py ~1773). Belongs to the dual-language Sanskrit result-translation flow, not chat. |
| `info` | **False positive** | Backend `/api/chat` never emits `info`, BUT the frontend `ChatInterface.tsx:471` *does* handle it as legitimate defensive code. "frontend declares, backend never emits" is benign here — not dead code. |

## Root cause of the false positives

`sse_contract_check` v1 greps **every** `{"type": ...}` SSE emit in the whole
`main.py` and compares against the **single** `/api/chat` `ChatEvent` union. But
`main.py` hosts multiple SSE endpoints (`/api/chat`, `/api/sanskrit-search`,
`/api/search`, deep-research). Lumping all their events into one set and diffing
against one frontend contract manufactures phantom drift.

## Why those v2 events were introduced and "failed"

They did not "fail" in the sense of breaking — they were introduced for the
`/api/sanskrit-search` feature and work on that endpoint. They only *look*
failed when measured against the wrong contract. The lesson is about
**measurement scope**, not a frontend bug.

## Action taken

- `guru_pause`: fully removed (separate change).
- The tool is being upgraded to v2: scope extraction to a single endpoint's
  emits (the `/api/chat` SSE generator) so it stops conflating endpoints.
- No frontend change for `query_translated` / `search_complete` /
  `translation_ready` / `info` — they are correct as-is.
