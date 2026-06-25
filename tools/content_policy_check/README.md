# content_policy_check

One-line purpose: _decide whether a post is allowed on a given channel (length,
hashtag count, banned promo terms) before it ever reaches the live connector API._

Replaces the per-channel "is this post within limits?" decision tree so the
worker consumes only `data.ok` / `data.violations` and never posts something the
platform would reject or spam-flag.

## Tool descriptor

```json
{
  "tool_name": "content_policy_check",
  "input_schema": {
    "type": "object",
    "properties": {
      "channel": { "type": "string" },
      "text":    { "type": "string" }
    },
    "required": ["channel", "text"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "ok":            { "type": "boolean" },
      "channel":       { "type": "string" },
      "violations":    { "type": "array", "items": { "type": "object" } },
      "length":        { "type": "integer" },
      "hashtag_count": { "type": "integer" }
    },
    "required": ["ok", "channel", "violations", "length", "hashtag_count"]
  }
}
```

## Output envelope

```json
{ "success": true,
  "data": { "ok": false, "channel": "x_twitter",
            "violations": [{"code":"too_long","message":"300 chars exceeds x_twitter limit of 280"}],
            "length": 300, "hashtag_count": 0 },
  "metadata": { "channel": "x_twitter", "raw_length": 300 }, "errors": [] }
```

On a tool-level failure (unknown channel / empty text): `success=false`,
`data=null`, `errors=[{code,message}]`.

## Usage

```bash
# from purangpt/ repo root
venv/bin/python -m tools.content_policy_check.check --channel x_twitter --text "Act, renounce the fruit. #Gita"
venv/bin/python -m tools.content_policy_check.check --channel x_twitter --text "..." --json
```

```python
from tools.content_policy_check.check import run
env = run(channel="x_twitter", text="...")
if env["success"] and env["data"]["ok"]:
    ...  # safe to hand to the connector
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Unknown channel | `success=false`, `errors=[{code:"unknown_channel"}]`, exit 2 |
| Empty/whitespace text | `success=false`, `errors=[{code:"empty_text"}]`, exit 2 |
| Post violates a limit | `success=true`, `data.ok=false`, `violations[]` populated, exit 1 |
| Compliant post | `success=true`, `data.ok=true`, exit 0 |

Violation codes: `too_long`, `too_many_hashtags`, `banned_term`.

## Tests

`venv/bin/python -m tools.content_policy_check.test_check` — asserts the envelope,
the per-channel limits (X 280 vs Telegram 4096), the 300-char-X rejection
(plan verify #5), hashtag caps, banned terms, and the error envelopes.
