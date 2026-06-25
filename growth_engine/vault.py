"""KeyVault — per-(user, channel) encrypted storage for social/API credentials.

Wraps the backend's Fernet helpers (encrypt_keys/decrypt_keys). Plaintext
credentials exist only in memory at publish time; the DB column ge_channel_
connections.enc_keys holds only Fernet ciphertext.

This is a thin orchestration layer over existing crypto — it never implements
encryption itself.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.db_client import encrypt_keys, decrypt_keys
from growth_engine.db import get_db_conn

logger = logging.getLogger(__name__)


class KeyVault:
    """Store/retrieve channel credentials, encrypted at rest."""

    def put(
        self,
        user_id: str,
        channel: str,
        mode: str,
        keys: dict,
        handle: Optional[str] = None,
    ) -> bool:
        """Upsert encrypted credentials for (user_id, channel). Returns True on success."""
        enc = encrypt_keys(keys)
        conn = get_db_conn()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ge_channel_connections
                        (user_id, channel, mode, enc_keys, handle, status)
                    VALUES (%s, %s, %s, %s, %s, 'active')
                    ON CONFLICT (user_id, channel) DO UPDATE SET
                        mode = EXCLUDED.mode,
                        enc_keys = EXCLUDED.enc_keys,
                        handle = EXCLUDED.handle,
                        status = 'active'
                    """,
                    (user_id, channel, mode, enc, handle),
                )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"KeyVault.put failed for {user_id}/{channel}: {e}")
            return False
        finally:
            conn.close()

    def get(self, user_id: str, channel: str) -> dict:
        """Return decrypted credentials for (user_id, channel), or {} if absent."""
        conn = get_db_conn()
        if not conn:
            return {}
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT enc_keys FROM ge_channel_connections "
                    "WHERE user_id = %s AND channel = %s AND status = 'active'",
                    (user_id, channel),
                )
                row = cur.fetchone()
                if not row:
                    return {}
                return decrypt_keys(row["enc_keys"])
        except Exception as e:
            logger.error(f"KeyVault.get failed for {user_id}/{channel}: {e}")
            return {}
        finally:
            conn.close()

    def list(self, user_id: str) -> list:
        """List a user's connections WITHOUT plaintext keys (dashboard-safe)."""
        conn = get_db_conn()
        if not conn:
            return []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT channel, mode, handle, status, last_checked_at "
                    "FROM ge_channel_connections WHERE user_id = %s "
                    "ORDER BY created_at DESC",
                    (user_id,),
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"KeyVault.list failed for {user_id}: {e}")
            return []
        finally:
            conn.close()


vault = KeyVault()
