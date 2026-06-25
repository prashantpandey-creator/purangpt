"""persistence — durable storage for seeker (player) state.

The narrative engine's SeekerState lives in a process-memory dict by default,
so every server restart wipes every player. This module persists it to the same
Postgres the backend already uses (via backend.db_client.get_db_conn), in a
self-contained `game_seekers` table it bootstraps lazily.

Design choices:
  - SELF-CONTAINED: does not touch session_manager._init_db or db_client. It owns
    its table and bootstraps it on first use. The engine stays a sealed unit.
  - GRACEFUL: if there is no DB (no VECTOR_DB_URL, import fails, connection
    refused), every function returns a falsy/None result and the caller falls
    back to in-memory. The game never crashes for lack of a database.
  - LOSSLESS: stores the whole SeekerState as one JSONB blob via to_dict(); reads
    back via from_dict(). (Both sides roundtrip — see test_engine roundtrip tests.)

Table:
  game_seekers(session_id TEXT PK, user_id TEXT, state JSONB, created/updated TIMESTAMPTZ)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from narrative_engine.seeker import SeekerState

logger = logging.getLogger(__name__)

_bootstrapped = False
_db_available: Optional[bool] = None  # None = unknown, True/False once probed


def _get_conn():
    """Borrow a pooled connection from the backend, or None if unavailable."""
    try:
        from backend.db_client import get_db_conn
    except Exception:
        return None
    try:
        return get_db_conn()
    except Exception as e:
        logger.debug(f"[narrative_engine.persistence] no DB conn: {e}")
        return None


def _ensure_table() -> bool:
    """Create the game_seekers table if needed. Returns True if the DB is usable.

    Probes once and caches the result; subsequent calls are free when the DB is
    down so we don't hammer a dead connection on every request.
    """
    global _bootstrapped, _db_available
    if _bootstrapped:
        return bool(_db_available)

    conn = _get_conn()
    if conn is None:
        _db_available = False
        _bootstrapped = True
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS game_seekers (
                    session_id  TEXT PRIMARY KEY,
                    user_id     TEXT,
                    state       JSONB NOT NULL DEFAULT '{}',
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_game_seekers_user
                    ON game_seekers(user_id);
            """)
        conn.commit()
        _db_available = True
    except Exception as e:
        logger.warning(f"[narrative_engine.persistence] table bootstrap failed: {e}")
        _db_available = False
    finally:
        conn.close()

    _bootstrapped = True
    return bool(_db_available)


def save_seeker(session_id: str, seeker: SeekerState,
                user_id: Optional[str] = None) -> bool:
    """Persist a seeker's state. Returns True on success, False if no DB / error.

    UPSERT keyed on session_id — last write wins, updated_at bumped.
    """
    if not _ensure_table():
        return False

    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO game_seekers (session_id, user_id, state, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (session_id) DO UPDATE
                  SET state = EXCLUDED.state,
                      user_id = COALESCE(EXCLUDED.user_id, game_seekers.user_id),
                      updated_at = NOW();
            """, (session_id, user_id, json.dumps(seeker.to_dict(), ensure_ascii=False)))
        conn.commit()
        return True
    except Exception as e:
        logger.warning(f"[narrative_engine.persistence] save failed for {session_id}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def load_seeker(session_id: str) -> Optional[SeekerState]:
    """Load a seeker's state, or None if not found / no DB."""
    if not _ensure_table():
        return None

    conn = _get_conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT state FROM game_seekers WHERE session_id = %s;",
                (session_id,))
            row = cur.fetchone()
        if not row:
            return None
        # RealDictCursor → row is a dict; state may be dict (JSONB) or str
        state = row["state"] if isinstance(row, dict) else row[0]
        if isinstance(state, str):
            state = json.loads(state)
        if not state:
            return None
        return SeekerState.from_dict(state)
    except Exception as e:
        logger.warning(f"[narrative_engine.persistence] load failed for {session_id}: {e}")
        return None
    finally:
        conn.close()


def delete_seeker(session_id: str) -> bool:
    """Delete a seeker's persisted state. Returns True if a row was removed."""
    if not _ensure_table():
        return False

    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM game_seekers WHERE session_id = %s;", (session_id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception as e:
        logger.warning(f"[narrative_engine.persistence] delete failed for {session_id}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def db_status() -> Dict[str, Any]:
    """Report whether persistence is wired to a live DB — for /meta/health."""
    available = _ensure_table()
    return {
        "persistence": "postgres" if available else "in-memory-only",
        "db_available": available,
    }
