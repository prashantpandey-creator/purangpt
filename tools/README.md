# tools/ — deterministic scripts the agent calls instead of sub-agents

This is the **tool registry**. Per Rule 0 (Orchestrator-First, in
`.agents/AGENTS.md`), before spawning a sub-agent or reading raw tool output into
context, check this table — a deterministic script here is cheaper and
repeatable. **Extend an existing tool before creating a new one.**

Each tool is an importable package (`tools.<name>`) exposing a `check.py` with:
- a CLI: human summary by default, `--json` for the `{success,data,metadata,errors}`
  envelope, exit codes `0` (ok) / `1` (finding) / `2` (error);
- an importable function returning that envelope (for tool-to-tool chaining);
- `test_<...>.py` (tests-first), and a co-located `README.md`.

To create a new tool: `cp -r tools/_template tools/<name>`, then fill in the
three functions and the README, tests-first (Rule 0, preconditions A & B in
`.agents/AGENTS.md`).

## Registry

| tool_name | purpose | invoke (JSON) | docs |
|-----------|---------|---------------|------|
| `sse_contract_check` | Detect drift between the backend `/api/chat` SSE event types (scoped to `event_gen`) and the frontend `ChatEvent` union | `venv/bin/python -m tools.sse_contract_check.check --json` | [README](sse_contract_check/README.md) |
| `doc_path_audit` | Pre-flight orientation pass: surface stale file-path claims in `.md` docs before any session action | `venv/bin/python -m tools.doc_path_audit.check --json` | [README](doc_path_audit/README.md) |
| `retrieval_qc` | Measure search efficacy & source quality (distribution, alphabetic bias, coverage, metadata QC, Guruji-vs-scripture separation) | `venv/bin/python -m tools.retrieval_qc.check --payload <run.json> --json` | [README](retrieval_qc/README.md) |
| `onnx_export` | Export multilingual-e5-small to ONNX INT8 + embed all 329K corpus chunks into corpus.db | `venv/bin/python -m tools.onnx_export.check --mode model --json` | [README](onnx_export/README.md) |
| `sqlite_export` | Export all_chunks.jsonl → SQLite DB with FTS5 for offline app use (329K rows, 246MB raw / 70MB gzip) | `venv/bin/python -m tools.sqlite_export.check --json` | [README](sqlite_export/README.md) |
| `register_router` | Decide Scholar (structured: summary→passage→relevance) vs Guru (flowing) layout per query — deterministic, replaces model-whim register choice | `venv/bin/python -m tools.register_router.check --query "..." --json` | [README](register_router/README.md) |
| `graph_clean_audit` | Quantify residual relationship-quality noise across all graph edges (kin/guru direction contradictions, genuine non-being relations, mis-typed-being re-type candidates) — verifies the character.py cleaning at scale | `venv/bin/python -m tools.graph_clean_audit.check --json` | [README](graph_clean_audit/README.md) |
| `source_reality_check` | Is a corpus file REAL Sanskrit or web/HTML garbage? Scans the WHOLE file (not a head sample, so the chunk_marker_audit scope-trap can't bite) → counts IAST diacritics, Devanagari, verse markers (prefixed `MU_1,26.13` OR bare `1.1.1`), HTML boilerplate → real_sanskrit / html_garbage / suspect / empty. Built for the yoga_vasistha incident (a saved archive.org page had been ingested as the source). Answers a DIFFERENT axis than `chunk_marker_audit` (reality, not decode-readiness). 11/11 tests | `venv/bin/python -m tools.source_reality_check.check data/chunks/yoga_vasistha.jsonl --json` | [README](source_reality_check/README.md) |
| `embed_eval` | Measure embedding model retrieval quality against a 30-query gold set spanning 20+ Sanskrit texts — hit@1/3/5/10, MRR, mean_rank, bootstrap 95% CI on hit@5. Single-model eval via `check.py`; multi-model comparison sweep via `ladder.py`. Data field: `{model, config, dim, n_queries, metrics{hit@1,hit@3,hit@5,hit@10,mrr,mean_rank_found,found,hit@5_ci95}, cost, per_query}`. 8 unit tests. | `venv/bin/python -m tools.embed_eval.check "intfloat/multilingual-e5-large" --corpus corpus.json --json` | [README](embed_eval/README.md) |
| `persona_extractor` | Build a talkable PERSONA from the graph layers (identity/lineage/kin/deeds + RAM decode) — the graph-grounded replacement for the hand-written `GURUJI_PERSONALITY`, and the engine behind the "talk to the gods" tab. Curated registry pins each persona to an exact entity id (defeats the `recall("Shailendra Sharma")`→mountain mis-cast); POV-normalizes kin direction; drops placeholder decodes. Guruji = entity #1, N gods in one machine. 12 real-graph tests. | `venv/bin/python -m tools.persona_extractor.check --persona shiva --json` | [README](persona_extractor/README.md) |
| `void_manifest` | **Puranic LLM PoC:** Intent → Architectural Graph (Conscious Void) → Manifest code files. LLM conceives the complete app as structured JSON; Witness validates deterministically; Manifest Engine compiles to Next.js+Prisma+TypeScript code — zero hallucination in rendering. Think in structured space, manifest in an instant. 22/22 tests. | `venv/bin/python -m tools.void_manifest.check --json "A todo app with users and tasks"` | [README](void_manifest/README.md) |

<!-- Add one row per new tool. Keep tool_name = the package dir name. -->

## Conventions

- **Run from the backend repo root** (`purangpt/`) so package imports resolve:
  `venv/bin/python -m tools.<name>.check`.
- **Tests:** `venv/bin/python -m tools.<name>.test_<name>` must exit `0`.
- **Consume only `data`.** Call with `--json` and read the envelope's `data`
  field; never pipe raw tool output into context (Rule 0).
- The end-state is an orchestrator + `tools/orchestrator/registry.yaml` carrying
  each tool's `{tool_name, input_schema, output_schema}`; until it exists this
  table is the registry.
