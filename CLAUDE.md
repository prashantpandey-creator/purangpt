# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

PuranGPT backend — a FastAPI RAG engine for querying Hindu sacred texts (18 Mahapuranas, Ramayana, Mahabharata, Gita, Upanishads) with exact verse citations and streaming LLM responses. The Guru persona is Shailendra Sharma — a living Yogi and custodian of the unbroken lineage of Yoga.

## Access & secrets for sessions (how to be fully operational)

Any session on this machine already has what it needs — these are the entry points:

- **GitHub (create/merge PRs, push):** authed via the `gh` CLI keyring (account
  `prashantpandey-creator`, HTTPS remotes). Just use `git push`, `gh pr create`,
  `gh pr merge`. No SSH key needed for git. Verify with `gh auth status`.
- **Secrets:** managed via **GitHub Repository Secrets** (source of truth for deploys).
  The deploy workflow renders `/root/purangpt/.env` from these secrets on every push to `main`.
  A SOPS-encrypted backup lives at `secrets/prod.env` (decrypt with `sops -d secrets/prod.env`
  if needed — requires age key at `~/.config/sops/age/keys.txt`). See `secrets/README.md`.
- **Server (SSH):** `ssh -i ~/.ssh/purangpt_hetzner root@204.168.176.229`. The user has
  authorized fully autonomous SSH/DB/deploy operations — no permission prompts needed.
- **Deploy:** push to `main` → GitHub Actions deploys (see `DEPLOY.md`).
- **Full operational state, keys, and the security-incident history** are in the
  gitignored `CLAUDE-secrets.md` (read it before any deploy/server/DB work).

## Current Production Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + uvicorn (port 8000) |
| LLM | **DeepSeek only** — `deepseek-chat` for chat, `deepseek-reasoner` for Deep Research. No other provider exists (Gemini/Groq/Ollama/Together/Zhipu were removed 2026-06). |
| Vector search | Postgres **pgvector** + FTS via `hybrid_search` SQL function (`indexer/search.py` → `HybridSearcher`) |
| Profiles/billing | `purangpt-pgvector-1` (same DB as vectors, using `VECTOR_DB_URL`, `backend/db_client.py`) |
| Sanskrit corpus | GRETIL (42 texts, ~40M chars, loaded at startup into memory) |
| Embeddings | `intfloat/multilingual-e5-small` (384-dim) — generated locally, stored in pgvector |
| Research mode | `backend/agents/deep_research.py` — DeepSeek-R1 reasoner with streamed `reasoning_content` |

**There is no Supabase, no ChromaDB, no Pinecone, no Ollama in production.** Those existed in earlier versions and are gone.

**LLM provider — DeepSeek ONLY.** `stream_llm` and startup validation route exclusively to DeepSeek; `LLM_PROVIDER` is ignored. Gemini/Groq/Ollama/Together/Zhipu code, keys, and `stream_*` functions have been deleted — do **not** reintroduce them or call a `stream_gemini`/`stream_groq` (they don't exist; doing so previously 500'd every chat). Deep Research uses `deepseek-reasoner` via its own client.

## Common Issues & Gotchas

- **SSE Yielding format**: When yielding events to `EventSourceResponse` (sse_starlette), the yielded dictionary MUST contain valid SSE kwargs like `data`, `event`, `id`, or `retry`. Do not yield arbitrary dicts like `{"type": "status", "message": "..."}` directly, as it will cause a `TypeError: ServerSentEvent.__init__() got an unexpected keyword argument`. A `safe_sse_stream` wrapper is now used in `backend/main.py` to auto-correct malformed dicts into a `{"data": json.dumps(...)}` format to prevent these crashes.
- **LLM Routing and `<think>` tags**:
  - `stream_llm(req_model="auto")` resolves to `state.active_model` (always `deepseek-chat`). DeepSeek is the only provider — `LLM_PROVIDER` is intentionally ignored.
  - When querying DeepSeek for JSON-only responses (like in `SanskritQueryProcessor`), remember that DeepSeek reasoning models will output `<think>...</think>` tags alongside the JSON. The JSON parser must strip `<think>` tags before calling `json.loads` to prevent crashes.

## Key Files

```
backend/
  main.py            # FastAPI app — all routes, AppState, startup/shutdown, ALL prompts live here
  db_client.py       # Postgres psycopg2 helpers: profiles, billing, usage_logs
  auth.py            # Logto JWT verification + profile upsert
  session_manager.py # Schema bootstrap (CREATE TABLE IF NOT EXISTS)
  billing.py         # Subscription/usage checks
  monitor.py         # /api/admin/monitor health check (DB + LLMs + pgvector)
  agents/
    deep_research.py # DeepSeek-R1 research: query gen → DuckDuckGo → reasoner synthesis

indexer/
  search.py          # HybridSearcher — asyncpg pool + sentence-transformers → pgvector RRF
  pg_ingest.py       # One-time indexer: chunks JSONL → pgvector (run offline, not at startup)

data_pipeline/       # Offline text ingestion (download → extract → chunk → index)
  downloader.py / fetch_*.py  # PDF + web scrapers for text acquisition
```

## Prompt Architecture (as of 2026-06)

There is **one single prompt** in production: `UNIFIED_SYSTEM` in `backend/main.py`.

- `RESEARCH_SYSTEM` and `GUIDE_SYSTEM` have been **deleted** — they were dead code. Do not recreate them.
- `PROMPTS` dict maps `chat`, `research`, and `guide` all to `UNIFIED_SYSTEM`.
- `GURUJI_PERSONALITY` is a separate constant injected as `{personality}` into every response.

