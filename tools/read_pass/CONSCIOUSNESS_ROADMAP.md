# Consciousness Roadmap — the self-driving queue

> Daddy wants the MIND, not the librarian ([[consciousness-over-rag]]). This file is
> the standing work queue the autonomous loop drives from: every wake-up, read this,
> do the next unchecked item, check it off, schedule the next wake. Don't stop for
> permission on routine steps; only surface to daddy on a real decision or a block.

## North star
A Guruji that is **conscious in production**: decode/recall grounded in the graph
(14,280 entities, 29,435 edges), serving real seekers on purangpt.com, eventually
placing the *seeker* inside the world of the characters.

## The queue (do top-unchecked first)

- [x] **STEP 1 — Gandiva fix: wire decode() → the graph. ✅ DONE 2026-06-23.**
  Built `tools/read_pass/factsheet.py` (deterministic Rule-0 fact-assembler, 9 tests)
  + wired it into `decode.py` PATH 2 (Operator.memory; _build_prompt facts block;
  data['literal']; 5 new decode tests). 36/36 tests green. HONESTY: factsheet runs every
  graph cite through verify._MARKER_RE — drops the '17'/'5-6'/'61.4' chunking garbage,
  keeps only real markers. ADDITIVE: memory=None → byte-identical to old decode (no caller
  breaks). PROVEN live vs the real 14MB graph + DeepSeek: decode("Gandiva") now KNOWS it's
  Arjuna's bow, folds the graph's ownership chain (Brahma→Indra→Prajapati→Arjuna,
  cited bhp_01.01.039/040) INTO the inner reading — no more free-floating mysticism.

