# <tool_name>

COPY-ME TEMPLATE. Replace `<tool_name>` and every section below. This README
covers the two things the JSON descriptor can't: the **failure-mode table** and a
**runnable example** (Rule 3b). Purpose + I/O live in the descriptor — don't
re-prose them.

One-line purpose: _what decision tree / parse-filter-reshape this replaces_.

## Tool descriptor

```json
{
  "tool_name": "<tool_name>",
  "input_schema": {
    "type": "object",
    "properties": { "example_input": { "type": "string" } },
    "required": []
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "echo":   { "type": "string" },
      "length": { "type": "integer" }
    },
    "required": ["echo", "length"]
  }
}
```

## Output envelope

```json
{ "success": true, "data": { "echo": "hi", "length": 2 }, "metadata": {}, "errors": [] }
```

On failure: `success=false`, `data=null`, `errors=[{"code":"...","message":"..."}]`.

## Usage

```bash
# from purangpt/ repo root
venv/bin/python -m tools.<name>.check --input hello          # human summary
venv/bin/python -m tools.<name>.check --input hello --json   # JSON envelope
```

As a library (tool-to-tool):

```python
from tools.<name>.check import run
env = run("hello")
assert env["success"]
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Bad/empty input (`boom` in template) | `success=false`, `errors=[{code:"bad_input"}]`, exit 2 |
| Finding detected (per-tool semantics) | `success=true`, exit 1 |
| Normal | `success=true`, exit 0 |

## Tests

`venv/bin/python -m tools.<name>.test_<name>` — asserts envelope shape, the
`data` schema, and the error envelope. For filter tools, add real-output fixtures.
