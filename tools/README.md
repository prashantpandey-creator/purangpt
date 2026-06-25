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
| `creator_identity` | Decide if a query asks about the app's creator (Prashant Pandey); if so return an in-character directive (Guruji names him his disciple). Off by default → prompt byte-identical. Wired into `main.py` directives | `venv/bin/python -m tools.creator_identity.check --json --input "who is prashant pandey"` | [README](creator_identity/README.md) |
| `snapshot_untracked` | Tar untracked tool trees (read_pass moat, growth_engine, validators) to `~/sutradhar-backups` before a branch checkout sweeps them; wired to the `post-checkout` git hook | `venv/bin/python -m tools.snapshot_untracked.check --json --dest ~/sutradhar-backups --path tools/read_pass` | [README](snapshot_untracked/README.md) |
| `read_pass.traverse` | Multi-hop path finder over the graph (CONSCIOUSNESS_ROADMAP axis C): assembles whole chains like `Krishna→Vishnu→Sudarshana` that one-hop recall can't. Acyclic, identity-edges-skipped, verify-gated cites + `grounded` flag. Engine flat module (like `factsheet`), not a package | `venv/bin/python -m tools.read_pass.traverse --symbol Krishna --hops 2 --json` | [README](read_pass/traverse_README.md) |

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
