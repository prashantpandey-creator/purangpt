"""monitor — Chat, User & System Metrics Snapshot

Rule 0 tool (deterministic JSON contract). Queries the production Postgres DB
for session/user/usage counts and polls the backend /api/status endpoint.
Outputs the standard {success, data, metadata, errors} envelope.

Usage:
  venv/bin/python -m tools.monitor.check --json   # machine-readable
  venv/bin/python -m tools.monitor.check           # human-readable summary
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── DB connection (reuses the project's VECTOR_DB_URL) ────────────────────
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

# ── HTTP for /api/status ─────────────────────────────────────────────────
try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


DB_URL = os.getenv("VECTOR_DB_URL", "")
BACKEND_URL = os.getenv("BACKEND_URL", "https://purangpt.com")


# ── Helpers ───────────────────────────────────────────────────────────────
def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_ago(h: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


def _run_query(sql: str, params: tuple = ()) -> Optional[List[Dict[str, Any]]]:
    """Run a read-only query against the production DB. Returns None on failure."""
    if not HAS_PSYCOPG or not DB_URL:
        return None
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=5)
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return None


def _fetch_status() -> Optional[Dict[str, Any]]:
    """Fetch backend /api/status. Returns None on failure."""
    if not HAS_URLLIB:
        return None
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/api/status")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


# ── Metrics queries ──────────────────────────────────────────────────────

def _session_counts() -> Dict[str, Any]:
    rows = _run_query("""
        SELECT
            COUNT(*)                                              AS total,
            COUNT(*) FILTER (WHERE created_at >= %s)              AS active_24h,
            COUNT(*) FILTER (WHERE created_at >= %s)              AS active_7d,
            COUNT(*) FILTER (WHERE updated_at >= %s)              AS touched_1h
        FROM chat_sessions
    """, (_hours_ago(24), _hours_ago(24 * 7), _hours_ago(1)))
    if rows and rows[0]:
        r = rows[0]
        return {"total": r["total"], "active_24h": r["active_24h"],
                "active_7d": r["active_7d"], "touched_1h": r["touched_1h"]}
    return {"error": "db_unreachable"}


def _user_counts() -> Dict[str, Any]:
    rows = _run_query("""
        SELECT
            COUNT(*)                                           AS total,
            COUNT(*) FILTER (WHERE role = 'pro')               AS pro,
            COUNT(*) FILTER (WHERE role = 'scholar')           AS scholar,
            COUNT(*) FILTER (WHERE role = 'admin')             AS admin,
            COUNT(*) FILTER (WHERE role = 'free')              AS free,
            COUNT(*) FILTER (WHERE created_at >= %s)           AS new_7d,
            COUNT(*) FILTER (WHERE updated_at >= %s)           AS active_7d
        FROM profiles
    """, (_hours_ago(24 * 7), _hours_ago(24 * 7)))
    if rows and rows[0]:
        r = rows[0]
        return {
            "total": r["total"], "pro": r["pro"], "scholar": r["scholar"],
            "admin": r["admin"], "free": r["free"],
            "new_7d": r["new_7d"], "active_7d": r["active_7d"],
        }
    return {"error": "db_unreachable"}


def _usage_24h() -> Dict[str, Any]:
    rows = _run_query("""
        SELECT
            COALESCE(SUM(tokens_used), 0)          AS tokens_24h,
            COUNT(*)                                AS messages_24h,
            COUNT(*) FILTER (WHERE mode = 'deep')   AS research_24h
        FROM usage_logs
        WHERE created_at >= %s
    """, (_hours_ago(24),))
    if rows and rows[0]:
        r = rows[0]
        return {"tokens_24h": r["tokens_24h"], "messages_24h": r["messages_24h"],
                "research_24h": r["research_24h"]}
    return {"error": "db_unreachable"}


def _guest_24h() -> int:
    rows = _run_query("""
        SELECT COUNT(*) AS n FROM chat_sessions
        WHERE created_at >= %s AND user_id IS NULL
    """, (_hours_ago(24),))
    return rows[0]["n"] if rows and rows[0] else 0


# ── Main ──────────────────────────────────────────────────────────────────
def run() -> Dict[str, Any]:
    t0 = time.monotonic()
    errors: List[Dict[str, str]] = []

    backend = _fetch_status()
    if backend is None:
        errors.append({"code": "backend_unreachable", "message": f"{BACKEND_URL}/api/status failed"})

    sessions = _session_counts()
    if "error" in sessions:
        errors.append({"code": "db_unreachable", "message": "Could not query chat_sessions"})

    users = _user_counts()
    if "error" in users:
        errors.append({"code": "db_unreachable", "message": "Could not query profiles"})

    usage = _usage_24h()
    if "error" in usage:
        errors.append({"code": "db_unreachable", "message": "Could not query usage_logs"})

    guests = _guest_24h()

    data = {
        "timestamp": _now(),
        "backend": {
            "status": backend.get("status", "unknown") if backend else "down",
            "provider": backend.get("llm_provider", "") if backend else "",
            "model": backend.get("model", "") if backend else "",
            "verses": backend.get("total_verses", 0) if backend else 0,
            "gretil_texts": backend.get("gretil_texts", 0) if backend else 0,
        },
        "sessions": sessions,
        "users": {**users, "guest_24h": guests},
        "usage": usage,
    }

    meta = {"elapsed_ms": round((time.monotonic() - t0) * 1000, 1)}
    return _envelope(len(errors) == 0, data, meta, errors)


# ── CLI ──────────────────────────────────────────────────────────────────
def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    env = run()
    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        d = env["data"]
        b = d["backend"]
        s = d["sessions"]
        u = d["users"]
        us = d["usage"]
        print(f"🕉️  PuranGPT Monitor — {d['timestamp']}")
        print(f"   Backend:  {b['status']} ({b['provider']}/{b['model']}) — {b['verses']:,} verses")
        print(f"   Sessions: {s.get('total',0):,} total | {s.get('active_24h',0)} 24h | {s.get('touched_1h',0)} 1h")
        print(f"   Users:    {u.get('total',0):,} total | {u.get('pro',0)} pro | {u.get('guest_24h',0)} guest/24h | {u.get('new_7d',0)} new/7d")
        print(f"   Usage:    {us.get('tokens_24h',0):,} tokens/24h | {us.get('messages_24h',0):,} msgs/24h | {us.get('research_24h',0)} research")
        if env["errors"]:
            for e in env["errors"]:
                print(f"   ⚠️  {e['code']}: {e['message']}")
    return 0 if env["success"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
