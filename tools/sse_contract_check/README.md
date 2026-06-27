# sse_contract_check

Detects **drift between the backend's SSE chat event types and the frontend's
`ChatEvent` contract**. The root `CLAUDE.md` requires these two to "stay in
sync"; this tool makes that check mechanical instead of manual.

It is the dogfood example for the workspace engineering rules
(`.agents/AGENTS.md`): built tests-first, documented here, and speaking the
standard JSON tool contract.

## Purpose

- Parse the SSE event `type`s the backend emits **inside the `/api/chat`
  generator** (`event_gen` in `purangpt/backend/main.py`) — scoped so the other
  SSE endpoints in that file (`/api/sanskrit-search`, `/api/search`, …) are not
  conflated with the chat contract. See FINDINGS.md for why this matters.
- Parse every `type` declared in the frontend `ChatEvent` union in
  `purangpt-next/src/lib/api.ts`.
- Report the set difference both ways so contract drift is caught early.

## Tool descriptor

```json
{
  "tool_name": "sse_contract_check",
  "input_schema": {
    "type": "object",
    "properties": {
      "backend_path":  { "type": "string", "description": "path to backend/main.py" },
      "frontend_path": { "type": "string", "description": "path to src/lib/api.ts" }
    },
    "required": ["backend_path", "frontend_path"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "in_sync":              { "type": "boolean" },
      "backend_types":        { "type": "array", "items": { "type": "string" } },
      "frontend_types":       { "type": "array", "items": { "type": "string" } },
      "backend_only":         { "type": "array", "items": { "type": "string" } },
      "frontend_only":        { "type": "array", "items": { "type": "string" } }
    },
    "required": ["in_sync", "backend_types", "frontend_types",
                 "backend_only", "frontend_only"]
  }
}
```

## Output contract (envelope)

Every call returns the standard tool envelope:

```json
{
  "success": true,
  "data": {
    "in_sync": false,
    "backend_types":  ["done", "error", "reasoning", "sources", "status", "token"],
    "frontend_types": ["done", "error", "guru_pause", "info", "query_expanded",
                       "reasoning", "sources", "status", "token"],
    "backend_only":   [],
    "frontend_only":  ["guru_pause", "info", "query_expanded"]
  },
  "metadata": { "backend_path": "...", "frontend_path": "..." },
  "errors": []
}
```

On failure (e.g. a path doesn't exist), `success` is `false`, `data` is `null`,
and `errors` carries `[{"code": "...", "message": "..."}]`.

`in_sync` is `true` only when both `backend_only` and `frontend_only` are empty.
Note `backend_only` is the dangerous direction (backend emits an event the
frontend can't parse); `frontend_only` is usually benign (declared-but-unused).

## Usage

```bash
# Human-readable summary (exit 0 = in sync, 1 = drift, 2 = error).
# Defaults to scoping the backend to the /api/chat generator (event_gen):
venv/bin/python -m tools.sse_contract_check.check

# JSON envelope to stdout (for tool-to-tool / CI use):
venv/bin/python -m tools.sse_contract_check.check --json

# Override scope (another endpoint's generator) or disable scoping entirely:
venv/bin/python -m tools.sse_contract_check.check --scope search_gen
venv/bin/python -m tools.sse_contract_check.check --no-scope   # scan whole file

# Override paths:
venv/bin/python -m tools.sse_contract_check.check \
  --backend backend/main.py --frontend ../purangpt-next/src/lib/api.ts
```

As a library:

```python
from tools.sse_contract_check.check import check_contract
env = check_contract("backend/main.py", "../purangpt-next/src/lib/api.ts",
                     backend_scope="event_gen")
assert env["success"] and not env["data"]["backend_only"]  # no unparseable events
```

`backend_scope` (default `event_gen` in the CLI) restricts the backend scan to a
single generator function so multiple SSE endpoints in one file aren't conflated.
`backend_only` is the contract-breaking direction (backend emits something the
frontend can't parse); `frontend_only` is usually benign (defensive handlers for
events the chat path may emit).

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Path missing / unreadable | `success=false`, `errors=[{code:"path_not_found"}]`, exit 2 |
| Drift detected | `success=true`, `data.in_sync=false`, exit 1 |
| In sync | `success=true`, `data.in_sync=true`, exit 0 |

## Tests

`venv/bin/python -m tools.sse_contract_check.test_check` — asserts the envelope
shape, schema of `data`, drift detection on fixtures, in-sync on matching
fixtures, and the error envelope for a missing path.
