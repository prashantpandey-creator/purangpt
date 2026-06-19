import os
import json
from datetime import datetime, timezone
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

# Local Postgres Initialization
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool as pg_pool

db_url = os.getenv("VECTOR_DB_URL")

# ── Connection pool ──────────────────────────────────────────────────────────
# Previously every call did psycopg2.connect()+close(), so a single /api/chat
# opened ~9-12 fresh connections. With multiple workers that exhausted the shared
# logto-db (max 100 conns) and starved Logto auth itself. We now keep a small
# per-process ThreadedConnectionPool and lend connections out, returning them on
# close() instead of tearing down the TCP+auth handshake each time.
_pool = None
_pool_lock = threading.Lock()

# Per-process pool sizing: psycopg2 is sync, so concurrency is bounded by the
# uvicorn threadpool (default ~40). Keep maxconn modest so 2 workers stay well
# under Postgres limits: 2 × 10 = 20 connections worst case.
_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:  # double-checked under lock
                _pool = pg_pool.ThreadedConnectionPool(
                    _POOL_MIN, _POOL_MAX, dsn=db_url, cursor_factory=RealDictCursor
                )
    return _pool


class _PooledConn:
    """Thin proxy so existing `conn = get_db_conn(); ...; conn.close()` call sites
    work unchanged — close() returns the connection to the pool instead of
    severing it. Rolls back any open transaction before returning so a failed
    request never leaves a dirty connection in the pool."""

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if self._conn is None:
            return
        try:
            if not self._conn.closed:
                self._conn.rollback()
        except Exception:
            pass
        try:
            self._pool.putconn(self._conn)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass
        finally:
            self._conn = None


def get_db_conn():
    if not db_url:
        logger.warning("VECTOR_DB_URL not set in env, DB operations won't work.")
        return None
    try:
        conn = _get_pool().getconn()
        return _PooledConn(conn, _get_pool())
    except Exception as e:
        logger.error(f"Failed to get pooled Postgres connection: {e}")
        return None

# Encryption for BYOK Keys
FERNET_KEY = os.getenv("FERNET_KEY", "")
if not FERNET_KEY:
    FERNET_KEY = Fernet.generate_key().decode()
    logger.warning(f"FERNET_KEY not set. Generated ephemeral key: {FERNET_KEY}")
fernet = Fernet(FERNET_KEY.encode())

def encrypt_keys(keys_dict: dict) -> str:
    """Encrypts a dictionary of API keys."""
    json_str = json.dumps(keys_dict)
    encrypted = fernet.encrypt(json_str.encode())
    return encrypted.decode()

def decrypt_keys(encrypted_str: str) -> dict:
    """Decrypts an encrypted string of API keys."""
    if not encrypted_str:
        return {}
    try:
        decrypted = fernet.decrypt(encrypted_str.encode())
        return json.loads(decrypted.decode())
    except Exception as e:
        logger.error(f"Error decrypting BYOK keys: {e}")
        return {}

def get_profile(user_id: str) -> dict:
    """Fetch user profile from local Postgres."""
    conn = get_db_conn()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                # Convert timestamps to ISO format strings for compatibility
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
                return dict(row)
    except Exception as e:
        logger.error(f"Error fetching profile for {user_id}: {e}")
    finally:
        conn.close()
    return None

