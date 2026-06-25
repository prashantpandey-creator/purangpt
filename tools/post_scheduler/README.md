# post_scheduler

One-line purpose: _given a campaign cadence, each channel's last-posted time, and
`now`, decide which (campaign, channel) slots are due and assign a stable
dedup_key so replaying a tick never double-posts._

`now` is an input (the tool never reads the clock), so it is deterministic and
testable. The dedup_key buckets `now` to the cadence interval → identical ticks
produce identical keys → `ge_post_queue.UNIQUE(dedup_key)` blocks duplicates
(plan verify #8).

## Tool descriptor

```json
{
  "tool_name": "post_scheduler",
  "input_schema": {
    "type": "object",
    "properties": {
      "campaign":    { "type": "object", "description": "{campaign_id, cadence, channels[]}" },
      "last_posted": { "type": "object", "description": "{channel: iso8601}" },
      "now":         { "type": "string", "description": "iso8601" }
    },
    "required": ["campaign", "now"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "due": { "type": "array", "items": {
        "type": "object",
        "properties": {
          "campaign_id":   { "type": "string" },
          "channel":       { "type": "string" },
          "dedup_key":     { "type": "string" },
          "scheduled_for": { "type": "string" }
        } } },
      "now": { "type": "string" }
    },
    "required": ["due", "now"]
  }
}
```

Cadences: `hourly`, `twice_daily`, `daily`, `weekly`, `once`.

## Output envelope

```json
{ "success": true,
  "data": { "due": [{"campaign_id":"camp-1","channel":"x_twitter",
                     "dedup_key":"camp-1:x_twitter:daily:20992","scheduled_for":"2026-06-22T10:00:00+00:00"}],
            "now": "2026-06-22T10:00:00+00:00" },
  "metadata": { "now": "2026-06-22T10:00:00+00:00" }, "errors": [] }
```

## Usage

```bash
venv/bin/python -m tools.post_scheduler.check \
  --campaign '{"campaign_id":"camp-1","cadence":"daily","channels":["x_twitter","telegram"]}' \
  --last-posted '{}' --now "2026-06-22T10:00:00+00:00" --json
```

```python
from tools.post_scheduler.check import run
env = run(campaign=camp, last_posted=last, now=now_iso)
for slot in env["data"]["due"]:
    ...  # insert ge_post_queue row keyed by slot["dedup_key"]
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `campaign` not a dict | `success=false`, `{code:"bad_campaign"}`, exit 2 |
| Unknown cadence | `success=false`, `{code:"bad_cadence"}`, exit 2 |
| Bad `now` timestamp | `success=false`, `{code:"bad_now"}`, exit 2 |
| Bad `last_posted` timestamp | `success=false`, `{code:"bad_timestamp"}`, exit 2 |
| Slots due | `success=true`, `data.due` non-empty, exit 1 (finding = work to do) |
| Nothing due | `success=true`, `data.due=[]`, exit 0 |

## Tests

`venv/bin/python -m tools.post_scheduler.test_check` — asserts due/not-due across
cadences, per-channel independence, dedup_key stability+uniqueness, and the error
envelopes.
