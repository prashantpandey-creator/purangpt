# campaign_brief_validate

One-line purpose: _gate a campaign brief (completeness, known channels, known
cadence/goal) BEFORE expensive LLM + media generation runs, returning a
normalized brief._

Known channels are sourced from `tools.content_policy_check.LIMITS` so the
channel vocabulary is canonical across the toolchain.

## Tool descriptor

```json
{
  "tool_name": "campaign_brief_validate",
  "input_schema": {
    "type": "object",
    "properties": { "brief": { "type": "object" } },
    "required": ["brief"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "valid":      { "type": "boolean" },
      "normalized": { "type": "object" }
    },
    "required": ["valid", "normalized"]
  }
}
```

A valid brief has: `name`, `goal` (one of app_installs/web_signups/awareness/
engagement/traffic), `audience`, `channels[]` (each a known channel, non-empty,
deduped), `cadence` (once/daily/weekly/twice_daily/hourly). `app_slug` defaults
to `purangpt`.

## Output envelope

```json
{ "success": true,
  "data": { "valid": true,
            "normalized": { "name":"Daily Gita Verse","app_slug":"purangpt",
                            "goal":"app_installs","audience":"...",
                            "channels":["x_twitter","telegram"],"cadence":"daily" } },
  "metadata": { "received_keys": ["audience","cadence","channels","goal","name"] },
  "errors": [] }
```

On failure: `success=false`, `data=null`, `errors` lists every problem found.

## Usage

```bash
# from purangpt/ repo root
venv/bin/python -m tools.campaign_brief_validate.check --file brief.json --json
venv/bin/python -m tools.campaign_brief_validate.check --brief '{"name":"...","goal":"app_installs","audience":"...","channels":["x_twitter"],"cadence":"daily"}'
```

```python
from tools.campaign_brief_validate.check import run
env = run(brief=brief_dict)
if env["success"]:
    brief = env["data"]["normalized"]   # safe to generate from
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `brief` not a dict | `success=false`, `errors=[{code:"bad_type"}]`, exit 2 |
| Missing required field | `errors` includes `{code:"missing_field"}`, exit 2 |
| Empty `channels[]` | `errors` includes `{code:"empty_channels"}`, exit 2 |
| Unknown channel | `errors` includes `{code:"unknown_channel"}`, exit 2 |
| Bad cadence / goal | `errors` includes `{code:"bad_cadence"}` / `{code:"bad_goal"}`, exit 2 |
| Valid | `success=true`, `data.valid=true`, exit 0 |

## Tests

`venv/bin/python -m tools.campaign_brief_validate.test_check` — asserts the valid
case, every rejection path, channel dedup/trim, and the app_slug default.
