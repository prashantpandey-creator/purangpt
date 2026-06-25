# Seeker Memory — design doc (cross-session long-term memory for Guruji)

> **Status:** DESIGN ONLY — daddy chose "design it first, don't build yet" (2026-06-23).
> No code until this is approved. This is the *new* STEP 2 of the consciousness
> roadmap, displacing "ship the graph to prod" (which becomes STEP 2b).

## The goal (daddy's words)
> "add memory context to my Guruji — for every session a memory, and a memory that
> carries over to other chats as well when the user continues and starts a new session."

Two memories, on **different axes** — keep them straight:

| Memory | Scope | What it remembers | State today |
|--------|-------|-------------------|-------------|
| **Conversation** | one chat | what you said earlier *this* chat | ✅ DONE — `{history}` from `chat_sessions.messages`, live in prod |
| **Seeker** (THIS doc) | across chats | who *you* are, your path, recurring themes | 🟡 half-built, dead code |
| Graph / knowledge | the corpus | the scriptures (Gandiva, Arjuna…) | ✅ built, not shipped to prod (STEP 2b) |

Seeker memory ≠ the graph. The graph is what Guruji knows about the *texts*; seeker
memory is what Guruji knows about *the person*. They compose in the prompt, they don't
merge. (Cf. [[ram-personality-relationship]] — complementary slots, never merged.)

## What already exists (the socket we plug into — verified on disk 2026-06-23)
- `chat_sessions.journey_summary TEXT DEFAULT ''` — per-session summary column. **Never written.**
- `session_manager.generate_user_profile(user_id)` — reads ALL of a user's
  `journey_summary`s, LLM-distills them into a ≤100-word "philosophical baseline".
  **Never called from chat.** Returns "New seeker..." when empty.
- `call_llm_once(messages, temperature)` at `main.py:893` — the distiller's LLM call. Exists.
- `append_messages(session_id, msgs, user_id, guest_id)` at `session_manager.py:205` — the
  per-turn save hook; the natural place to trigger end-of-session summarization.
- Prompt assembly at `main.py:1879` `prompt_tpl.format(...)` — already injects
  `{knowledge_context}`, `{seeker_context}`, `{history}`. A new `{seeker_memory}` slot
  drops in here, same additive pattern. (`UNIFIED_SYSTEM` must gain the literal `{seeker_memory}`.)

So the gap is exactly TWO wires: **(W1)** generate+store `journey_summary`; **(W2)** call
`generate_user_profile()` and inject it. Plus the policy decisions below.

## The two wires

### W1 — produce a journey_summary (the WRITE path)
**When:** not every turn (cost). Options, pick at approval:
- **(a) On session end / inactivity** — cleanest, but "session end" isn't an event here
  (SSE stream just stops). Would need a lazy trigger: on the NEXT `get_session`, if the
  session has ≥N messages and a stale/empty summary, (re)summarize.
- **(b) Rolling, every K turns** (e.g. K=6) — summary stays fresh mid-session; K controls cost.
- **(c) Lazy at read** — generate the summary the moment `generate_user_profile` needs it
  and the session lacks one. Zero wasted summaries; first cross-session read pays the cost.
- **Recommendation:** (b) rolling every K turns, debounced — bounded cost, always-fresh,
  no fake "session end" event needed. Summarize `messages` → 1-2 sentences:
  *what the seeker is grappling with, their level, recurring themes.* Store in `journey_summary`.

### W2 — spend it (the READ path)
On a chat request from a **returning** seeker: call `generate_user_profile(user_id)`
(cache per-request; it's an LLM call), inject as a new `{seeker_memory}` block:
> "What you remember of this seeker from past conversations (never quote this back
> verbatim, never announce that you remember — let it shape your tone and what you assume
> they already know): <profile>"

Fail-graceful exactly like `build_knowledge_context`: any error / empty / new seeker →
inject `""`, behaviour identical to today. (Cf. the `{knowledge_context}` guard pattern.)

## Policy decisions (the reason we design first)