### How UNIFIED_SYSTEM works

It is **ONE voice with TWO registers** that the model selects per query:

1. **Guru register** (default): Warm, direct, first-person. Max 2-3 sentences. No bullet points. No `[1]` citations. Scripture woven in as lived truth. Used for personal, spiritual, practical, or open-ended questions.
2. **Scholar register**: Structured layout (Summary → Extracted Sacred Texts → Explanation with `[1]` inline citations). Only activated when the user explicitly asks for sources, exact verses, or scholarly analysis.

### Prompt Separation: Voice vs. Policy

- **`GURUJI_PERSONALITY`** contains purely voice, tone, and worldview instructions (e.g., bare/direct tone, precise examples, no mystical abstractions).
- **`UNIFIED_SYSTEM`** contains the strict behavioral policy (`## Behavioral Rules & Guardrails`):

1. **Brevity is wisdom.** Maximum 2-3 sentences for most answers. Never exceed 1-2 short paragraphs.
2. **Practice & Initiation Limit.** The Guru NEVER gives pranayama, kriya, bandha, or mudra instructions from general knowledge. Practice may only be shared if explicitly present in retrieved passages. Otherwise deflect: *"This practice belongs to the direct relationship between Guru and disciple. The practice finds you when the Guru finds you."*
3. **Seeker Context Subtlety.** The model must never explicitly mention the silent metadata (location, time, device) it receives.

### The [GURU_PAUSE] token
When the model emits `[GURU_PAUSE]` on its own line, the SSE stream parser intercepts it (line ~1517 of `main.py`) and emits a `{"type": "guru_pause"}` SSE event. The frontend renders this as an inline sacred geometry animation. Instructed to use sparingly (0 or 1 per response) after profound statements.

### Seeker Context (`build_seeker_context`)

Every chat request calls `build_seeker_context(req, user, guest_id, history_len)` which assembles tonal instructions from:
- Identity (signed-in vs guest)
- Conversation depth (first message / early / deep)
- Browser `Accept-Language` header (locale → cultural tone)
- `User-Agent` (mobile vs desktop)
- IP-based country/timezone — resolved **entirely in-process** using Python's `ipaddress` stdlib + a static CIDR range table. **No external HTTP calls. No third-party dependency. Zero latency.**

This context is injected as `{seeker_context}` into `UNIFIED_SYSTEM`. It is phrased as behavioral tone instructions (not raw data), so the model adapts naturally without being able to accidentally quote back metadata. The model is also explicitly instructed to **never mention location, local time, device, or travel status** to the seeker.

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `VECTOR_DB_URL` | **Yes** | `postgresql://postgres:postgres@pgvector:5432/purangpt` in Docker (pgvector container, NOT logto-db). Without it `index_ready: false`. Stored in GitHub secret `VECTOR_DB_URL`. |
| `DEEPSEEK_API_KEY` | **Yes** | The ONLY LLM key. Powers chat (`deepseek-chat`) + Deep Research (`deepseek-reasoner`). Without it chat cannot generate. |
| `LLM_PROVIDER` | No | **Ignored** — kept only for backward compat. DeepSeek is always used regardless of value. |
| `FERNET_KEY` | Yes | Encrypts sensitive user data at rest; fail-fast in prod if missing |
| `LOGTO_ENDPOINT` | No | Auth JWT issuer verification |

In Docker the pgvector DB service name is `purangpt-pgvector-1` (a separate container from `logto-db`). Outside Docker use `localhost:5433` (mapped port).

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

SSE events from `/api/chat`: `sources` → `reasoning` (R1 only) → `token` × N → `guru_pause` (optional) → `done`

## Chat Modes

Defined in `backend/main.py` (`PROMPTS` dict), advertised via `GET /api/modes`, and kept in sync with the frontend `QueryMode` in `purangpt-next/src/lib/api.ts`. There is now **one user-facing chat mode** plus the standalone Deep Research mode:

- `chat` — **PuranGPT** (the only chat mode): uses `UNIFIED_SYSTEM`. The model reads each query and chooses its register: **Guru** by default, **Scholar** only when explicitly asked for sources/citations/analysis. Retrieval always runs; the SSE `sources` event is always emitted.
- `research` / `guide` — **legacy aliases**, both resolve to `UNIFIED_SYSTEM`. No separate prompt exists for these — do not create one.
- `deep` — **Deep Research** (`backend/agents/deep_research.py`): **standalone** web-grounded mode, reached only via the side-panel "Deep Research" link → `/dashboard/deep-research` page (sends `mode: "deep"`). `/api/chat` dispatches `mode == "deep"` to the two-stage agent (clarify → DuckDuckGo → DeepSeek-R1 synthesis with streamed `reasoning`).

`ChatRequest` also carries per-user `temperature` (clamped 0.0–1.5, default 0.3), `verbosity` (`concise|balanced|detailed`), and `address_as` (how the assistant addresses the seeker); the latter two are woven into the system prompt alongside the language instruction.

(The earlier `yogic`/`compare`/`translate`/`find_instances` modes no longer exist.)

## Deploy

GitHub Actions (`.github/workflows/deploy.yml`) triggers on push to `main` when backend files change. It SSHes to Hetzner (`204.168.176.229`), hard-resets the tree, and rebuilds the Docker container. Requires `VPS_SSH_KEY` secret on `prashantpandey-creator/purangpt`.

**Never edit files directly on the server** — it dirties the git tree and silently blocks future deploys.
