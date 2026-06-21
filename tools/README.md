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
