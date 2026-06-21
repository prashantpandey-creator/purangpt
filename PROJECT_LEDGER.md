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
- **Theme** (2026-06-21): candlelit gold accent `#cba455` (token `--gold` / Tailwind `saffron`), highlight `#e7cd84`, slate `#7e92b8`, ivory text `#e2d4b2`. **Chat page = true-black OLED** (`#000` base/topbar/thread, neutral-dark surfaces `#0e0e11`/`#141416`) — the earlier indigo base was dropped per user request. Landing/marketing still use the warmer dark from globals. Restrained glow only on focal points. Side panel uses warm Quicksand (`--font-sidebar`). Do NOT reintroduce neon `#ff9933`. See CLAUDE.md UI guidelines.

### Known issues / open risks
- **DB migration pending:** `guruji_texts` table + `hybrid_search_guruji()` not yet on prod. Run `migrate_to_local_pg.py` DDL then `split_guruji_corpus.py` before merging backend PR. Until then, all results come from `purana_verses` only (safe fallback).
- **Prod embeddings stale:** 2026-06-16 rebuild restored FTS but did **not** fully re-create semantic vectors → semantic half weak (purely semantic/transliteration queries rank poorly).
- **Darshan citations** collapse to "Introduction, Ch. Introduction" (no chapter/verse metadata).
- **Doc drift:** `README.md` says `e5-large` (stale) vs actual `e5-small/384`.

---

## Ledger (newest first)

### 2026-06-21 — Frontend: contextual follow-up pills after every answer · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: user wants suggestion pills after every answer so seekers can keep going with one tap ("keep user engaged forever"). The old inline `[SUGGESTIONS]` parser in `ChatInterface` was dead — the backend never emits that marker — so follow-ups never appeared. Built a reliable, decoupled system instead of relying on LLM compliance in the answer stream.
- Changed: `purangpt-next` — NEW `src/app/api/followup-suggestions/route.ts` (POST: takes last `{question, answer, mode, language}`, prompts DeepSeek→Gemini for 3 short first-person follow-ups distinct in depth/breadth/practice, language-aware en/hi/ru, evergreen fallback if both LLMs fail; mirrors the `guru-suggestions` infra); `src/components/chat/ChatInterface.tsx` (new `followups` state keyed by assistant msg id; `fetchFollowups` fired on every `done` event; NEW `FollowupPills` component — Sparkles-labelled tap-to-send pills with a shimmer-while-loading skeleton and staggered reveal, rendered ONLY under the latest answer when not streaming).
- New state / gotchas: follow-ups are a **separate LLM call after `done`** (not parsed from answer content) → guaranteed to appear, answer content stays clean. Renders only for `messages[last]` so old turns don't clutter. Stopped/aborted/error answers get no follow-ups (only the `done` branch fires). The legacy inline `[SUGGESTIONS]` parse is left in place (harmless, still dead). No backend deploy needed — route lives in the Next app.
- Follow-ups / risks: adds ~1–3 s + one cheap LLM call per answer; acceptable. If we later want zero extra latency, switch to having the backend append a `[SUGGESTIONS]` block in-stream.

### 2026-06-21 — Frontend: 3D logo wobble + dramatic floating captions in loader · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: user asked for the chat load animation to "rotate on its vertical axis making it 3D" and for the loading text to appear/disappear dramatically at different positions around the animation rather than sitting statically below it.
- Changed: `purangpt-next` — `ui/Logo.tsx` (new `tiltRef` wrapper; rAF loop now adds independent Y+X sinusoidal phases → `perspective(${size*3}px) rotateY()deg) rotateX()deg)` on the tiltRef, giving a slow 3-D rock; amplitude/speed scale with `isThinking`); `chat/SacredGeometryLoader.tsx` (yantra enlarged 144→200 px, 3-D rock added to `svgWrapRef` via same rAF loop; static caption below removed and replaced with two independent `FloatingCaption` slots cycling phrases at diagonal anchor positions — upper-left↔lower-right and upper-right↔lower-left — with a 1.3 s stagger so two captions are always visible simultaneously); `chat/ChatInterface.tsx` (empty-state logo 116→132 px).
- New state / gotchas: **TRAP — tiltRef wrapper must be `display: inline-block` with explicit `width/height`** or it collapses to 0 and the glow/mask disappear. `perspective()` is on `tiltRef`; `overflow: hidden + border-radius` clipping is on `outerRef` (child) — this is the correct order: clip in 2-D then tilt in 3-D so the circle becomes an oval visually.
- Follow-ups / risks: none.

