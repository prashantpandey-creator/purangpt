# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

PuranGPT backend — a FastAPI RAG engine for querying Hindu sacred texts (18 Mahapuranas, Ramayana, Mahabharata, Gita, Upanishads) with exact verse citations and streaming LLM responses.

## Access & secrets for sessions (how to be fully operational)

Any session on this machine already has what it needs — these are the entry points:

- **GitHub (create/merge PRs, push):** authed via the `gh` CLI keyring (account
  `prashantpandey-creator`, HTTPS remotes). Just use `git push`, `gh pr create`,
  `gh pr merge`. No SSH key needed for git. Verify with `gh auth status`.
- **Secrets (decrypt/edit):** managed by **SOPS + age**. All secrets are encrypted
  in `secrets/prod.enc.yaml` (committed). Decrypt with `sops -d secrets/prod.enc.yaml`
  — this works automatically when the **age private key is present at
  `~/.config/sops/age/keys.txt`** (distributed out-of-band; NEVER committed, never
  pasted into any tracked file — that would defeat the whole scheme). See
  `secrets/README.md` for edit/rotate/grant-access workflow.
- **Server (SSH):** `ssh -i ~/.ssh/purangpt_hetzner root@204.168.176.229`.
- **Deploy:** push to `main` → GitHub Actions deploys (see `DEPLOY.md`).
- **Full operational state, keys, and the security-incident history** are in the
  gitignored `CLAUDE-secrets.md` (read it before any deploy/server/DB work).

> Why the age key is NOT in this file: `secrets/prod.enc.yaml` is only safe to commit
> because the key lives outside the repo. Putting the key in a tracked file would let
> anyone with repo access decrypt every production secret.

## Current Production Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + uvicorn (port 8000) |
| LLM | Gemini (`gemini-2.5-flash`, current prod primary via `LLM_PROVIDER=gemini`); DeepSeek/Groq fallback |
| Vector search | Postgres **pgvector** + FTS via `hybrid_search` SQL function (`indexer/search.py` → `HybridSearcher`) |
| Profiles/billing | Same Postgres DB (`backend/db_client.py`, psycopg2) |
| Sanskrit corpus | GRETIL (42 texts, ~40M chars, loaded at startup into memory) |
| Embeddings | `intfloat/multilingual-e5-small` (384-dim) — generated locally, stored in pgvector |
| Research mode | `backend/agents/deep_research.py` — DeepSeek-R1 reasoner with streamed `reasoning_content` |

**There is no Supabase, no ChromaDB, no Pinecone, no Ollama in production.** Those existed in earlier versions and are gone.

## Key Files

```
backend/
  main.py           # FastAPI app — all routes, AppState, startup/shutdown
  db_client.py      # Postgres psycopg2 helpers: profiles, billing, usage_logs
  auth.py           # Logto JWT verification + profile upsert
  session_manager.py # Schema bootstrap (CREATE TABLE IF NOT EXISTS)
  billing.py        # Subscription/usage checks
  monitor.py        # /api/admin/monitor health check (DB + LLMs + pgvector)
  agents/
    deep_research.py # DeepSeek-R1 research: query gen → DuckDuckGo → reasoner synthesis

engine/
  query_engine.py   # PuranGPTEngine: SSE stream orchestration
  prompts.py        # Mode prompts: scholar, yogic, compare, guide (Guru mode), etc.

indexer/
  search.py         # HybridSearcher — asyncpg pool + sentence-transformers → pgvector RRF
  build_index.py    # One-time indexer: chunks JSONL → pgvector (run offline, not at startup)

data_pipeline/      # Offline text ingestion (download → extract → chunk → index)
  downloader.py     fetch_*.py scripts  # PDF + web scrapers for text acquisition
```

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `VECTOR_DB_URL` | **Yes** | `postgresql://logto:logto@logto-db:5432/logto` in Docker; without it `index_ready: false` |
| `DEEPSEEK_API_KEY` | Yes | Primary LLM + R1 research mode |
| `GROQ_API_KEY` | No | Fallback LLM |
| `GEMINI_API_KEY` | No | Second fallback |
| `LOGTO_ENDPOINT` | No | Auth JWT issuer verification |

In Docker the service hostname for the DB is `logto-db` (same container as Logto auth). Outside Docker use `localhost:5432`.

## Commands

```bash
# All python commands use the local venv
venv/bin/python run.py              # start server (:8000)
venv/bin/python run.py --dev        # hot-reload
venv/bin/python run.py --status     # health check (indexes, LLM providers)

# Syntax check (no test suite)
venv/bin/python -m py_compile backend/main.py
venv/bin/python -m py_compile indexer/search.py

# Ad-hoc smoke tests (run directly)
venv/bin/python test_db.py
venv/bin/python test_search.py
venv/bin/python test_deep_research.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | SSE streaming chat (main endpoint) |
| POST | `/api/search` | Raw hybrid search |
| GET | `/api/status` | Health: `index_ready`, `total_verses`, LLM provider |
| GET | `/api/admin/monitor` | Full health: DB, pgvector, LLM latencies |

SSE events from `/api/chat`: `sources` → `reasoning` (R1 only) → `token` × N → `done`

## Chat Modes

Defined in `backend/main.py` (`PROMPTS` dict — `RESEARCH_SYSTEM`, `GUIDE_SYSTEM`),
advertised via `GET /api/modes`, and must stay in sync with the frontend's
`QueryMode` type in `purangpt-next/src/lib/api.ts`. There are **two** modes:

- `research` — **Scholar Mode**: academic, mandatory structure (Summary → Extracted Sacred Texts → Explanation), inline `[1]` citations. UI label "Scholar Mode".
- `guide` — **Guru Mode**: warm, concise single-paragraph guidance in Guruji Sri Shailendra Sharma's voice, no citation clutter. Retrieval applies `sharma_weighting`. UI label "Guru Mode".

(The earlier `yogic`/`compare`/`translate`/`find_instances` modes no longer exist.)

A third mode, `deep` — **Deep Research** (`backend/agents/deep_research.py`) — is a
**standalone** web-grounded mode, intentionally kept out of the in-chat Scholar/Guru
toggle. It is reached only via the side-panel "Deep Research" link → the
`/dashboard/deep-research` page, which sends `mode: "deep"`. The `/api/chat` handler
dispatches `mode == "deep"` to the interactive two-stage agent (clarifying question →
DuckDuckGo search → DeepSeek-R1 synthesis with streamed `reasoning`). Frontend
`QueryMode` is `guide | research | deep`; the `/chat` route only maps `guide | research`
so deep can never appear as a chat toggle.

## Deploy

GitHub Actions (`.github/workflows/deploy.yml`) triggers on push to `main` when backend files change. It SSHes to Hetzner (`204.168.176.229`), hard-resets the tree, and rebuilds the Docker container. Requires `VPS_SSH_KEY` secret on `prashantpandey-creator/purangpt`.

**Never edit files directly on the server** — it dirties the git tree and silently blocks future deploys.
