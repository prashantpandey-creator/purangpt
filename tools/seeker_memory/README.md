# seeker_memory — Guruji's memory of the PERSON (axis 2)

The seeker-memory layer: what Guruji knows about *you* across sessions — distinct
from the corpus mind (`{knowledge_context}`, what he knows about the *texts*) and
from conversation memory (`{history}`, this chat). They compose as separate prompt
slots; they never merge. Design: `tools/read_pass/SEEKER_MEMORY_DESIGN.md` (the
"Smriti" synthesis).

## Tool descriptor

```json
{
  "tool_name": "seeker_memory.distill",
  "input_schema": {
    "type": "object",
    "properties": {
      "prior_summary": { "type": "string", "description": "the session's current running read (may be empty)" },
      "exchange":      { "description": "latest exchange: a list of {role,content} msgs, or a plain string" },
      "max_words":     { "type": "integer", "default": 80 }
    },
    "required": ["prior_summary", "exchange"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "summary":       { "type": "string" },
      "revised":       { "type": "boolean" },
      "prior_summary": { "type": "string" }
    },
    "required": ["summary", "revised", "prior_summary"]
  }
}
```

The LLM is injected as a `caller(messages, temperature=...)` callable, so the module
is pure plumbing + prompt construction — deterministic and network-free in tests.

## What it does

The **WRITE path** of seeker memory: revise one session's running `journey_summary`.
It does NOT append — the prompt explicitly instructs the model to keep what holds,
OVERWRITE what the exchange contradicts, DROP what is stale. That overwrite-on-
contradiction is what makes the memory *evolve* instead of *accumulate*. `revised` is
True iff there was a prior to revise (first-ever distill is a fresh read, `revised=False`).

## Output envelope

```json
{ "success": true,
  "data": { "summary": "Daily meditator now; restlessness fading.", "revised": true, "prior_summary": "Beginner, does not meditate." },
  "metadata": { "had_prior": true, "exchange_chars": 142, "max_words": 80 },
  "errors": [] }
```

## Live wire (in `backend/main.py`, NOT here)

`_maybe_distill_seeker_summary(...)` is spawned fire-and-forget right after the turn
is saved (beside `increment_usage`). It is:
- **flag-gated OFF**: `SEEKER_MEMORY_ENABLED=1` to enable (default off → perfect no-op);
- **cadence + staleness gated**: re-distills every `SEEKER_MEMORY_TURN_CADENCE` turns
  (default 3) OR when `chat_sessions.journey_summary_at` is >30 min old (restart-proof);
- **cheap-tier + bounded**: routes to `SEEKER_MEMORY_MODEL` (default `auto`) under a
  hard `SEEKER_MEMORY_TIMEOUT_S` (default 20s) timeout, so it can't starve the
  user-facing provider or pin a connection;
- **swallowed**: any failure leaves the prior summary intact and never touches the turn.

Schema (idempotent `ALTER TABLE` in `session_manager._init_db`):
`chat_sessions.journey_summary_at`, `profiles.seeker_profile`, `profiles.seeker_profile_at`.
Writer/gate helpers: `session_manager.save_journey_summary` / `journey_summary_stale`.

---

# warmth — earned-warmth tier classifier (READ path, Phase 1)

The emotional heart of session-less seeker memory. Daddy's design: Guruji is courteous
to a stranger, but as the seeker RETURNS across distinct days his warmth grows — "an old
teacher whose face softens at a known one." Pure decision tree: `(visit_days,
days_since_last, is_guest)` → familiarity tier + the hand-authored tone-line that colours
Guruji's voice. No LLM, no DB, no clock — so every branch is deterministically testable.
Full design: `tools/read_pass/SEEKER_MEMORY_DESIGN.md` §"SESSION-LESS REDESIGN".

```json
{
  "tool_name": "seeker_memory.warmth",
  "input_schema": {
    "type": "object",
    "properties": {
      "visit_days":      { "type": "integer", "minimum": 1, "description": "distinct calendar days the seeker has been active" },
      "days_since_last": { "type": ["integer","null"], "minimum": 0, "description": "days since last visit; > 90 drops one tier" },
      "is_guest":        { "type": "boolean", "default": false, "description": "guests have no durable identity → pinned to stranger" }
    },
    "required": ["visit_days"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "tier":         { "enum": ["stranger","acquainted","known","intimate"] },
      "directive":    { "type": "string", "description": "the warmth tone-line for the {seeker_memory} block" },
      "disclose_arc": { "type": "boolean", "description": "may the distilled seeker-profile arc appear at this tier?" },
      "decayed":      { "type": "boolean", "description": "did a >90-day absence drop the tier?" }
    },
    "required": ["tier","directive","disclose_arc","decayed"]
  }
}
```

**Tiers** (by `visit_days`): stranger=1, acquainted=2–4, known=5–14, intimate=15+. KNOWN is
the first tier that discloses the arc as a *felt sense* (never a transcript). A `>90`-day
absence drops one tier (floored at stranger) and swaps in a glad-but-gentle return directive.
The directive is ALWAYS warmth-as-recognition, NEVER a claim-of-record — surveillance is the
failure mode the whole model exists to avoid. Guests are pinned to stranger (no durable identity).

### warmth failure modes

| `errors[].code` | Condition | Caller effect |
|-----------------|-----------|---------------|
| `bad_visit_days` | `visit_days` not an int ≥ 1 | fall back to empty block (no warmth line) |
| `bad_days_since_last` | `days_since_last` negative / non-int | same — fail-graceful to "" |
| (none) | normal | `success=true`, use `data.directive` in the block |

## Not yet built (Phase 2+)
- **Phase 2** — `seeker_memories` pgvector table + cloned `seeker_hybrid_search` (mandatory
  owner arg) + the write side + `recall.py` (relevance floor + recency-decay). The
  `{seeker_memory}` read slot ships in Phase 1 carrying ONLY the warmth line + distilled arc.
- **Phase 3** — reopen UI: `reopen_rank` + `POST /api/sessions/relevant` + frontend top-3 card.
- **Phase 4** — reindex backfill, `kind='exchange'` retention cap (last-N), GDPR forget path.
- **Phase 5** — guest memory (DEFERRED; needs a durable per-device token; signed-in only for v1).

## Usage

```bash
# from purangpt/ repo root
venv/bin/python -m tools.seeker_memory.test_distill   # 10 tests, pure (network-free)
venv/bin/python -m tools.seeker_memory.test_warmth    # 16 tests, pure decision tree
venv/bin/python test_seeker_memory_wire.py            # 5 tests, the live wire
venv/bin/python -m tools.seeker_memory.warmth --visit-days 9 --json   # smoke the classifier
```

As a library (tool-to-tool):

```python
from tools.seeker_memory.distill import distill_session_summary
env = distill_session_summary(prior, exchange, caller=my_llm_caller)
```

## Failure modes

| `errors[].code` | Condition | Live-wire effect |
|-----------------|-----------|------------------|
| `empty_exchange` | nothing new to distill | skip; no LLM call, no write |
| `caller_failed`  | LLM provider raised / timed out | skip; prior summary intact |
| `empty_result`   | LLM returned blank | skip; a blank must never overwrite a good prior |
| (none)           | normal | `success=true`, write the revised summary |
