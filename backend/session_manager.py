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

                -- Workspace: uploaded document tracking
                CREATE TABLE IF NOT EXISTS workspace_documents (
                    doc_id        TEXT PRIMARY KEY,
                    user_id       TEXT NOT NULL,
                    filename      TEXT NOT NULL,
                    doc_type      TEXT NOT NULL,
                    source_url    TEXT,
                    status        TEXT NOT NULL DEFAULT 'pending',
                    error_msg     TEXT,
                    chunk_count   INT DEFAULT 0,
                    section_count INT DEFAULT 0,
                    title         TEXT,
                    thread_map    JSONB,
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    updated_at    TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_workspace_user ON workspace_documents(user_id);

                -- Workspace: per-user reading progress (semantic coverage tracking)
                CREATE TABLE IF NOT EXISTS reading_progress (
                    user_id     TEXT NOT NULL,
                    doc_id      TEXT NOT NULL,
                    chunk_id    TEXT NOT NULL,
                    read_at     TIMESTAMPTZ DEFAULT NOW(),
                    time_spent  INT,
                    PRIMARY KEY (user_id, doc_id, chunk_id)
                );
                CREATE INDEX IF NOT EXISTS idx_progress_user_doc ON reading_progress(user_id, doc_id);

                -- Seeker memory (axis 2 of the "Smriti" design): Guruji remembering
                -- the PERSON across sessions. Additive columns on existing tables, so
                -- ALTER ... IF NOT EXISTS rather than baking into the CREATE above
                -- (idempotent on every boot, safe on tables that already have rows).
                --   journey_summary_at: when this session's running read was last
                --     revised — the restart-proof staleness clock (a process-local
                --     timestamp would reset every deploy and re-distill the world).
                --   profiles.seeker_profile(_at): the cross-session distilled read of
                --     the seeker, derived from all their session journey_summaries.
                ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS journey_summary_at TIMESTAMPTZ;
                ALTER TABLE profiles ADD COLUMN IF NOT EXISTS seeker_profile TEXT DEFAULT '';
                ALTER TABLE profiles ADD COLUMN IF NOT EXISTS seeker_profile_at TIMESTAMPTZ;

                -- Earned warmth (Phase 1): Guruji's warmth grows with DISTINCT
                -- return-days, not message count. visit_days is the load-bearing
                -- signal for the warmth-tier classifier (tools.seeker_memory.warmth).
                -- Denormalized here (bumped once per tz-day via a gap-gated atomic
                -- UPDATE) rather than COUNT(DISTINCT date(...))-d every turn, which
                -- would sort a heavy returner's whole history on the hot path.
                --   visit_days:    distinct calendar days with any activity (>=1).
                --   last_seen_at:  the gate clock + recency-decay input.
                --   first_seen_at: when this seeker first arrived (audit / future).
                ALTER TABLE profiles ADD COLUMN IF NOT EXISTS visit_days INT DEFAULT 1;
                ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;
                ALTER TABLE profiles ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ;
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
                    # Deterministic title from first query
                    _GURUJI_KEY_TERMS = {
                        "ojas", "amrita", "prana", "kundalini", "samadhi", "khechari",
                        "mudra", "bandha", "kriya", "shiva", "shakti", "mercury",
                        "parada", "time", "immortality", "nada", "bindu", "chakra",
                        "dhyana", "dharana", "yama", "niyama", "asana", "pranayama",
                        "guru", "shishya", "parampara", "veda", "purana", "upanishad",
                        "gita", "yoga", "yogi", "akasha", "tattva", "karma", "bhakti",
                        "jnana", "tantra"
                    }
                    import re
                    words = [w for w in re.findall(r'\b\w+\b', content) if len(w) > 3]
                    skt_terms = [w.title() for w in words if w.lower() in _GURUJI_KEY_TERMS]
                    
                    if skt_terms:
                        # "Ojas and Time" or just "Ojas"
                        title = " and ".join(list(dict.fromkeys(skt_terms))[:2])
                    else:
                        # fallback: first 4 meaningful words
                        stop_words = {"what", "how", "why", "who", "when", "where", "is", "are", "do", "does", "can", "could", "would", "the", "this", "that", "please", "tell", "know", "about", "with"}
                        meaningful = [w.title() for w in words if w.lower() not in stop_words][:4]
                        if meaningful:
                            title = " ".join(meaningful)
                        else:
                            title = content[:30].title() + ("..." if len(content) > 30 else "")
                    
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

    async def generate_user_profile(self, user_id: str, limit: int = 20) -> str:
        """Reads the journey_summary of a user's most-recent sessions and generates
        a 1-paragraph distilled read of their spiritual/philosophical arc — the
        cross-session `seeker_profile` that the {seeker_memory} block carries.

        BOUNDED: takes the `limit` most-recently-updated sessions (newest first),
        not an unbounded scan — a years-deep seeker would otherwise sort + stuff
        hundreds of summaries into one prompt. Recent sessions carry the live arc;
        the distiller already overwrites-on-contradiction so old reads age out."""
        conn = self._get_conn()
        if not conn:
            return ""

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT journey_summary FROM chat_sessions "
                    "WHERE logto_user_id = %s AND journey_summary IS NOT NULL "
                    "AND journey_summary != '' "
                    "ORDER BY updated_at DESC LIMIT %s",
                    (user_id, limit))
                rows = cur.fetchall()

            summaries = [row["journey_summary"] for row in rows]
            if not summaries:
                return "New seeker. No established philosophical baseline yet."
                
            # We defer the LLM import locally to avoid circular dependencies
            from backend.main import call_llm_once
            
            prompt = (
                "You are profiling a spiritual seeker's philosophical baseline based on their past session summaries.\n"
                "Synthesize the following session summaries into a SINGLE paragraph (max 100 words) describing "
                "their core spiritual inquiries, their level of scriptural understanding, and any recurring themes.\n\n"
                "Session summaries:\n" + "\n".join(f"- {s}" for s in summaries)
            )
            
            profile = await call_llm_once([
                {"role": "system", "content": "You are an analytical profiling assistant. Be clinical and precise."},
                {"role": "user", "content": prompt}
            ], temperature=0.1)
            
            return profile.strip()

        except Exception as e:
            logger.error(f"Error generating user profile for {user_id}: {e}")
            return ""
        finally:
            conn.close()

    # --- Seeker memory (axis 2): the running per-session read of the seeker. ---
    # The WRITE side (save_journey_summary) and the gate-READ side
    # (journey_summary_stale) of the fire-and-forget distill hook in main.py. Both
    # are best-effort: a DB miss must never break a chat turn, so they swallow and
    # return a benign default ("" / not-stale) rather than raise.

    def save_journey_summary(self, session_id: str, summary: str,
                             user_id: str = None, guest_id: str = None) -> bool:
        """Persist the revised running read for this session and stamp the
        staleness clock. Scoped by owner so a guest can't overwrite a user's row
        (or vice-versa). Returns True on a real write."""
        if not summary or not summary.strip():
            return False
        conn = self._get_conn()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        "UPDATE chat_sessions SET journey_summary = %s, "
                        "journey_summary_at = NOW() WHERE id = %s AND logto_user_id = %s",
                        (summary.strip(), session_id, user_id))
                else:
                    cur.execute(
                        "UPDATE chat_sessions SET journey_summary = %s, "
                        "journey_summary_at = NOW() WHERE id = %s AND guest_id = %s",
                        (summary.strip(), session_id, guest_id))
                wrote = cur.rowcount > 0
            conn.commit()
            return wrote
        except Exception as e:
            logger.error(f"save_journey_summary failed for {session_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def journey_summary_stale(self, session_id: str, max_age_minutes: int = 30,
                              user_id: str = None, guest_id: str = None):
        """The distill gate's restart-proof clock: is this session's running read
        older than max_age_minutes (or never written)? Returns
        (is_stale: bool, prior_summary: str). Reads journey_summary_at from the
        DB — NOT process memory — so a deploy/restart doesn't re-distill the world.
        On any error, returns (False, "") so the gate stays CLOSED (fail-safe: a
        DB hiccup must not trigger a flood of distills)."""
        conn = self._get_conn()
        if not conn:
            return (False, "")
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        "SELECT journey_summary, journey_summary_at FROM chat_sessions "
                        "WHERE id = %s AND logto_user_id = %s", (session_id, user_id))
                else:
                    cur.execute(
                        "SELECT journey_summary, journey_summary_at FROM chat_sessions "
                        "WHERE id = %s AND guest_id = %s", (session_id, guest_id))
                row = cur.fetchone()
            if not row:
                return (False, "")
            prior = row.get("journey_summary") or ""
            stamped_at = row.get("journey_summary_at")
            if stamped_at is None:
                # Never distilled for this session → stale (write the first read).
                return (True, prior)
            age = datetime.now(timezone.utc) - stamped_at
            is_stale = age.total_seconds() >= max_age_minutes * 60
            return (is_stale, prior)
        except Exception as e:
            logger.error(f"journey_summary_stale failed for {session_id}: {e}")
            return (False, "")
        finally:
            conn.close()

    # --- Earned warmth (Phase 1): the distinct-return-day signal. ---------------
    # bump_visit_day is the WRITE side (one atomic, gap-gated increment per tz-day);
    # get_visit_stats is the READ side that feeds tools.seeker_memory.warmth. Both
    # are signed-in only (a durable identity to attach a relationship to) and
    # best-effort — a DB miss must never break a chat turn.

    def bump_visit_day(self, user_id: str, tz: str = "UTC") -> bool:
        """Increment visit_days by ONE iff this is the seeker's first activity on a
        new calendar day (bucketed in THEIR timezone). The gate is the whole point:
          - a daily returner who continues ONE localStorage-persisted thread still
            increments (the gate is on the date, not on a new chat_sessions row);
          - a 10-new-chats-in-one-afternoon spammer increments at most ONCE.
        Atomic: the WHERE clause IS the gate, so two concurrent turns on the same
        day can't double-count (the second finds last_seen_at already today).
        Returns True iff this call actually bumped the counter (rowcount > 0).

        `tz` is an IANA name (e.g. 'America/New_York'); an unknown tz makes Postgres
        raise inside the txn → we swallow and return False (no bump, turn unharmed).
        """
        if not user_id:
            return False
        conn = self._get_conn()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                # first_seen_at is set once (COALESCE keeps the original); the gate
                # compares calendar dates in the seeker's tz, so crossing local
                # midnight — not a fixed 24h window — is what earns a visit-day.
                cur.execute(
                    """
                    UPDATE profiles
                       SET visit_days    = visit_days + 1,
                           last_seen_at  = NOW(),
                           first_seen_at = COALESCE(first_seen_at, NOW())
                     WHERE id = %s
                       AND (
                            last_seen_at IS NULL
                            OR (last_seen_at AT TIME ZONE %s)::date
                                 < (NOW() AT TIME ZONE %s)::date
                       )
                    """,
                    (user_id, tz, tz),
                )
                bumped = cur.rowcount > 0
            conn.commit()
            return bumped
        except Exception as e:
            logger.error(f"bump_visit_day failed for {user_id} (tz={tz}): {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_visit_stats(self, user_id: str):
        """Read the earned-warmth signal for the classifier. Returns
        (visit_days: int, days_since_last: int|None). days_since_last is computed
        from last_seen_at (None if never seen). On any error returns (1, None) —
        the STRANGER default — so the warmth path stays fail-graceful (a DB hiccup
        must never manufacture false intimacy)."""
        if not user_id:
            return (1, None)
        conn = self._get_conn()
        if not conn:
            return (1, None)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT visit_days, last_seen_at FROM profiles WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
            if not row:
                return (1, None)
            visit_days = row.get("visit_days") or 1
            last_seen = row.get("last_seen_at")
            days_since_last = None
            if last_seen is not None:
                delta = datetime.now(timezone.utc) - last_seen
                days_since_last = max(0, delta.days)
            return (visit_days, days_since_last)
        except Exception as e:
            logger.error(f"get_visit_stats failed for {user_id}: {e}")
            return (1, None)
        finally:
            conn.close()

    # --- Cross-session seeker profile (Phase 1 arc): the distilled read of WHO ---
    # the seeker is, synthesized from their session journey_summaries by
    # generate_user_profile and carried into the {seeker_memory} block. Mirrors the
    # save_journey_summary / journey_summary_stale pair so the live wire can refresh
    # it lazily (not every turn) and read it cheaply each turn.

    def get_seeker_profile(self, user_id: str) -> str:
        """The current cross-session distilled read for this seeker (or '')."""
        if not user_id:
            return ""
        conn = self._get_conn()
        if not conn:
            return ""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT seeker_profile FROM profiles WHERE id = %s", (user_id,))
                row = cur.fetchone()
            return (row.get("seeker_profile") if row else "") or ""
        except Exception as e:
            logger.error(f"get_seeker_profile failed for {user_id}: {e}")
            return ""
        finally:
            conn.close()

    def save_seeker_profile(self, user_id: str, profile: str) -> bool:
        """Persist the freshly-distilled cross-session read + stamp its clock.
        Returns True on a real write. A blank profile is never written (a degraded
        LLM must not wipe a good prior read — same discipline as journey_summary)."""
        if not user_id or not profile or not profile.strip():
            return False
        conn = self._get_conn()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE profiles SET seeker_profile = %s, "
                    "seeker_profile_at = NOW() WHERE id = %s",
                    (profile.strip(), user_id))
                wrote = cur.rowcount > 0
            conn.commit()
            return wrote
        except Exception as e:
            logger.error(f"save_seeker_profile failed for {user_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def seeker_profile_stale(self, user_id: str, max_age_minutes: int = 1440):
        """Is the cross-session profile older than max_age_minutes (default 24h),
        or never generated? Returns (is_stale: bool, prior_profile: str). Reads the
        stamp from the DB so a restart doesn't re-synthesize the world. On error
        returns (False, "") — gate stays CLOSED (a DB hiccup must not trigger a
        flood of profile LLM calls)."""
        if not user_id:
            return (False, "")
        conn = self._get_conn()
        if not conn:
            return (False, "")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT seeker_profile, seeker_profile_at FROM profiles "
                    "WHERE id = %s", (user_id,))
                row = cur.fetchone()
            if not row:
                return (False, "")
            prior = row.get("seeker_profile") or ""
            stamped_at = row.get("seeker_profile_at")
            if stamped_at is None:
                return (True, prior)  # never generated → stale
            age = datetime.now(timezone.utc) - stamped_at
            return (age.total_seconds() >= max_age_minutes * 60, prior)
        except Exception as e:
            logger.error(f"seeker_profile_stale failed for {user_id}: {e}")
            return (False, "")
        finally:
            conn.close()
