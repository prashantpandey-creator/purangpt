# PROJECT_LEDGER — PuranGPT (backend + frontend)

> The single source of truth for the live state of the whole app. Read **Current
> State** before starting any work. After finishing a unit of work, update Current
> State if it changed the picture, and **prepend** a dated entry to the Changelog
> below (newest first). This file was recreated 2026-07-03 — both `purangpt/CLAUDE.md`
> and `purangpt-next/CLAUDE.md` pointed here already; the file itself had gone
> missing (deleted or never actually created) while the docs kept citing it. The
> Changelog starts today — it is not a backfilled commit history. For anything
> before 2026-07-03, `git log --oneline` on both repos is the real record.

---

## Current State (2026-07-03)

### Auth
Google OAuth + X (Twitter) OAuth 2.0 PKCE + Apple session token, verified directly
against each provider in `backend/auth.py`. **No Logto anywhere in live code paths**
— `auth.py` has zero Logto references (grep-verified). Two things to know before
assuming a totally clean slate:
- `logto_user_id` is still the **live DB column name** in `chat_sessions`
  (`session_manager.py`) — real schema, holds whatever provider's verified user ID,
  just never renamed. Cosmetic, not a dependency; renaming it is a migration nobody
  has asked for.
- A handful of comments (`apple_signin.py:157-158`, `db_client.py:20`, `main.py:133,1707`)
  still say "Logto" in prose describing historical behavior or connection-pool
  sizing lessons. Not live code paths — just unrefreshed wording.
- No email/password path exists — it was built at one point, then removed entirely.

### Voice / TTS
**ElevenLabs Professional Voice Clone is PRIMARY** (`src/lib/voiceEngine.ts`,
`_synthElevenLabs`, ~0.36s). XTTS-v2 (local `:8123` dev / Modal GPU prod, with RVC
timbre conversion) is the **tier-2 fallback**, not primary. This reverses an earlier
2026-06-28 decision that explicitly rejected ElevenLabs — the commit that flipped it
(`4b75fe4`) doesn't explain why. See memory `voice-prod-architecture-modal` for the
full Modal/RVC engineering detail, which is still accurate for the fallback tier.

### Retrieval (GURUJI_MODE — embedding-free)
`GURUJI_MODE=1` skips SentenceTransformer entirely. Path: ILIKE keyword fetch (20
candidates, 0.01s) → Witness LLM judge picks 5 (6-8s, worth it for quality) →
graph-grounded generation (9,006 entities, 24,918 edges, 613 decode keys, always-on
via `GRAPH_MEMORY_ENABLED=1`). Cluster-based retrieval (451 Louvain communities,
`/api/clusters`) replaces the old broken chapter navigator. `e5-small` embeddings
(384-dim) remain dormant in the pgvector schema — not deleted, just unused while
GURUJI_MODE is on. A bge-m3 + Devanagari-normalization upgrade (benchmarked 2×
hit@5 over e5-small) is on ice; it answers a question GURUJI_MODE no longer asks.

### Buddhi layer — shipped, dormant
`backend/buddhi.py` (720 lines, commit `90f6579`), a 3-stage granthi-bheda synthesis
layer between graph_memory+RAG and the chat prompt. Flag `BUDDHI_ENABLED` defaults
OFF; deterministic mode is sub-2ms/zero-cost, LLM mode is built but never called.
Not in the backend CLAUDE.md's "Active production modes" table — easy to miss.
See memory `buddhi-layer-dormant`.

### Frontend surface
Graph Explorer shipped (`/library/graph` — cluster browsing, entity profiles, mobile
list view). Deep Insight (◈) got an "Inner Meanings" collapsible panel. 73 mesh
gradient illustrations (40 Mahabharata/hub deities + 33 Ramayana). Illuminate V2
(display modes + chapter summaries) and a library redesign shipped. The app's front
door (`/`) is a real HTTP 308 → `/chat` (routing-layer redirect in `next.config.ts`,
not a page-level shell) — verified live 2026-07-02.

### Billing
Dual gateway: Stripe (international) + Razorpay (India), Pro at ₹1111/mo, three
coupon codes (`guruji83`, `gurujifullpower`, `guruji`). Razorpay webhook secret was
set 2026-06-22; dashboard-side webhook URL registration is the one step Razorpay's
API can't automate (see memory `pipeline-auth-billing-state`). Not re-verified live
by this ledger's author — code shipped per git log, operational status unconfirmed.

### Infra / reliability
An OOM/crash incident around 2026-07-02 03:15 was resolved by reverting; the backend
now ships an auto-healer pipeline for self-recovery and the frontend deploy has
auto-rollback on failed health check. Container fragility note still holds: large DB
UPDATEs kill the backend container on 8GB — run migrations via `psql` directly on
the Hetzner host, never batch UPDATEs through the Python container.

### Known-hot files (expect concurrent-session churn)
`purangpt-next/src/components/chat/ChatInterface.tsx` took 40+ commits in the last
few days — full background-system replacement, two full palette reversals
(gold↔indigo↔gold), Framer Motion rework. Check `git log` on this specific file
before editing, not just the repo, before assuming your base is current.

---

## Changelog

### 2026-07-03 — Prachar/growth_engine resurrected onto main
Marketing-automation engine (Prachar) was built + smoke-tested 2026-06-26 (commit
`90dc962`) but landed only on stranded feature branches (`claude/graph-repair-
conflation-fix`, `corpus-and-search-fixes`) — never merged to `main`. `growth_engine/`
did not exist on disk on `main` until today. Cherry-picked `90dc962` onto `main`
(clean, zero conflicts — commit only ever touched `growth_engine/` + 4 new `tools/`
dirs, confirmed via full diffstat before picking). Pushed as `c5b1f52`.
**Re-verified green against today's `main`, not just old test output:** all 4 Rule-0
tool suites (`content_policy_check`, `campaign_brief_validate`, `post_scheduler`,
`connector_envelope`) exit 0; `growth_engine.test_schema` passes against the still-live
local `purangpt_dev` Postgres (6 `ge_*` tables present/idempotent); `growth_engine.llm`'s
re-export of `backend.main.{stream_llm,call_llm_once,get_providers}` still resolves
post-drift (Logto removal, GURUJI_MODE, etc. didn't touch these three names). Live
providers available today: groq, gemini, deepseek, openai. Also registered the 4 tools
in `tools/README.md` (`2264f73`) — they shipped tested but were never added to the
registry, making them invisible to Rule 0's "check the registry first" step.
**Still not live-posting:** `growth_engine/` isn't wired into `docker-compose.yml` or
imported by `main.py` (inert on prod by design, zero deploy risk from this push), and
no real X/Telegram API keys exist in any `.env` yet. That's the next real blocker, not
a code problem.

### 2026-07-03
- Recreated this file. Both CLAUDE.md files cited it; it didn't exist (confirmed via
  filesystem + git history search on `purangpt/`). Seeded Current State above from a
  full sync pass across both repos (git log, both CLAUDE.md files re-read against
  actual code, doc_path_audit pre-flight run). Corrected two stale entries in the
  persistent memory system (voice TTS primary-provider reversal, billing refresh-token
  claim) and added two new ones (Buddhi dormant layer, this file's prior absence).