### 2026-06-21 — Fix: ouroboros snake now actually rotates (closest-side mask) · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: the spinning logo never visibly rotated. Root cause: `ui/Logo.tsx` layer masks used `radial-gradient(circle, …)` which **defaults to farthest-corner**, so all % mapped to ~1.41× the radius → the static centre layer covered the whole ring and the rotating layer only held the empty corner margin. Nothing moved.
- Changed: `purangpt-next/src/components/ui/Logo.tsx` — added **`closest-side`** to both masks (100% = edge/half-width, matching the measured profile: figure 0–60%, gap ~67%, ring 70–90%); idle spin 0.3→0.45.
- New state / gotchas: **TRAP — any CSS `radial-gradient`/mask sized in % for the logo MUST use `closest-side`**, or the geometry is off by √2. Verified by simulating both masked layers in PIL (static=figure only, rotating=ring only, head moves on rotation).
- Follow-ups / risks: none.

### 2026-06-21 — Frontend: emblem de-noise + welcome hero redesign + compact sidebar · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: the `logo-emblem.png` shipped with a baked-in **green/teal noise background** (looked corrupt on black & hid the ouroboros). Cleaned it and redesigned the chat welcome hero; tidied the sidebar.
- Changed: `purangpt-next` — `public/logo-emblem.png` (keyed warm-vs-green, removed speckle via scipy connected-components, recentred, → transparent PNG, 1.2MB→250KB), `ui/Logo.tsx` (re-measured radial profile → **mask split moved into the 65–70% gap so ONLY the snake ring rotates**, not the figure; idle spin 0.18→0.3), `chat/ChatInterface.tsx` (welcome hero: larger centred logo, softer gold-gradient Marcellus title, ॥-flanked divider, discipleship line as small dedication), `chat/Sidebar.tsx` (**removed the conversation search box** + its dead state/imports; compacted vertical spacing across header/zones/rows/footer).
- New state / gotchas: emblem is now transparent line-art — if you ever regenerate it, keep bg transparent or the snake mask geometry (figure 0–60%, gap ~67%, ring 70–90% of radius) breaks. Sidebar no longer filters conversations (search removed); `ui.search_placeholder`/`ui.no_match` keys now unused. `tsc` + `next build` clean.
- Follow-ups / risks: no in-browser screenshot possible in this env (no Playwright/Chromium) — verified via static render of the asset + a PIL mock.

### 2026-06-21 — Frontend: chat page → OLED black + uniform topbar + warm sidebar · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: user feedback on the chat page. Moved off the indigo "Twilight" surfaces to a true-black OLED feel and cleaned up several chrome details.
- Changed: `purangpt-next` — `globals.css` (`--bg-deep`/`--dark-bg` → `#000`, surfaces neutral `#0e0e11`/`#141416`, body bg pure black + single faint gold top-glow, no blue radial), `layout.tsx` (html/body → black; **added Quicksand font as `--font-sidebar`** for a warm/curvy side panel), `DashboardShell.tsx` (removed topbar border + made it `#000` uniform with chat; top-right emblem now becomes a profile-initials avatar once `initialized && user`), `Sidebar.tsx` (`--font-ui`/`--font-display` → `--font-sidebar`, tightened over-wide tracking, dropped the "Sacred Texts AI" wordmark tagline via `tagline={null}`), `ChatInterface.tsx` (root/composer/bubble/error bgs → black-neutral; empty-state hint restyled small Marcellus), `i18n.ts` (`ui.welcome_hint` en/hi/ru → "Under the discipleship of Sri Shailendra Sharma").
- New state / gotchas: chat is now pure `#000` across topbar+thread (no divider). Sidebar text uses `--font-sidebar` (Quicksand, latin-only → Devanagari falls back to system). `tsc` + `next build` clean.
- Follow-ups / risks: none.

