# register_router

Decide whether a chat query gets the **structured Scholar layout** (summary →
key quoted passage → relevance) or the **flowing Guru voice**. Replaces leaving
that choice to the model — the single-prompt merge had silently gated the
structured layout behind a few keywords, so complex/analytical questions that
deserved it fell back to prose. Returns a ready-to-inject directive.

## Tool descriptor

```json
{
  "tool_name": "register_router",
  "input_schema": {
    "type": "object",
    "properties": { "query": { "type": "string" } },
    "required": []
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "register":  { "type": "string", "enum": ["scholar", "guru"] },
      "score":     { "type": "number" },
      "threshold": { "type": "number" },
      "signals":   { "type": "array", "items": { "type": "string" } },
      "directive": { "type": "string" }
    },
    "required": ["register", "score", "threshold", "signals", "directive"]
  }
}
```

`directive` is the empty string when `register == "guru"`, so a caller can
unconditionally append `data["directive"]` to its prompt directives list.

## Output envelope

```json
{ "success": true,
  "data": { "register": "scholar", "score": 4.0, "threshold": 3.0,
            "signals": ["analytic:compare"], "directive": "## REGISTER: ..." },
  "metadata": { "query_len": 61, "word_count": 9 }, "errors": [] }
```

## Scoring (THRESHOLD = 3.0)

| Signal | Weight | Notes |
|--------|--------|-------|
| Explicit intent (`cite`, `source`, `exact verse`, `according to the text`, …) | +3.0 | decisive alone |
| Analytic framing (`compare`, `contrast`, `differ`, `relationship between`, …) | +3.0 | comparison is essay-shaped; decisive alone |
| Multi-part (≥2 `?`) | +1.5 | compound ask wants structure |
| Question + ` and ` clause | +1.0 | |
| Long query (≥25 words / ≥16 words) | +1.5 / +1.0 | substantive |
| Corpus reference (`Purana`, `Gita`, `Upanishad`, …) | +0.5 | weak nudge |

## Usage

```bash
# from purangpt/ repo root
venv/bin/python -m tools.register_router.check --query "Cite the verse on dharma"
venv/bin/python -m tools.register_router.check --query "What is dharma?" --json
```

As a library (used by `backend/main.py` event_gen):

```python
from tools.register_router.check import run
env = run(request.query)
if env["success"] and env["data"]["directive"]:
    directives.append(env["data"]["directive"])
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `query` not a str | `success=false`, `errors=[{code:"bad_input"}]`, exit 2 |
| Scholar layout selected | `success=true`, exit 1 (a "finding") |
| Guru voice (default) | `success=true`, exit 0 |
| Empty / whitespace query | `success=true`, `register="guru"`, never crashes |

## Tests

`venv/bin/python -m tools.register_router.test_check` — pins the scholar/guru
boundary with real query corpora (explicit, complex-no-keyword, simple/personal),
asserts the envelope shape, the directive-only-for-scholar invariant, and score
monotonicity.
