import os
import json
import time
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, max_history=100):
        self.max_history = max_history
        self.db_url = os.getenv("VECTOR_DB_URL")
        self._init_db()

    def _get_conn(self):
        # Route through the shared db_client pool instead of opening a fresh
        # psycopg2 connection per call (sessions are read/written several times
        # per chat turn, so this was a big chunk of the connection churn).
        from backend.db_client import get_db_conn
        return get_db_conn()

    def _init_db(self):
        conn = self._get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    display_name TEXT,
                    role TEXT DEFAULT 'free',
                    subscription_status TEXT DEFAULT 'inactive',
                    subscription_plan TEXT,
                    subscription_expires_at TIMESTAMPTZ,
                    daily_message_count INT DEFAULT 0,
                    deep_research_count INT DEFAULT 0,
                    daily_reset_at TIMESTAMPTZ DEFAULT NOW(),
                    stripe_customer_id TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_profiles_role ON profiles(role);

                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    logto_user_id TEXT,
                    guest_id TEXT,
                    title TEXT DEFAULT 'New Inquiry',
                    messages JSONB DEFAULT '[]',
                    journey_summary TEXT DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_logto_user ON chat_sessions(logto_user_id);
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_guest ON chat_sessions(guest_id);

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
                    provider TEXT,
                    external_subscription_id TEXT,
                    plan TEXT,
                    status TEXT,
                    current_period_start TIMESTAMPTZ DEFAULT NOW(),
                    current_period_end TIMESTAMPTZ
                );

                CREATE TABLE IF NOT EXISTS usage_logs (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT,
                    session_id TEXT,
                    model_used TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                -- Guest rate limiting, keyed by IP|device-id, one row per guest per UTC day.
                -- Replaces the old in-memory per-worker dict (which gave guests N× the
                -- limit across N workers and reset on every deploy). Atomic UPSERT +
                -- count increment makes the check race-free and shared across workers.
                CREATE TABLE IF NOT EXISTS guest_usage (
                    guest_id TEXT NOT NULL,
                    usage_date DATE NOT NULL,
                    count INT DEFAULT 0,
                    PRIMARY KEY (guest_id, usage_date)
                );
                CREATE INDEX IF NOT EXISTS idx_guest_usage_date ON guest_usage(usage_date);
                """)
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize chat_sessions table: {e}")
        finally:
            conn.close()

    def count_active_sessions(self, minutes: int = 15) -> int:
        """Sessions updated within the last `minutes` — a real 'active now' metric.
        (Replaces a dead reference to an in-memory .sessions dict that no longer
        exists since sessions moved to Postgres, which always reported 0.)"""
        conn = self._get_conn()
        if not conn:
            return 0
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM chat_sessions WHERE updated_at > NOW() - (%s || ' minutes')::interval",
                    (minutes,),
                )
                row = cur.fetchone()
                return (row["n"] if row else 0) or 0
        except Exception as e:
            logger.error(f"count_active_sessions failed: {e}")
            return 0
        finally:
            conn.close()

    def get_session(self, session_id: str, user_id: str = None, guest_id: str = None) -> dict:
        conn = self._get_conn()
        if not conn:
            return {"id": session_id, "title": "New Chat", "updated_at": time.time(), "history": [], "journey_summary": ""}
        
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("SELECT * FROM chat_sessions WHERE id = %s AND logto_user_id = %s", (session_id, user_id))
                else:
                    cur.execute("SELECT * FROM chat_sessions WHERE id = %s AND guest_id = %s", (session_id, guest_id))
                
                row = cur.fetchone()
                if row:
                    updated_at = row["updated_at"].timestamp() if row["updated_at"] else time.time()
                    return {
                        "id": row["id"],
                        "title": row["title"] or "New Chat",
                        "updated_at": updated_at,
                        "history": row["messages"] or [],
                        "journey_summary": row.get("journey_summary", "")
                    }
        except Exception as e:
            logger.error(f"Error fetching session {session_id}: {e}")
        finally:
            conn.close()

        return {"id": session_id, "title": "New Chat", "updated_at": time.time(), "history": [], "journey_summary": ""}

    def save_session(self, session_id: str, data: dict, user_id: str = None, guest_id: str = None):
        conn = self._get_conn()
        if not conn:
            return

        try:
            messages_json = json.dumps(data.get("history", []))
            title = data.get("title", "New Chat")
            journey_summary = data.get("journey_summary", "")
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_sessions (id, logto_user_id, guest_id, title, messages, journey_summary, updated_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        messages = EXCLUDED.messages,
                        journey_summary = EXCLUDED.journey_summary,
                        updated_at = NOW();
                """, (session_id, user_id, guest_id, title, messages_json, journey_summary))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving session {session_id}: {e}")
            conn.rollback()
        finally:
            conn.close()

    def append_messages(self, session_id: str, messages: List[dict], user_id: str = None, guest_id: str = None):
        session = self.get_session(session_id, user_id, guest_id)
        
        if not session.get("history") and messages:
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "").strip()
                    title = content[:40] + ("..." if len(content) > 40 else "")
                    session["title"] = title
                    break
                    
        session["history"] = session.get("history", []) + messages
        if len(session["history"]) > self.max_history:
            session["history"] = session["history"][-self.max_history:]
            
        self.save_session(session_id, session, user_id, guest_id)
        return session
        
    def truncate_session(self, session_id: str, index: int, user_id: str = None, guest_id: str = None):
        session = self.get_session(session_id, user_id, guest_id)
        if "history" in session and 0 <= index <= len(session["history"]):
            session["history"] = session["history"][:index]
            self.save_session(session_id, session, user_id, guest_id)
        return session
        
    def clear_session(self, session_id: str, user_id: str = None, guest_id: str = None):
        conn = self._get_conn()
        if not conn:
            return
            
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("DELETE FROM chat_sessions WHERE id = %s AND logto_user_id = %s", (session_id, user_id))
                else:
                    cur.execute("DELETE FROM chat_sessions WHERE id = %s AND guest_id = %s", (session_id, guest_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            conn.rollback()
        finally:
            conn.close()
            
    def get_all_sessions(self, user_id: str = None, guest_id: str = None) -> List[dict]:
        conn = self._get_conn()
        if not conn:
            return []
            
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("SELECT id, title, updated_at FROM chat_sessions WHERE logto_user_id = %s ORDER BY updated_at DESC", (user_id,))
                else:
                    if not guest_id:
                        return []
                    cur.execute("SELECT id, title, updated_at FROM chat_sessions WHERE guest_id = %s ORDER BY updated_at DESC", (guest_id,))
                
                rows = cur.fetchall()
                sessions = []
                for row in rows:
                    updated_at = row["updated_at"].timestamp() if row["updated_at"] else time.time()
                    sessions.append({
                        "id": row["id"],
                        "title": row["title"] or "Chat",
                        "updated_at": updated_at
                    })
                return sessions
        except Exception as e:
            logger.error(f"Error fetching all sessions: {e}")
            return []
        finally:
            conn.close()
