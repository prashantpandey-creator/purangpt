# 🟠 PROJECT LEDGER — PuranGPT ("the Daddy")

**Single source of truth for the state of the app and key engineering events.**
Spans both repos: `purangpt` (backend) and `purangpt-next` (frontend).

Every agent MUST:
1. **Before starting** — read **Current State of the App** below.
2. **After finishing any unit of work** — prepend a dated entry to **Ledger (newest first)** and
   update the relevant **Current State** bullet(s) if your change altered them.

> Keep it tight. This file is read at the start of every task — signal, not noise.

### Entry format (copy this)
```
### YYYY-MM-DD — <short title>  · branch/PR · agent
- What & why: <1–3 lines>
- Changed: <files / areas>
- New state / gotchas: <behavior change, traps discovered>
- Follow-ups / risks: <open items, or "none">
```

---

## Current State of the App (snapshot — keep current)

### Backend — `purangpt` (FastAPI RAG)
- **LLM:** prod primary = **Gemini `gemini-2.5-flash`** (`LLM_PROVIDER=gemini`); DeepSeek/Groq fallback. R1 deep-research via DeepSeek.
- **Vector store (schema on branch, NOT yet on prod DB):** code now expects two tables: `purana_verses` (sacred texts, same schema as before) + `guruji_texts` (Guruji commentary/discourse, same columns). `hybrid_search` + `hybrid_search_guruji` SQL functions. **DDL in `scripts/migrate_to_local_pg.py`; row split in `scripts/split_guruji_corpus.py`.**
- **Dual-corpus retrieval:** `search_corpora()` in `indexer/search.py` fetches both tables concurrently, mode-aware merge (Guru=Guruji-first, Scholar=Puranas-primary w/ ≥1-2 Guruji guaranteed). Buggy `sharma_weighting` multiplier removed.
- **Backward compat:** until `guruji_texts` exists in prod, `_fetch_table("hybrid_search_guruji")` returns `[]` gracefully — no crash.
- **Sanskrit query expansion (works — don't break):** `backend/query_processor.py` `SanskritQueryProcessor.expand()` → `QueryExpansion` (`embed_phrase`, `fts_phrase`, `gretil_search_terms`, `devanagari`, `synonyms`). Fed into `search_corpora` + parallel GRETIL scans at `backend/main.py:~1226`. Emits `query_expanded` SSE event.
- **Modes:** `research` (Scholar), `guide` (Guru), `deep` (standalone Deep Research). `/api/chat` SSE.
- **Source text cap:** raised 600 → **2000** chars in `build_source_list` (so full verse + translation surface). Cap 8→10.

### Frontend — `purangpt-next` (Next.js 16, App Router)
- Landing page keeps the **CitationComparison** (grounded-vs-general). The BG 16.23–16.24 scripture block, corpus bento grid, and locked-sources preview were **moved to `/about`**; About is i18n (en/hi/ru).
- Homepage has a **Guruji/Gita section** (Sanskrit verse → Yogeshwari translation → citation).
- `glass-panel` / `saffron-glow` are global utilities in `globals.css`.

### Known issues / open risks
- **DB migration pending:** `guruji_texts` table + `hybrid_search_guruji()` not yet on prod. Run `migrate_to_local_pg.py` DDL then `split_guruji_corpus.py` before merging backend PR. Until then, all results come from `purana_verses` only (safe fallback).
- **Prod embeddings stale:** 2026-06-16 rebuild restored FTS but did **not** fully re-create semantic vectors → semantic half weak (purely semantic/transliteration queries rank poorly).
- **Darshan citations** collapse to "Introduction, Ch. Introduction" (no chapter/verse metadata).
- **Doc drift:** `README.md` says `e5-large` (stale) vs actual `e5-small/384`.

---

## Ledger (newest first)

### 2026-06-20 — Backend: dual-corpus Guruji search · `claude/chat-tier-modes-naming-48z104` (PR pending) · agent(opus)
- What & why: Guruji commentary was flooding results (buggy ×1.6 boost, ×0.6 penalty never matched live ids `sharma-darshan_*`). Plan: separate `guruji_texts` table + mode-aware quota merge so Guruji is reliably *alongside* Puranas (not drowning them).
- Changed: `indexer/search.py` (remove buggy multiplier; add `_fetch_table`, `search_corpora` with dual-corpus concurrent fetch + mode-aware merge + MMR on `source_group`); `backend/main.py` (`/api/chat`, `/api/search`, `/api/infer` → `search_corpora`; cap 8→10; fix edition/tradition/bias getattr bug); `scripts/migrate_to_local_pg.py` (`guruji_texts` table + `hybrid_search_guruji` SQL); `scripts/split_guruji_corpus.py` (NEW — one-off row migration preserving embeddings).
- New state / gotchas: **DDL + row split must run on live DB before merging to main.** Until then, `guruji_texts` fetch returns `[]` gracefully — Puranas still answer. Merge order: (1) run DDL on prod (`migrate_to_local_pg.py`), (2) run `split_guruji_corpus.py`, (3) verify counts, (4) merge PR.
- Follow-ups / risks: full re-embedding of stale prod vectors (offline job); Darshan metadata re-ingest for real chapter/verse citations.

### 2026-06-20 — Create this ledger; reset backend branch to origin/main · `claude/chat-tier-modes-naming-48z104` · agent(opus)
- What & why: stand up a single living knowledge base so agents stop rediscovering app state (e.g. a stale local clone hid the whole Sanskrit query layer). Reset the working branch onto current `origin/main` (`c40cdf4`) before implementing the Guruji-search plan.
- Changed: new `PROJECT_LEDGER.md`; `CLAUDE.md` (+ "Project Ledger" protocol pointer).
- New state / gotchas: local clones can be **badly stale** — always `git fetch` + verify against `origin/main` (the Sanskrit layer landed in `299f890` and was invisible on the old branch tip).
- Follow-ups / risks: implement the approved Guruji-aware search plan (separate `guruji_texts` table, mode-aware merge, weighting-bug removal). Plan at `/root/.claude/plans/harmonic-yawning-umbrella.md`.

### 2026-06-20 — Backend: raise source-text cap 600→2000 · PR #3 (merged) · agent(sonnet)
- What & why: `build_source_list` truncated every chunk to 600 chars, clipping long commentary (e.g. Yogeshwari verse blocks) before the translation. Bumped to 2000.
- Changed: `backend/main.py` `to_frontend_dict` (`:556`).
- New state / gotchas: source cards / raw search now return fuller excerpts.
- Follow-ups / risks: none.

### 2026-06-20 — Frontend: reorg landing → About + i18n; homepage Guruji/Gita section · PRs #16, #17 (merged, deployed) · agent(sonnet)
- What & why: keep CitationComparison on home; move deeper sections to `/about`; translate About (en/hi/ru); add homepage section showing Guruji's Gita translation (verse → translation → citation).
- Changed: `purangpt-next` `src/app/page.tsx`, `src/app/about/*`, `src/lib/i18n.ts`, `src/app/globals.css`.
- New state / gotchas: About is now a server wrapper + `"use client"` `AboutContent` (metadata stays server-side). Sanskrit verses tagged `lang="sa"`.
- Follow-ups / risks: swap the homepage Yogeshwari passage for Guruji's verbatim 16.23–16.24 once pulled from the corpus.
