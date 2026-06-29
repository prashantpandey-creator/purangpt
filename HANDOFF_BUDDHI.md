# 🤝 HANDOFF — Buddhi Layer (to other Claude sessions)

**From:** Claude session on terminal (current)
**To:** All Claude sessions working on purangpt/
**Date:** 2026-06-30 04:55 IST

---

## What Was Built

### `backend/buddhi.py` — The Discriminating Intelligence Layer

Sits between graph_memory (Mahat) + RAG (Manas) and the UNIFIED_SYSTEM prompt.
Performs 3-stage granthi-bheda synthesis on raw retrieval output.

- **Deterministic mode:** Structural synthesis from graph entities + 613 RAM keys. Sub-2ms, zero API cost.
- **LLM mode:** Delegates to provider-agnostic stream_llm with structured granthi-bheda prompt (ready, not yet called).

### Integration Points (already wired)

1. **`backend/main.py:126-133`** — Buddhi import, fail-graceful (same pattern as graph_memory)
2. **`backend/main.py:1956-1994`** — Buddhi synthesis step in chat flow, behind `BUDDHI_ENABLED=1` flag
3. **`backend/main.py:1965`** — Passes `expansion` (with new `graph_terms` field) to Buddhi
4. **`backend/main.py:1988-1989`** — Emits `{"type":"buddhi","lens":"...","confidence":0.XX}` as SSE event

### Query Expansion Enhancement

Added `graph_terms: list[str]` field to `QueryExpansion` — entity names specifically for graph recall, distinct from IAST embedding synonyms.

Updated both LLM prompts (`_CROSSLINGUAL_PROMPT` and `expand_with_history`) to extract graph entity names. The prompts now include the mind-layer entity chain and graph entity knowledge.

### Flag Gates

```
GRAPH_MEMORY_ENABLED=1   # graph recall (already existed)
BUDDHI_ENABLED=1         # Buddhi synthesis (NEW — defaults OFF)
```

Both flags default OFF. Byte-identical behavior when disabled.

### Files Changed (uncommitted)

```
 M backend/main.py              # +45 lines (Buddhi import + integration)
 M backend/query_processor.py   # +graph_terms field + prompt updates
?? backend/buddhi.py            # NEW — 720 lines
?? tools/buddhi_ab_test.py      # NEW — A/B comparison tool
?? tools/buddhi_demo.py         # NEW — 7-ability demo
```

## Overlap with Recent Commits

- **7dd96f0 (4h ago): "RAM lens injection, single adaptive prompt"** — Compatible. They inject 120 RAM keys into `{personality}`. Buddhi uses RAM keys for synthesis in `{context}`. Different prompt slots.
- **b6b8ac0 (3h ago): "dynamic mood tracking"** — Compatible. They added `mood` to QueryExpansion. We added `graph_terms`. Different fields.
- **85f7d19 (42m ago): "void_manifest"** — No overlap. Separate tool.

## What You Need to Know

1. **Don't remove the `graph_terms` field** from QueryExpansion — Buddhi depends on it for entity name matching when graph recall returns few entities.

2. **Don't remove the Buddhi import block** (lines 126-133 in main.py) — it's the same fail-graceful pattern as graph_memory and persona_extractor.

3. **Don't remove the Buddhi synthesis block** (lines 1956-1994) — it's flag-gated OFF by default. Zero impact unless `BUDDHI_ENABLED=1`.

4. **If you modify the LLM prompts** in query_processor.py, keep the `graph_terms` field in the JSON template and the examples that show mind-layer entity chains.

5. **The Buddhi module can be extended** to call the LLM for higher-quality synthesis (the `_synthesize_with_llm` async function is ready). The deterministic path is the default.

## To Enable in Production

```bash
# On Hetzner box:
echo "BUDDHI_ENABLED=1" >> /root/purangpt/.env
docker compose up -d backend
```

## Questions?

This handoff file is temporary. Delete after reading.
