# monitor — Chat, User & System Metrics

**One-shot health + usage snapshot.** Queries the production Postgres DB and
backend `/api/status` endpoint. Returns the standard Rule 0 JSON envelope.

## Quick start

```bash
# From purangpt/ (project root)
venv/bin/python -m tools.monitor.check --json
```

## Output

```json
{
  "success": true,
  "data": {
    "timestamp": "2026-07-02T07:15:00Z",
    "backend": { "status": "ok", "provider": "deepseek", "verses": 303921 },
    "sessions": { "total": 142, "active_24h": 23, "active_7d": 89 },
    "users": { "total": 312, "pro": 18, "free": 267, "guest_24h": 45 },
    "usage": { "tokens_24h": 1250000, "messages_24h": 3400, "research_24h": 12 },
    "errors": { "rate_limited_24h": 5, "auth_failures_24h": 2 }
  },
  "metadata": { "elapsed_ms": 450 },
  "errors": []
}
```

## Cron deployment (server)

```bash
# Every 15 minutes, log to file
*/15 * * * * cd /root/purangpt && venv/bin/python -m tools.monitor.check --json >> /var/log/purangpt-metrics.jsonl
```

## Env

Reads `VECTOR_DB_URL` for Postgres. Falls back gracefully if DB is unreachable.