def create_profile_if_not_exists(user_id: str, email: str = None) -> dict:
    """Creates a user profile in local Postgres if it does not already exist."""
    conn = get_db_conn()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
                return dict(row)
            
            now = datetime.now(timezone.utc)
            cur.execute(
                "INSERT INTO profiles (id, email, created_at, updated_at) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (user_id, email, now, now)
            )
        conn.commit()
        return get_profile(user_id)
    except Exception as e:
        logger.error(f"Error in create_profile_if_not_exists for {user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()
    return None

def update_profile(user_id: str, data: dict):
    """Update user profile in local Postgres."""
    conn = get_db_conn()
    if not conn: return
    try:
        data["updated_at"] = datetime.now(timezone.utc)
        fields = []
        values = []
        for k, v in data.items():
            fields.append(f"{k} = %s")
            values.append(v)
        values.append(user_id)
        query = f"UPDATE profiles SET {', '.join(fields)} WHERE id = %s"
        with conn.cursor() as cur:
            cur.execute(query, tuple(values))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating profile for {user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def check_rate_limit(user_id: str, role: str, is_byok: bool = False) -> tuple[bool, int]:
    """Check if the user has exceeded their daily message limit."""
    if role in ["pro", "scholar", "admin"] or is_byok:
        return True, 999999
        
    profile = get_profile(user_id)
    if not profile:
        return False, 0
        
    limit = 10 # Free tier limit
    
    # Check if we need to reset the daily count
    last_reset = profile.get("daily_reset_at")
    try:
        last_reset_dt = datetime.fromisoformat(last_reset.replace('Z', '+00:00')) if last_reset else datetime.min.replace(tzinfo=timezone.utc)
    except:
        last_reset_dt = datetime.min.replace(tzinfo=timezone.utc)
        
    now = datetime.now(timezone.utc)
    if now.date() > last_reset_dt.date():
        # Reset count
        update_profile(user_id, {
            "daily_message_count": 0,
            "deep_research_count": 0,
            "daily_reset_at": now
        })
        return True, limit
        
    count = profile.get("daily_message_count", 0) or 0
    return count < limit, limit - count

def check_research_limit(user_id: str, role: str, is_byok: bool = False) -> tuple[bool, int]:
    """Check if the user has exceeded their daily deep research limit."""
    if is_byok:
        return True, 999999
        
    limit = 50 if role in ["pro", "scholar", "admin"] else 3
    
    profile = get_profile(user_id)
    if not profile:
        return False, 0
        
    count = profile.get("deep_research_count", 0) or 0
    return count < limit, limit - count

def increment_usage(user_id: str, session_id: str = None, model: str = None):
    """Increment the user's daily message count and log the usage."""
    conn = get_db_conn()
    if not conn: return
    try:
        profile = get_profile(user_id)
        if profile:
            new_count = (profile.get("daily_message_count", 0) or 0) + 1
            update_profile(user_id, {"daily_message_count": new_count})
            
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usage_logs (user_id, session_id, model_used, created_at) VALUES (%s, %s, %s, NOW())",
                (user_id, session_id, model)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Error incrementing usage for {user_id}: {e}")
        conn.rollback()
    finally:
        conn.close()
        
def increment_research_usage(user_id: str):
    """Increment the user's daily deep research count."""
    try:
        profile = get_profile(user_id)
        if profile:
            new_count = (profile.get("deep_research_count", 0) or 0) + 1
            update_profile(user_id, {"deep_research_count": new_count})
    except Exception as e:
        logger.error(f"Error incrementing research usage for {user_id}: {e}")

def get_admin_stats() -> dict:
    """Fetch analytics for the admin dashboard from local Postgres."""
    conn = get_db_conn()
    if not conn: return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM profiles")
            total_users = cur.fetchone()["count"]
            
            cur.execute("SELECT COUNT(*) FROM profiles WHERE role IN ('pro', 'scholar')")
            paid_users = cur.fetchone()["count"]
            
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            cur.execute("SELECT COUNT(*) FROM usage_logs WHERE created_at >= %s", (today_start,))
            messages_today = cur.fetchone()["count"]
            
            return {
                "total_users": total_users,
                "paid_users": paid_users,
                "messages_today": messages_today
            }
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        return {}
    finally:
        conn.close()

def get_all_users() -> list:
    """Fetch all users for admin dashboard from local Postgres."""
    conn = get_db_conn()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profiles ORDER BY created_at DESC LIMIT 100")
            rows = cur.fetchall()
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, datetime):
                        row[k] = v.isoformat()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching all users: {e}")
        return []
    finally:
        conn.close()