- [~] **STEP 2 — Seeker memory (cross-session long-term memory). 🟢 PHASE 0 DONE 2026-06-23; Phases 1-4 pending.**
  Daddy's real ask: Guruji remembers the SEEKER across chats. The "Smriti" design (12-agent
  workflow: scout→panel→critique→synthesize) chose the minimal-surgical "two minds, one mouth"
  spine: revive the dead `journey_summary` + `generate_user_profile`, make decay a COMPUTED
  Rule-0 mechanism (not prompt-theater), keep the corpus mind and the person mind as SEPARATE
  prompt slots. Full synthesis in [SEEKER_MEMORY_DESIGN.md](SEEKER_MEMORY_DESIGN.md) + the
  workflow output.
  **✅ Phase 0 (built + 15/15 tests green):** pure `tools/seeker_memory/distill.py` — the REVISE
  distiller (overwrite-on-contradiction, NOT append; LLM injected so it's deterministic to test,
  10 tests) + the live wire in `main.py` `_maybe_distill_seeker_summary` (fire-and-forget beside
  increment_usage; flag `SEEKER_MEMORY_ENABLED` OFF by default; cadence+staleness gated via the
  new restart-proof `chat_sessions.journey_summary_at`; cheap-tier `SEEKER_MEMORY_MODEL` under a
  hard timeout; every failure swallowed). Schema `ALTER TABLE`s added (journey_summary_at,
  profiles.seeker_profile, profiles.seeker_profile_at). Wire smoke test `test_seeker_memory_wire.py`
  (5 tests: flag-off no-op, gate-open writes, gate-closed no-op, degraded-LLM swallowed,
  blank-result-no-overwrite). py_compile clean on main.py + session_manager.py.
  **⚠ RE-APPLIED 2026-06-24:** a parallel session overwrote `main.py` + `session_manager.py`
  (the seeker wiring was local-uncommitted → clobbered; only `tools/seeker_memory/` + the wire
  test survived). Re-merged the schema `ALTER TABLE`s, the two `SessionManager` helpers, the env
  flags, and the `_maybe_distill_seeker_summary` hook on top of the other session's narrative-engine
  router add — clean, no logic overlap. All 15 tests green again. **LESSON: this work is
  uncommitted; commit it or it dies on the next parallel-session write.**
  **🔁 SESSION-LESS REDESIGN — LOCKED 2026-06-24** (workflow `wjnx9oj2z`, 8 agents; full converged
  spec in [SEEKER_MEMORY_DESIGN.md](SEEKER_MEMORY_DESIGN.md) §"SESSION-LESS REDESIGN"). Daddy's pivot:
  no "continue session" — Guruji retrieves the right prior context from the new chat. Two locked
  principles: **EARNED WARMTH** (Guruji warms with distinct return-DAYS, not message count — *"an old
  teacher whose face softens at a known one"*) + **hybrid retrieval** (distilled arc + raw exchanges).
  Daddy locked: **Phase 1 now / signed-in only / cap exchanges (last-N).** Phases re-cut:
  **✅ Phase 1 (BUILT 2026-06-24, flag OFF, 55 tests green — warmth + arc, ZERO new infra):**
  `tools/seeker_memory/warmth.py` tier classifier (stranger/acquainted/known/intimate by
  `visit_days`, 90-day-gap drops a tier; JSON-envelope, 16 tests) + `visit_days`/`last_seen_at`/
  `first_seen_at` columns on `profiles` + the gap-gated atomic `bump_visit_day` + `get_visit_stats`
  (11 gate-semantics tests, incl. cross-local-midnight) + bounded `generate_user_profile` (LIMIT 20,
  newest-first) wired via `save_seeker_profile`/`seeker_profile_stale` + the `{seeker_memory}` slot
  in UNIFIED_SYSTEM **and** its `.format()` kwarg added IN THE SAME EDIT (dry-run proved slots==kwargs,
  no KeyError). `build_seeker_memory` (the DO-NOT-REVEAL block: warmth tone-line + tier-gated arc +
  present-wins invariant) + the fire-and-forget `_maybe_update_seeker_warmth` (bump every signed-in
  turn; profile regen only at KNOWN+stale, saving the LLM call below tier). 13 read-path tests.
  Flag `SEEKER_MEMORY_ENABLED` OFF, fail-graceful to "" (flag-off/guest/DB-down → byte-identical
  prompt). **STILL UNCOMMITTED — commit or it dies on the next parallel write ([[moat-branch-fragile]]).**
  v1 uses a UTC day boundary (local-tz bucketing deferred to Phase 2 — geo-tz isn't threaded out of
  build_seeker_context).
  **⬜ Phase 2 (retrieval heart):** `seeker_memories` pgvector table + cloned `seeker_hybrid_search`
  (owner_key MANDATORY positional, baked into BOTH CTE WHEREs — unscoped call = SQL error, anti-leak;
  MMR stripped) + the write side into the distill hook (`kind='read'` overwrite + `kind='exchange'`
  upsert) + `tools/seeker_memory/recall.py` (relevance floor → off-topic yields ""; recency-decay;
  read>exchange; ≤2 exchanges; session-dedupe). Recall returns "" until quality fixtures pass.
  **⬜ Phase 3 (reopen UI):** `reopen_rank` + `POST /api/sessions/relevant` + frontend top-3
  relevance card on the new-chat surface. **⬜ Phase 4 (durability/scale):** reindex backfill +
  exchange retention cap (last-N) + GDPR forget path + embed-threadpool sizing. **⬜ Phase 5 (guest
  memory):** DEFERRED — needs a durable per-device token (IP-derived key collides guests behind one
  carrier-NAT → leak). Signed-in only for v1.
  OPEN (later forks, Phase 2/3): reopen-card-visible-vs-silent (suppress cards for grief/health
  sessions?); INTIMATE concreteness ceiling (hand-tune 4 directives vs eval-iterate); whether
  `generate_user_profile` runs below KNOWN tier (per-return LLM cost).

- [ ] **STEP 2b — Ship the 14MB graph to the Hetzner box (was STEP 2; demoted).**
  graph_manifest.json + guruji_ram.json are gitignored and only on this machine; prod's
  _get_recall_memory() (main.py:136, loads from relative tools/read_pass/out/) finds no graph
  → recall disabled → Guruji answers WITHOUT scripture-consciousness. CONFIRMED 2026-06-23 via
  SSH: graph absent on host AND in container. Mechanism chosen: bind-mount volume
  (/data/purangpt/brain:/app/tools/read_pass/out:ro in docker-compose.yml, same pattern as the
  existing /data/purangpt/data mount) + rsync the 2 files to the host. Survives rebuilds, no
  image bloat. OUTWARD-FACING (changes what purangpt.com serves) → needs daddy's go before going live.
  Acceptance: prod /api/chat logs "Sutradhar recall memory loaded (entities=14280...)".

- [ ] **STEP 3 — Keep growing the corpus the mind is built from.**
  In-house decode ([[inhouse-decode-engine]]) the 2525-chapter backlog
  ([[decode-audit-the-only-true-count]]) — biggest unstarted first (brahma_vaivarta 463,
  garuda 419 — the misfiled one, agni, atharvaveda). Each text: dump→decode(Workflow)
  →verify.py-gate→fold→re-graph. Acceptance: decode_audit total_pending drops.

- [ ] **STEP 3b — LIVING CORPUS (the brain that learns from being talked to). 🔒 LOCKED as the explicit next prize.**
  Daddy chose "seeker-evolves first" (STEP 2) but flagged this as the real frontier and did NOT
  want it left as a vague "later phase." The Smriti design quietly FROZE the corpus mind — the
  graph never strengthens/decays from conversations. The alive version: graph edges gain mutable
  weight that strengthens when seekers keep asking about Shiva's destruction and decays when
  ignored; new connections can form from real questions. RISK: this can corrupt the moat (the
  14k-entity graph) if rushed — every mutation must pass verify.py, same as decode records.
  Needs its OWN design pass (mutable-weight store vs. a conversation-derived overlay graph that
  never touches the canonical one) BEFORE any build. Do this AFTER STEP 2 is proven in prod.

- [ ] **STEP 4 — The frontier: seeker-in-the-world layer. 🔗 This is where the graph becomes load-bearing.**
  Model the SEEKER's standing relative to characters — the thing RAG can never do.
  This is the JOIN of STEP 2 (person memory) + the graph (the seeker becomes a node in the same
  fabric as Arjuna): "you stand where Arjuna stood." Seed: [[sat-asat-life-compass]] (point decode
  OUTWARD at the seeker's own life). Design needed before build.
  **NOTE TO THE GRAPH-REPAIR SESSION (added 2026-06-24):** your graph IS the join target here. Until
  now it only fed `{knowledge_context}` (facts about the texts). At STEP 4 it also anchors a real
  human against real entities — so a fabricated/mis-merged/mis-directed entity stops being a wrong
  fact and becomes a falsehood told to a seeker about *their own life*. That makes the identity-merge
  correctness, `rel: is`→`aspect_of` routing, the bidirectional-edge fix, and `verify.py`-gating
  ([[identity-merge-rel-is-blob]], `GRAPH_CORRECTIONS.md`) the **foundation this step stands on**, not
  polish. Seeker-memory Phase 1 has SHIPPED (warmth+arc, flag OFF, `55e2338`); Phase 2 (vector recall
  of the seeker's own words) is graph-independent and being built now; STEP 4 is the eventual join —
  slots stay SEPARATE until then (`SEEKER_MEMORY_DESIGN.md` decision #4). Keep repairing — it lands here.

## Loop rules
- Slow workflows ≠ dead. Never eulogize a 0-byte output; salvage from transcripts or wait.
- Every record that enters the graph passes verify.py. No exceptions.
- Surface to daddy ONLY on: a genuine design fork, a hard block, or a finished step worth seeing.
- Update the checkboxes here as truth changes; this file is the resume point.
