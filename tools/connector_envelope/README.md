# connector_envelope

One-line purpose: _map a raw channel-publish API response (X API v2, Telegram Bot
API — each a different shape) into the uniform {success,data,metadata,errors}
envelope with a normalized external_id/external_url._

So the worker writes `ge_post_log` from `data` and never parses raw provider JSON
in its own context. Tested against **real captured response shapes** in
`fixtures.py`.

## Tool descriptor

```json
{
  "tool_name": "connector_envelope",
  "input_schema": {
    "type": "object",
    "properties": {
      "channel": { "type": "string", "enum": ["x_twitter", "telegram"] },
      "raw":     { "type": "object", "description": "the provider's raw JSON response" },
      "handle":  { "type": "string", "description": "optional @handle for URL building" }
    },
    "required": ["channel", "raw"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "external_id":  { "type": "string" },
      "external_url": { "type": "string" },
      "channel":      { "type": "string" }
    },
    "required": ["external_id", "external_url", "channel"]
  }
}
```

## Output envelope

```json
{ "success": true,
  "data": { "external_id":"1572360002101411840",
            "external_url":"https://x.com/purangpt/status/1572360002101411840",
            "channel":"x_twitter" },
  "metadata": { "channel":"x_twitter","handle":"purangpt" }, "errors": [] }
```

On a provider error (duplicate, bad token, chat not found, malformed):
`success=false`, `data=null`, `errors=[{code:"x_error"|"telegram_error", message}]`.

## Usage

```bash
venv/bin/python -m tools.connector_envelope.check --channel telegram \
  --raw '{"ok":true,"result":{"message_id":1487,"chat":{"username":"purangpt"}}}' --json
```

```python
from tools.connector_envelope.check import run
env = run(channel="x_twitter", raw=api_response, handle="purangpt")
if env["success"]:
    log_post(env["data"]["external_id"], env["data"]["external_url"])
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Unsupported channel | `success=false`, `{code:"unknown_channel"}`, exit 2 |
| `raw` not a dict | `success=false`, `{code:"bad_raw"}`, exit 2 |
| X error / no data.id | `success=false`, `{code:"x_error"}`, exit 2 |
| Telegram `ok:false` / no message_id | `success=false`, `{code:"telegram_error"}`, exit 2 |
| Telegram private chat (no username) | `success=true`, `external_url=""` (no public link) |
| Normalized OK | `success=true`, exit 0 |

## Tests

`venv/bin/python -m tools.connector_envelope.test_check` — asserts normalization
of real X + Telegram success bodies and every documented error shape. Fixtures
live in `fixtures.py`.