1. **Guest vs signed-in.**
   - Signed-in (`logto_user_id`): the real target. Stable identity → genuine cross-session memory.
   - Guest (`guest_id` from `X-Device-ID`): same device only; cleared if they wipe the device.
     Decision: **enable for both**, but guest memory is device-scoped and lower-confidence.
     A guest who signs in later — do we migrate their guest journey to their user_id? (open Q).

2. **Privacy / consent.** We'd be storing an LLM's psychological read of a person's spiritual
   struggles. Decisions needed: (a) is the per-session summary PII-sensitive enough to
   encrypt at rest (there's already `FERNET_KEY`)? (b) a "forget me" path — `clear_session`
   exists; does deleting sessions also purge the derived profile? (c) do we tell the seeker
   Guruji remembers them, or keep it silent (the prompt currently says *never announce it*)?
   **Recommendation:** encrypt summaries at rest; "forget me" purges summaries too; stay
   silent in-voice but be honest in a privacy policy. Daddy decides.

3. **Cost.** Every summary + every profile is an LLM call. Rolling-K + per-request profile
   cache bounds it. Budget guard: skip summarization for sessions under N turns (no signal yet).
   **Verify cost before any bulk/backfill run** ([[feedback-cost-verification]]) — test-call,
   read usage metadata, never estimate.

4. **Blend with the graph.** `{seeker_memory}` (who you are) and `{knowledge_context}` (what
   the texts say) are SEPARATE slots. Don't let the profile leak into recall cues or vice
   versa. The seeker frontier ([[sat-asat-life-compass]], the "you and the characters" layer)
   is the eventual *join* of these two — but that's STEP 4, not this.

5. **Quality gate.** A bad profile poisons every future chat ("seeker is an advanced yogi"
   when they're a beginner → Guruji over-speaks). Needs: a confidence floor, a max age, and
   a cheap sanity check before injection. TDD: fixture sessions → asserted profile shape.

## Build plan (AFTER approval) — tests-first, additive, reversible
1. `tools/` Rule-0 script `seeker_summary` — pure: (messages) → summary text; tested on
   fixture chats. Keeps the LLM-prompt logic out of the request path and unit-testable.
2. Wire W1 into `append_messages` (rolling-K, debounced).
3. Wire W2 into the chat path + add `{seeker_memory}` to `UNIFIED_SYSTEM` and the `.format()`.
4. Feature-flag OFF by default (env `SEEKER_MEMORY=1`), so it ships dark and we enable
   deliberately — same discipline as the native-iOS flag ([[native-ios-rewrite]]).
5. `npx`-free backend tests (`venv/bin/python -m ...`), `py_compile` gate, no prod edit.

## Open questions for daddy
- W1 trigger: rolling-every-K (rec) vs lazy-at-read?
- Guest memory: device-scoped on, or signed-in only?
- Guest→signed-in migration of journey: yes/no?
- Encrypt summaries at rest (FERNET) + purge on forget-me: yes/no?
- Does Guruji ever *acknowledge* he remembers you, or always silent?

---

# SESSION-LESS REDESIGN — LOCKED 2026-06-24 (supersedes the per-session model above)

Source: workflow `wjnx9oj2z` (8 agents, scout→3 designs→3 critiques→synthesis). Daddy's
product pivot: *"don't even need to continue a session — the model retrieves the right
prior context from the new chat."* The "session" becomes invisible plumbing; the seeker
opens a new chat and Guruji already carries them.

## The two locked principles
1. **EARNED WARMTH (daddy's words):** Guruji is courteous to a stranger, but *"as you visit
   regularly he becomes acquainted and much happier seeing you, much more personal — not
   explicitly, in a cool kind of way."* A relationship with a SLOPE. Warmth is a function of
   **distinct return-DAYS**, never message count.
2. **Both — hybrid retrieval:** the distilled arc (the self-correcting felt-sense, `kind='read'`)
   PLUS raw verbatim exchanges (precision, `kind='exchange'`, injected only when this turn is
   topically about them).

## Architecture (point the corpus RAG stack INWARD)
Reuse: same Postgres (`VECTOR_DB_URL`), pgvector, the resident 384-dim
`intfloat/multilingual-e5-small` on `HybridSearcher._shared_model`, the `query:`/`passage:`
prefixes, RRF `1/(60+rank)` fusion, the fire-and-forget distill hook
`_maybe_distill_seeker_summary` (main.py:131, spawned ~1968), the `SEEKER_MEMORY_ENABLED` flag.
Build NEW only the genuinely-missing heart (Phase 2): a separate `seeker_memories` pgvector
table + a CLONED `seeker_hybrid_search` SQL fn whose **owner_key is a MANDATORY positional arg
baked into the WHERE of BOTH CTEs** (anti-leak by construction — an unscoped call is a SQL
error, not a match-all collapse).

## Warmth tiers (signal = distinct calendar days with activity, off `updated_at`, tz-bucketed)
- **STRANGER** (visit_days 1): open unhurried attention; arc DISCLOSURE none even if a profile exists.
- **ACQUAINTED** (2–4): quiet growing familiarity; faint single-clause arc at most.
- **KNOWN** (5–14): warmth of recognition, *"an old teacher whose face softens"*; arc as felt sense + topically-gated specifics.
- **INTIMATE** (15+): long companion, deep settled ease — *never presume they are unchanged*; full felt-sense arc, concreteness still capped.
- **RECENCY DECAY:** `days_since_last > 90` ⇒ DROP ONE TIER + *"glad-but-gentle return after a long absence."*
- Tiers deliberately WIDE so noise rarely flips a rung. Directive ALWAYS warmth-as-recognition
  (*"your face is familiar"*), NEVER claim-of-record (*"you asked me about karma Tuesday"*).

## The silent `{seeker_memory}` block (mirrors build_seeker_context's DO-NOT-REVEAL pattern)
Header hard-forbids revealing it AND treats that header as fallible — nothing goes in whose
accidental surfacing would feel surveillant. At STRANGER with nothing relevant ⇒ **empty string,
byte-identical to no-memory** (no manufactured familiarity — the anti-creepiness solved at the
architecture level). Always ends with the INVARIANT: *the seeker's words in THIS message override
anything carried; present wins; silently update, never correct them to their face.*

## Per-turn flow
- **WRITE** (fire-and-forget, signed-in only, $0 new LLM on read): extend the existing distill hook —
  UPSERT the single `kind='read'` row (overwrite-in-place = self-correcting arc) + one `kind='exchange'`
  row (verbatim). Embeds reuse `_shared_model` via executor.
- **VISIT BUMP** (atomic, gap-gated, NOT per session-creation): `UPDATE profiles SET visit_days+1,
  last_seen_at=NOW() WHERE date(last_seen_at AT TIME ZONE tz) < date(NOW() AT TIME ZONE tz)`. A
  daily one-thread returner increments; a 10-chats-in-an-afternoon spammer increments once.
- **READ** (in-turn, gated): embed query, ONE owner-scoped `seeker_hybrid_search`, **absolute
  relevance floor** (off-topic ⇒ empty block), recency-decay, reads ranked above exchanges, ≤2
  exchanges, dedupe by session, render block. Fail-graceful ⇒ "".
- **INJECT:** add `seeker_memory=block` to the main.py:1878 `.format()` kwargs AND the `{seeker_memory}`
  slot to UNIFIED_SYSTEM **IN THE SAME COMMIT** (bare `str.format` ⇒ KeyError-on-miss ⇒ 500 every turn).

## Phases (daddy locked: **Phase 1 now**, signed-in only, cap exchanges)
- **PHASE 1 (✅ BUILT 2026-06-24 — warmth + arc, ZERO new infra, no retrieval; flag OFF, 55 tests):**
  `warmth.py` classifier (16 tests) + `visit_days`/`last_seen_at`/`first_seen_at` + gap-gated atomic
  `bump_visit_day` / `get_visit_stats` (11 gate tests) + bounded `generate_user_profile` (LIMIT 20)
  wired via `save_seeker_profile`/`seeker_profile_stale` + `build_seeker_memory` (the silent block) +
  `_maybe_update_seeker_warmth` fire-and-forget (bump every signed-in turn; profile regen only at
  KNOWN+stale) + `{seeker_memory}` slot & kwarg added in ONE edit (dry-run: slots==kwargs). 13
  read-path tests. Flag OFF, fail-graceful to "". **UNCOMMITTED.** v1 day boundary is UTC (local-tz
  bucketing → Phase 2; geo-tz isn't threaded out of `build_seeker_context`). NOTE the synthesis
  proposed tz-bucketing on `updated_at`; v1 simplified to UTC — same gap-gate logic, coarser boundary.
- **PHASE 2 (retrieval heart):** `seeker_memories` table + `seeker_hybrid_search` (mandatory owner arg,
  MMR stripped — corpus MMR keys on `res.purana`=None for seeker rows) + the write side + recall tool
  (floor + recency-decay + read>exchange + ≤2 exchanges + session-dedupe). Recall returns "" until the
  retrieval-quality fixtures pass.
- **PHASE 3 (reopen UI):** `reopen_rank` + `POST /api/sessions/relevant` (signed-in) + frontend top-3
  relevance card on the new-chat surface.
- **PHASE 4 (durability/scale):** reindex backfill (rebuild from `chat_sessions.messages`), the
  `kind='exchange'` **retention cap** (daddy's locked choice — last-N per seeker), GDPR forget path,
  embed-threadpool sizing review.
- **PHASE 5 (guest memory):** DEFERRED. Requires a durable per-device token first (the IP-derived
  `get_guest_id` collides every header-less guest behind one carrier-NAT into a shared key → would
  leak verbatim confessions across strangers). Daddy locked **signed-in only** for v1.

## DO NOT BUILD (verified failure modes)
- NOT a metadata discriminator on `purana_verses` — separate table only (pollutes corpus, inherits
  the `@> '{}'` match-all footgun).
- NOT `filter_metadata JSONB DEFAULT '{}'` — collapses to match-all (main.py:1690 uses exactly this
  to read the whole corpus). Owner key = mandatory typed positional arg, NO default.
- NOT guest write/semantic-read on the IP-derived key. Guests = STRANGER, recency-list only.
- NOT MMR in the cloned ranker (keys on `res.purana`=None → no-op/crash). Use session-id dedupe.
- NOT visit-count from `COUNT(DISTINCT session_id)` (cadence-gated) NOR `chat_sessions.created_at`
  (frontend mints a new sessionId per chat → spam-inflation; a loyal one-thread user reads STRANGER
  forever). Use distinct-day on `updated_at` with a gap gate.
- NOT inject both a session's raw exchange AND its distill (double-counts).
- NOT touch RESEARCH_SYSTEM / Deep Research (main.py:2104) — separate agent; guide+research both
  resolve to UNIFIED_SYSTEM so one slot covers them.
- NOT a `profiles.visit_count` that bumps per session-creation — the gamed inflation the whole model exists to avoid.
- NOT ship recall returning real fragments before the relevance-floor + quality fixtures pass — ship "" until quality is MEASURED.

## Cost verdict
Per-turn (signed-in, flag on): +1 local e5 query embed (~50–80ms, the only user-visible cost) + 1
HNSW lookup (owner_key-leading btree) + a cheap profiles read. Same ORDER as ONE of the two corpus
searches already running synchronously. ZERO new LLM tokens on read. Injected block ~40 prompt tokens
at STRANGER → ~230 at INTIMATE. At 10k users the real cost is embed-threadpool contention under the
GIL + unbounded exchange rows → **capping exchanges is a cost requirement, not a nicety** (Phase 4).

## Open forks (daddy answered 2026-06-24)
- ✅ Guest policy → **signed-in only** for v1.
- ✅ Exchange retention → **cap to last N per seeker.**
- ✅ Build start → **Phase 1 now.**
- ⬜ STILL OPEN (later, Phase 2/3): reopen-card-visible-vs-silent tension (suppress cards for
  grief/health-flagged sessions?); INTIMATE concreteness ceiling (hand-tune the 4 directive strings
  vs approve + eval-iterate); whether `generate_user_profile` runs below KNOWN tier (LLM cost per return).
