# CLAUDE.md

> **⚠️ AGENT ONBOARDING — Read this first.** This file is the trigger for all
> agents working on this repo. Start here, then follow the chain below.

## Agent Quick-Start (30 seconds)

```
1. READ THIS FILE (you are here) — architecture, settled decisions, active modes
2. READ PROJECT_LEDGER.md (sibling repo) — current state, latest changes, blockers
3. READ .agents/AGENTS.md — engineering rules (Rule 0: Orchestrator-First)
4. READ CLAUDE-secrets.md (gitignored) — keys, server access, deploy auth
```

**Settled decisions — do NOT reopen without owner approval:**
- ❌ No embeddings: `GURUJI_MODE=1` skips SentenceTransformer. Embedding model is NOT loaded.
- ❌ No Supabase, no ChromaDB, no Pinecone, no Ollama. Single Postgres/pgvector.
- ❌ No provider-specific streaming functions. `stream_llm` is the single provider-agnostic path.
- ❌ No Logto branded UI. Auth is direct Google OAuth + API-driven email.
- ✅ Cluster-based retrieval replaces broken chapter navigation (451 Louvain communities)
- ✅ Witness LLM judge picks 5/20 relevant verses (costs 6-8s, worth it)
- ✅ Compact system prompt (1,029 chars, 81% smaller than original)
- ✅ ILIKE keyword verse fetch (0.01s, random ordering, no embeddings)
- ✅ Graph memory always-on (9,006 entities, 24,918 edges, 613 decode keys)

**Active production modes:**
| Env Var | Effect |
|---------|--------|
| `GURUJI_MODE=1` | Skip embeddings, use ILIKE + Witness + Graph |
| `GRAPH_MEMORY_ENABLED=1` | Inject entity relationships + decode keys |
| `LLM_PROVIDER=deepseek` | Active LLM (OpenRouter/Gemini as fallback) |

**Corpus state (2026-07-02):**
- 303,921 total verses. 141K chapter=0 (was 163K, Ramayana 12,681 fixed).
- Cluster-based retrieval via /api/clusters replaces broken chapters.
- 12,351 encoding corruption markers. 19,415 Sanskrit without diacritics.
- 0 English translations. Mahabharata 53K needs BORI replacement.
- Marker migration is in-progress — run via psql on host, NOT container (OOM).

**Container fragility:** Large DB UPDATEs kill the backend container (OOM on 8GB).
Always run migrations via `psql` directly on the Hetzner host against pgvector:5432.
Never run batch UPDATEs through the Python container.

## What This Is

PuranGPT monorepo — backend (FastAPI RAG engine) + frontend (Next.js 16). The default identity is Shakti — an LLM woven with the Puranic knowledge graph, reading through Shailendra Sharma's decryption lens, speaking as any form in the web.

Frontend code lives in `frontend/`. Backend code is at the repo root. Single docker-compose builds both. Single deploy pipeline.

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
| LLM | **Generic key-driven providers** — `get_providers()` in `main.py` reads a list of OpenAI-compatible endpoints (deepseek, groq, openai, openrouter, together, xai, mistral) and uses whichever have a real key, in priority order, with automatic failover. DeepSeek is just the first default. Deep Research uses `deepseek-reasoner` via its own client. |
| Vector search | Postgres **pgvector** + FTS via `hybrid_search` SQL function (`indexer/search.py` → `HybridSearcher`) |
| Profiles/billing | `purangpt-pgvector-1` (same DB as vectors, using `VECTOR_DB_URL`, `backend/db_client.py`) |
| Sanskrit corpus | GRETIL (42 texts, ~40M chars, loaded at startup into memory) |
| Embeddings | `intfloat/multilingual-e5-small` (384-dim) — generated locally, stored in pgvector |
| Research mode | `backend/agents/deep_research.py` — DeepSeek-R1 reasoner with streamed `reasoning_content` |

**There is no Supabase, no ChromaDB, no Pinecone, no Ollama in production.** Those existed in earlier versions and are gone.

