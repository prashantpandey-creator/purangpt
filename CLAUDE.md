# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Work-in-Progress — READ FIRST

**[`../PROJECT_LEDGER.md`](../PROJECT_LEDGER.md)** is the shared WIP state for all
agents across both repos. Read its Current State before starting; update it after
finishing. It tracks what's done, what's blocked, and what's active so sessions
don't duplicate or conflict.

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
| LLM | **Generic key-driven providers** — `get_providers()` in `backend/main.py` reads a list of OpenAI-compatible endpoints (deepseek, groq, openai, openrouter, together, xai, mistral) and uses whichever have a real key, in priority order, with automatic failover. DeepSeek is just the first default. Deep Research uses `deepseek-reasoner` via its own client. |
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

## Active Workstreams (read before touching prompts or intelligence code)

Two parallel efforts are converging on Guruji's behaviour. If you're editing one,
know the other exists so you don't break it.

### 1. read_pass — Proactive Comprehension (offline intelligence layer)

**Status (2026-06-23 post-audit):** Full 12-module engine built (97 tests). **8 REAL
texts decoded** (Bhagavata, Mahabharata, Ramayana, Brahma, Padma, Skanda, Gheranda,
Bhagavata-proof). **16 fabricated texts quarantined** to `out/quarantine/` — they were
decoded against Bhagavata chunk windows, not their own text (identical `bhagavata-1-*`
chunk IDs, `bhp_` markers, 419-420 record counts). The pipeline works; the bug was
upstream chunk routing. `graph_manifest.json` needs rebuild from only the 8 real texts
(current manifest is 70% fabricated data).

**Audit tool:** `venv/bin/python -m tools.graph_health.check --json` (12 tests).

**Key components:** `group.py` (windowing) → `comprehend.py` (LLM decode with Sharma
lens, 390 chunks in `sharma_texts.jsonl`) → `verify.py` (deterministic citation
grounding) → `predicate.py` (verb normalization) → `graph.py` (union-find entity
merge, manifest mode) → `identity.py` (typed same_as/avatar_of/aspect_of edges, 2006
discovered, never merged into manifest) → `resolve.py` → `synthesize.py` →
`insights.py` → `timeline.py` → `guruji_ram.py` (613 keys) → `recall.py` + `decode.py`
(live query-time intelligence).

**Lens integration:**
- Awakener EN (145 chunks) → IN `sharma_texts.jsonl` (comprehend lens)
- Guruji RAM (613 keys) → IN `recall.py`, `factsheet.py`, `decode.py` (query-time)
- Awakener NOT in RAM corpus dir (`data/raw_texts/sharma/`)
- `sharma_biography.json` (780 events, 285 encounters) → orphaned, not wired

**What it does NOT touch:** `backend/main.py`, any live prompts, the production
system. It's offline, writes flat JSONL to `tools/read_pass/out/` (gitignored).

**Integration:** `{knowledge_context}` is already wired at `build_knowledge_context()`
(main.py:158) — `recall.py` + `factsheet.py` + `decode.py` inject graph data at
query time, fail-graceful (returns `""` on any error). **However**, the graph files
are gitignored and local-only — NOT on the prod server yet (STEP 2b of roadmap). So
recall is dark in production; every seeker currently gets the amnesiac Guru.

**Comprehension providers:** `comprehend.py` supports DeepSeek (default), Gemini
(historical fallback — hit free-tier 429 on the original Bhagavata run), and
**in-house Claude** (`INHOUSE_DECODE=1`, Workflow fan-out, disk-cached). **Gemini is
NOT the primary provider anymore.** New decode runs should default to DeepSeek or
in-house.

Full design: [`tools/read_pass/ARCHITECTURE.md`](tools/read_pass/ARCHITECTURE.md).

### 2. Personality Restructuring (live prompts — frontend work)

**Status:** In progress (separate sessions).

**What it touches:** `UNIFIED_SYSTEM`, `GURUJI_PERSONALITY`, and voice/policy
constants in `backend/main.py`. Potentially also frontend chat UI/UX in
`purangpt-next/`.

**What it does NOT touch:** `tools/read_pass/` or the offline comprehension pipeline.

### 3. Seeker Memory ("Smriti" — Guruji remembers the person)

**Status (2026-06-23):** Phase 0 BUILT (flag OFF, 15/15 tests). Design from a
12-agent Smriti workflow.

**What it is:** Cross-session memory of the *seeker*, not the *texts*. Three memory
axes (keep straight — confusing them is the trap):
- **Conversation memory** (`{history}`) — one chat remembers itself. ✅ DONE, live.
- **Seeker memory** (`{seeker_memory}`, NEW) — Guruji remembers *you* across chats.
  🟡 Phase 0 built, Phases 1-4 pending.
- **Graph/knowledge** (`{knowledge_context}`) — Guruji remembers the *texts*. ✅
  Built, not shipped to prod.

**What's built (Phase 0):**
- `tools/seeker_memory/distill.py` — pure REVISE distiller (overwrite-on-contradiction,
  NOT append; LLM injected as `caller`). 10 tests.
- `_maybe_distill_seeker_summary` in `main.py` (~line 910) — fire-and-forget beside
  `increment_usage`. Flag `SEEKER_MEMORY_ENABLED` **OFF** by default; cadence+staleness
  gated (restart-proof via `journey_summary_at`); cheap-tier `SEEKER_MEMORY_MODEL`;
  hard timeout; every failure swallowed.
- Schema: `ALTER TABLE` adds `journey_summary_at`, `profiles.seeker_profile`,
  `profiles.seeker_profile_at` (idempotent in `_init_db`).

**What touches:** `backend/main.py` (the fire-and-forget hook + helper),
`backend/session_manager.py` (schema + save/gate helpers), `tools/seeker_memory/`.
When flag is OFF, behaviour is **byte-identical** to before — the hook is a no-op.

**Roadmap:** `tools/read_pass/CONSCIOUSNESS_ROADMAP.md` (STEP 2, phases 0-4).

### Coordination rules

- **Don't cross the streams.** If you're doing personality/prompt work, don't edit
  `tools/read_pass/` or `tools/seeker_memory/`. If you're doing read-pass work, don't
  edit the live prompts in `main.py`. Seeker memory touches `main.py` only through
  the flag-gated fire-and-forget hook.
- **The Practice & Initiation Limit** is lifted for the offline read-pass only
  (knowledge-layer comprehends everything). The live prompt still has it. If
  personality restructuring removes it from the live prompt, that's a deliberate
  decision — but know that the read-pass was designed assuming the live mouth has
  *some* guardrail.
- **The `PROMPTS` dict, `build_seeker_context()`, and the `{...}` template variable
  pattern in `UNIFIED_SYSTEM`** are the shared surface. All workstreams need these
  to survive intact. Add variables; don't rename or restructure the pattern without
  checking all sides. The seeker memory slot `{seeker_memory}` is not yet in the
  template — that's Phase 2.
