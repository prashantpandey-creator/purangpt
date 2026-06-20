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
- **Vector store:** single Postgres **pgvector** table `purana_verses` (`vector(384)`, JSONB `metadata`, generated `fts`). `hybrid_search` SQL is **hardcoded to that one table** (`scripts/migrate_to_local_pg.py`). Embeddings: `intfloat/multilingual-e5-small` (384-dim), `"passage:"`/`"query:"` prefixes.
- **Sanskrit query expansion (works — don't break):** `backend/query_processor.py` `SanskritQueryProcessor.expand()` → `QueryExpansion` (`embed_phrase`, `fts_phrase`, `gretil_search_terms`, `devanagari`, `synonyms`). Fed into `hybrid_search` + parallel GRETIL scans at `backend/main.py:~1226`. Emits `query_expanded` SSE event.
- **Modes:** `research` (Scholar), `guide` (Guru), `deep` (standalone Deep Research). `/api/chat` SSE.
- **Source text cap:** raised 600 → **2000** chars in `build_source_list` (so full verse + translation surface).

### Frontend — `purangpt-next` (Next.js 16, App Router)
- Landing page keeps the **CitationComparison** (grounded-vs-general). The BG 16.23–16.24 scripture block, corpus bento grid, and locked-sources preview were **moved to `/about`**; About is i18n (en/hi/ru).
- Homepage has a **Guruji/Gita section** (Sanskrit verse → Yogeshwari translation → citation).
- `glass-panel` / `saffron-glow` are global utilities in `globals.css`.

### Known issues / open risks
- **Retrieval ranking bug** (`indexer/search.py:223-230`): `yogic-discourse` Darshan chunks get ×1.6 and the intended ×0.6 penalty is dead (id/purana mismatch) → Darshan intros flood, Puranas + Yogeshwari verses buried.
- **Scholar mode has no Guruji guarantee** (`sharma_weighting=False`).
- **MMR** keyed per-file `purana` → near-duplicate Darshan intros not de-duped.
- **Prod embeddings stale:** 2026-06-16 rebuild restored FTS but did **not** fully re-create semantic vectors → semantic half weak (purely semantic/transliteration queries rank poorly).
- **Darshan citations** collapse to "Introduction, Ch. Introduction" (no chapter/verse metadata).
- **Doc drift:** `README.md` says `e5-large` (stale) vs actual `e5-small/384`.

---

## Ledger (newest first)

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