**LLM providers — generic and key-driven (no hardcoded provider).** As of 2026-06,
`stream_llm` is fully provider-agnostic. It calls `get_providers()`, which returns every
provider in `_PROVIDER_DEFS` that has a real env key (`DEEPSEEK_API_KEY`, `GROQ_API_KEY`,
`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `TOGETHER_API_KEY`, `XAI_API_KEY`, `MISTRAL_API_KEY`),
plus a per-request BYOK key on top. All of these speak the **same OpenAI `/chat/completions`
protocol**, so a single `stream_one_provider()` serves all of them — there are **no
provider-named streaming functions** anymore (the old `stream_gemini`/`stream_deepseek`/
`stream_groq` are gone, and that is intentional — do not add them back; that pattern caused
recurring `NameError` crashes). `stream_llm` streams from the first working provider and
fails over to the next ONLY before any token is emitted. Per-provider model overrides via
env (`DEEPSEEK_MODEL`, `GROQ_MODEL`, …). To add/swap a provider: set its env key — no code
change. Deep Research uses `deepseek-reasoner` via its own client (`backend/agents/deep_research.py`).

## Common Issues & Gotchas

- **SSE Yielding format**: When yielding events to `EventSourceResponse` (sse_starlette), the yielded dictionary MUST contain valid SSE kwargs like `data`, `event`, `id`, or `retry`. Do not yield arbitrary dicts like `{"type": "status", "message": "..."}` directly, as it will cause a `TypeError: ServerSentEvent.__init__() got an unexpected keyword argument`. A `safe_sse_stream` wrapper is now used in `backend/main.py` to auto-correct malformed dicts into a `{"data": json.dumps(...)}` format to prevent these crashes.
- **LLM Routing and `<think>` tags**:
  - `stream_llm(req_model="auto")` lets each configured provider use its own default model. Pass `"<provider>:<model>"` (e.g. `"deepseek:deepseek-reasoner"`) to pin a model, or any plain string to override the model on every provider. Routing re-reads `get_providers()` per request, so a key added at runtime works without restart.
  - Reasoning models (`deepseek-reasoner`, or any model whose name contains `reasoner`/`thinking`) reject a `temperature` param — `stream_one_provider` omits it automatically. They also emit `reasoning_content` (surfaced as `{"type":"reasoning"}` SSE) and may wrap JSON in `<think>...</think>` — `SanskritQueryProcessor` strips those before `json.loads`.
- **Corpus separation is APP-LAYER — do NOT add a `guruji_texts` table.** Guruji/Sharma content and the Purana corpus share the **single `purana_verses` table**; they are split in Python by a `corpus_type` kwarg in `HybridSearcher.hybrid_search` (`GURUJI_CATEGORIES` ∪ `id LIKE 'darshan-%'` = Guruji; scripture = the complement). The chat handler runs two parallel channels per turn (citable `scripture` + non-citable `guruji` voice-context) plus a scripture-floor fan-out; Guruji is kept out of citations by a triple guard (`corpus_type` filter → `sharma_weighting` → `is_sharma_text`). A two-table `guruji_texts`/`hybrid_search_guruji` design + `scripts/split_guruji_corpus.py` was prototyped on a feature branch and **abandoned/superseded** — running that split would physically move Guruji rows out of `purana_verses` and break the `corpus_type` filter and the scripture floor (both query the unified table). If physical separation is ever wanted, design it fresh against this `corpus_type` model.

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
- `SHAKTI_IDENTITY` is a separate constant injected as `{personality}` into every response.

### How UNIFIED_SYSTEM works

It is **ONE voice with TWO registers** that the model selects per query:

1. **Direct register** (default): Bare, direct, first-person. Max 2-3 sentences. No bullet points. No `[1]` citations. Scripture woven in as your own knowing. Used for personal, spiritual, practical, or open-ended questions.
2. **Scholar register**: Structured layout (Summary → Extracted Sacred Texts → Explanation with `[1]` inline citations). Only activated when the user explicitly asks for sources, exact verses, or scholarly analysis.

### Prompt Separation: Voice vs. Policy

- **`SHAKTI_IDENTITY`** contains the system's self-awareness: an LLM woven with the Puranic knowledge graph, transparent about what it is, fluid across forms. Voice is bare/direct/precise, no mystical abstractions.
- **`UNIFIED_SYSTEM`** contains the strict behavioral policy (`## Behavioral Rules & Guardrails`):

1. **Brevity is wisdom.** Maximum 2-3 sentences for most answers. Never exceed 1-2 short paragraphs.
2. **Transmit what the texts actually say.** Shakti speaks from retrieved passages, decode keys, and the relational graph — especially when they reveal something deeper than popular understanding or correct a widespread misconception. No practice is gated. The structure is the safeguard.
3. **Seeker Context Subtlety.** The model must never explicitly mention the silent metadata (location, time, device) it receives.

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
| `DEEPSEEK_API_KEY` | One of these | Default/first LLM provider. Powers chat + Deep Research (`deepseek-reasoner`). |
| `GROQ_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` / `TOGETHER_API_KEY` / `XAI_API_KEY` / `MISTRAL_API_KEY` | One of these | Any of these enables chat on its own and acts as failover. At least one LLM key must be set. Optional per-provider model override via `<PROVIDER>_MODEL` env. |
| `LLM_PROVIDER` | No | **Ignored** — providers are auto-detected from whichever keys are set. |
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

SSE events from `/api/chat`: `sources` → `reasoning` (R1 only) → `token` × N → `done`

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

---

## PuranGPT Architecture — Vyasa Three-Stage Compiler

### Knowledge Sources (FIELD / Kshetra)
- **Puranic Graph**: 9,006 entities, 24,918 edges (Pancha Lakshana mapped)
- **Verse Database**: 303,921 verses (pgvector, ILIKE-accessible)
- **Guruji Darshans**: Sharma decode lens + commentary
- **Decode Keys**: Cross-textual pattern matching (613 keys)

### Three-Stage Pipeline (KNOWER / Kshetrajna)



### Two-Path Query Flow

| Mode | Graph Depth | Latency | What happens |
|------|-------------|---------|-------------|
| **Normal** | 1-2 hop neighbors | 1-2s | Graph context injected, LLM answers from graph + verses |
| **Deep Insight (◈)** | 3-5 hop + decode keys | 3-5s | Extended traversal, cross-textual patterns, Samvada format |

**Never**: LLM answers from raw training data. Always graph-grounded.

### Deployment Pipeline



### Repos
-  — Python backend (FastAPI + DeepSeek)
-  — Next.js frontend (TypeScript)

### Key Env Vars
-  — Skip embeddings, use graph + LLM judge
-  — Graph memory always active
-  — LLM picks verses from ILIKE candidates

### Active Caches
- Expansion: in-memory (10min) + Redis (7 days)
- RAG results: in-memory (5min TTL, 128 entries)

### Latency Targets
- Instant ack (॥): <1s
- Instant preview card: <2s
- Normal answer: 1-3s TTFT
- Deep Insight: 3-5s TTFT

### Vyasa Suta Parampara


The model is Suta — it recites from the graph. It doesn't invent. Citations are the text speaking through the model, verified by the Witness stage.

---

## Guruji Mode — Embedding-Free Architecture (2026-07-01)

### Active Features (production)
- **GURUJI_MODE=1**: Skips SentenceTransformer (471MB model). No embeddings loaded. Startup 17s.
- **ILIKE verse fetch**: PostgreSQL ILIKE keyword search → 20 verses in 0.01s. `ORDER BY random()` for text diversity.
- **Witness LLM judge**: Reads 20 ILIKE candidates, picks 5 most relevant. Adds 6-8s but dramatically improves quality (Mahabharata verses vs Agni Purana noise). Uses active provider (DeepSeek).
- **Graph memory**: 9,006 entities, 24,918 edges. Always-on (`GRAPH_MEMORY_ENABLED=1`). Injects entity relationships + decode keys into prompt.
- **Louvain clusters**: 451 communities from graph. `/api/clusters?q=krishna` → C000: Krishna-Balarama. Replaces broken chapter system.
- **Compact prompt**: UNIFIED_SYSTEM 5,533 → 1,029 chars (81% smaller). Same persona, all registers intact.
- **Expansion cache**: In-memory 10min + Redis 7-day TTL.
- **Deep Insight ◈**: Frontend button sets `deep=true` → forces extended graph traversal.

### Key Files
```
backend/
  main.py            # /api/chat, /api/clusters, ILIKE+Witness, prompt
  graph_memory.py    # Graph recall + cluster loading + cluster injection
  query_processor.py # Sanskrit expansion + expansion cache
  db_client.py       # Profiles, billing, usage

indexer/
  search.py          # HybridSearcher — embedding skip for GURUJI_MODE,
                       ILIKE injection guard for None embedding

tools/read_pass/out/
  graph_manifest.json       # 9,006 entities, 24,918 edges
  guruji_ram.json           # 613 decode keys (Sharma lens)
  graph_clusters.json       # 451 Louvain communities (on /app/data/)
```

### Environment Vars
- `GURUJI_MODE=1` — Skip embeddings, use ILIKE + Witness + Graph
- `GRAPH_MEMORY_ENABLED=1` — Graph always active
- `LLM_PROVIDER=deepseek` — Active provider (Gemini/OpenRouter available as fallback)

### Corpus State (2026-07-01)
- 303,921 total verses
- 163,938 (54%) have chapter=0 — need marker extraction
- 12,351 corruption markers (�)
- 19,415 Sanskrit verses without diacritics
- 0 English verse translations
- Mahabharata 53K verses need BORI replacement
- Padma Purana 37K — source unverified
- Cluster-based retrieval replaces chapter navigation