### 2026-06-21 — Frontend: "Twilight Sanctum" theme + centred empty-state · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: old UI leaned on one neon-saffron (`#ff9933`) sprayed everywhere with heavy halos → read as cheap. Reworked into a researched, restrained palette; also unified the chat empty-state into one centred logo→title→input→suggestions composition (was: title floating mid-screen, input pinned to bottom).
- Changed: `purangpt-next` — `src/app/globals.css` (`:root` tokens, softened glows, indigo body bg), `tailwind.config.ts` (`saffron` → `#cba455`), `src/components/chat/ChatInterface.tsx` (centred empty state, viewport-bound mobile keyboard), `Logo.tsx` (softer glow), ~200 hex/rgb literals swept across components. `CLAUDE.md` UI guidelines rewritten to lock the direction.
- New state / gotchas: Palette = indigo-aubergine base `#0A0810` / surfaces `#141121`·`#16131F`, candlelit gold `#cba455` (token `--gold`, Tailwind `saffron` class), highlight `#e7cd84`, aged brass `#b8893b`, moonlit slate `#7e92b8`, ivory text `#e2d4b2`. Glow reserved for focal points via `--glow-gold-*` (≤0.30 alpha). **TRAP: Tailwind arbitrary values can't contain spaces — write `rgba(203,164,85,0.3)` no-space inside `[...]`.** Don't reintroduce `#ff9933`.
- Follow-ups / risks: none — `tsc --noEmit` + `next build` both clean.

### 2026-06-21 — Fix: chat dead-air / 60s hang — cap query-expansion LLM call · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: prod chat streamed **zero tokens for 60s** then closed. Root cause: the Sanskrit query-expansion step (`SanskritQueryProcessor._expand_sanskrit`) calls the LLM via `call_llm_once`, whose shared aiohttp client has a 60s timeout. Under DeepSeek slowness this blocks the whole `/api/chat` *before* search or generation — pure dead air. Expansion is only a nice-to-have and already has a graceful passthrough fallback, so it must never stall the stream.
- Changed: `backend/query_processor.py` — `import asyncio`; new `EXPANSION_TIMEOUT_S` (env-tunable, default 8s); wrapped the expansion `_call_llm` in `asyncio.wait_for(...)`; added an explicit `asyncio.TimeoutError` log → falls through to the existing passthrough `QueryExpansion`.
- New state / gotchas: chat now starts within ≤8s even if expansion's LLM is unresponsive (it degrades to the raw query). Generation keeps its own longer timeout. **Two prod-infra issues remain (need SSH, not code):** `/api/status` shows `index_ready:false` + `total_verses:0` (vector index/DB down → only GRETIL grounding), and `llm_provider` has fallen back from Gemini to **deepseek**.
- Follow-ups / risks: needs to reach `main` to deploy (backend deploys only on push to main w/ backend paths). This branch also carries the **un-migrated dual-corpus** work — do NOT bulk-merge to main without running the DDL; prefer a clean hotfix branch off `origin/main` carrying only this change. Fix prod DB/index + Gemini key separately via SSH.

### 2026-06-21 — AI merge-conflict bot for claude/** branches (both repos) · `claude/chat-tier-modes-naming-48z104` · agent(sonnet)
- What & why: a drifted `claude/**` branch kept conflicting with `main` in the frontend deploy's auto-merge step, which **silently skipped the deploy** (root cause of "logo changes never showed up"). Added a bot so this self-heals.
- Changed: NEW `.github/scripts/ai-merge-resolve.py` (stdlib-only; resolves conflict markers via free-tier Gemini `gemini-2.0-flash`), NEW `.github/scripts/merge-bot.sh` + `.github/workflows/merge-bot.yml` (on push to main: merge main into each active claude/** branch, AI-resolve, push, open one deduped issue if it can't; skips branches idle >30d). Frontend also made its `deploy.yml` auto-merge step AI-assisted. Same files added to **both** repos.
- New state / gotchas: needs `GEMINI_API_KEY` repo secret (backend already has it; **verify/add on `purangpt-next`**). Branch pushes use `GITHUB_TOKEN` → don't re-trigger workflows (no loops/surprise deploys). File contents are sent to Gemini free tier — fine for now, swap to paid key if data policy tightens. Bot in this repo only activates once `merge-bot.yml` reaches `main`.
- Follow-ups / risks: confirm `GEMINI_API_KEY` exists as an Actions secret in `purangpt-next`; otherwise the frontend bot falls back to opening issues instead of auto-resolving.

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
