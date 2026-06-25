"""Schema bootstrap for growth_engine — 6 ge_* tables.

Mirrors backend.session_manager.SessionManager._init_db(): plain
CREATE TABLE IF NOT EXISTS at startup, idempotent, no migration step (the
deploy pipeline is hands-off). Shares the same Postgres as the rest of the
stack (VECTOR_DB_URL). The `ge_` prefix avoids collision with the existing
profiles/subscriptions/usage_logs/chat_sessions/guest_usage tables.

`gen_random_uuid()` requires pgcrypto, which is already in use by the
frontend's api_keys table, so it is available in this DB.
"""

from __future__ import annotations

import logging

from growth_engine.db import get_db_conn

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS ge_campaigns (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL,
    app_slug   TEXT NOT NULL DEFAULT 'purangpt',
    name       TEXT NOT NULL,
    brief      JSONB NOT NULL DEFAULT '{}',
    status     TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ge_campaigns_user ON ge_campaigns(user_id);

CREATE TABLE IF NOT EXISTS ge_content_assets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES ge_campaigns(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    channel     TEXT,
    payload     JSONB NOT NULL DEFAULT '{}',
    file_path   TEXT,
    status      TEXT NOT NULL DEFAULT 'ready',
    meta        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ge_assets_campaign ON ge_content_assets(campaign_id);

CREATE TABLE IF NOT EXISTS ge_channel_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,
    channel         TEXT NOT NULL,
    mode            TEXT NOT NULL,
    enc_keys        TEXT NOT NULL,
    handle          TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    last_checked_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, channel)
);
CREATE INDEX IF NOT EXISTS idx_ge_conn_user ON ge_channel_connections(user_id);

CREATE TABLE IF NOT EXISTS ge_post_queue (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id   UUID REFERENCES ge_campaigns(id) ON DELETE CASCADE,
    asset_id      UUID REFERENCES ge_content_assets(id) ON DELETE CASCADE,
    channel       TEXT NOT NULL,
    mode          TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    approved_by   TEXT,
    attempts      INT DEFAULT 0,
    dedup_key     TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (dedup_key)
);
CREATE INDEX IF NOT EXISTS idx_ge_queue_due ON ge_post_queue(status, scheduled_for);

CREATE TABLE IF NOT EXISTS ge_post_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id    UUID REFERENCES ge_post_queue(id) ON DELETE SET NULL,
    channel     TEXT NOT NULL,
    external_id TEXT,
    external_url TEXT,
    result      TEXT NOT NULL,
    error       TEXT,
    posted_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ge_postlog_channel ON ge_post_log(channel, posted_at);

CREATE TABLE IF NOT EXISTS ge_analytics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_log_id UUID REFERENCES ge_post_log(id) ON DELETE CASCADE,
    channel     TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       NUMERIC NOT NULL DEFAULT 0,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ge_analytics_post ON ge_analytics(post_log_id);
"""

GE_TABLES = [
    "ge_campaigns",
    "ge_content_assets",
    "ge_channel_connections",
    "ge_post_queue",
    "ge_post_log",
    "ge_analytics",
]


def init_growth_schema() -> bool:
    """Create all ge_* tables if absent. Idempotent. Returns True on success."""
    conn = get_db_conn()
    if not conn:
        logger.warning("init_growth_schema: no DB connection (VECTOR_DB_URL unset?)")
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(_DDL)
        conn.commit()
        logger.info("growth_engine schema ready (%d tables)", len(GE_TABLES))
        return True
    except Exception as e:
        logger.error(f"init_growth_schema failed: {e}")
        return False
    finally:
        conn.close()


def tables_present() -> list:
    """Return which ge_* tables currently exist (for smoke tests)."""
    conn = get_db_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name = ANY(%s)",
                (GE_TABLES,),
            )
            return sorted(r["table_name"] for r in cur.fetchall())
    finally:
        conn.close()
