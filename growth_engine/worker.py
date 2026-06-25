"""growth_engine worker — the autonomous posting loop.

Runs as a separate process so media jobs and channel API calls never block
the PuranGPT chat request path. Start with:
  venv/bin/python -m growth_engine.worker

Loop every TICK_SECONDS:
  1. post_scheduler tool → which (campaign, channel) slots are due
  2. Insert ge_post_queue rows (UNIQUE dedup_key prevents double-insert)
  3. Drain pending rows:
       mode=auto  → publish immediately via connector
       mode=draft → leave pending, dashboard queues for approval
  4. On publish: write ge_post_log (success or failure)
  5. On failure: exponential backoff, mark failed after MAX_ATTEMPTS
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from growth_engine.db import get_db_conn
from growth_engine.llm import ensure_http_client, close_http_client
from growth_engine.vault import vault
from growth_engine.connectors.registry import get_connector
from growth_engine.schema import init_growth_schema
from tools.post_scheduler.check import run as schedule_check
from tools.connector_envelope.check import run as normalize_response
from tools.content_policy_check.check import run as policy_check

logger = logging.getLogger(__name__)

TICK_SECONDS = int(os.getenv("GE_TICK_SECONDS", "60"))
MAX_ATTEMPTS = int(os.getenv("GE_MAX_ATTEMPTS", "3"))
_stop = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Queue management ──────────────────────────────────────────────────────────

def _upsert_queue_row(conn, campaign_id: str, asset_id: Optional[str],
                      channel: str, mode: str, dedup_key: str, scheduled_for: str):
    """Insert a queue row; silently ignore duplicate dedup_key (idempotent)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ge_post_queue
                (campaign_id, asset_id, channel, mode, scheduled_for, dedup_key)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (dedup_key) DO NOTHING
            """,
            (campaign_id, asset_id, channel, mode, scheduled_for, dedup_key),
        )
    conn.commit()


def _load_active_campaigns(conn) -> list:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text, app_slug, brief, status FROM ge_campaigns WHERE status = 'active'"
        )
        return [dict(r) for r in cur.fetchall()]


def _last_posted_per_channel(conn, campaign_id: str) -> dict:
    """Return {channel: iso8601} for the last successful post per channel."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT q.channel, MAX(l.posted_at)::text AS last
            FROM ge_post_log l
            JOIN ge_post_queue q ON q.id = l.queue_id
            WHERE q.campaign_id = %s AND l.result = 'posted'
            GROUP BY q.channel
            """,
            (campaign_id,),
        )
        return {r["channel"]: r["last"] for r in cur.fetchall()}


def _drain_pending(conn) -> list:
    """Fetch and lock pending auto-mode rows due now."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, campaign_id::text, asset_id::text,
                   channel, mode, attempts
            FROM ge_post_queue
            WHERE status = 'pending'
              AND mode = 'auto'
              AND scheduled_for <= NOW()
            ORDER BY scheduled_for
            LIMIT 20
            FOR UPDATE SKIP LOCKED
            """,
        )
        return [dict(r) for r in cur.fetchall()]


def _set_queue_status(conn, queue_id: str, status: str, bump_attempts: bool = False):
    with conn.cursor() as cur:
        if bump_attempts:
            cur.execute(
                "UPDATE ge_post_queue SET status=%s, attempts=attempts+1 WHERE id=%s",
                (status, queue_id),
            )
        else:
            cur.execute("UPDATE ge_post_queue SET status=%s WHERE id=%s", (status, queue_id))
    conn.commit()


def _write_log(conn, queue_id: str, channel: str, result: str,
               external_id: str = "", external_url: str = "", error: str = ""):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ge_post_log (queue_id, channel, external_id, external_url, result, error)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (queue_id, channel, external_id, external_url, result, error or None),
        )
    conn.commit()


def _load_asset(conn, asset_id: Optional[str]) -> Optional[dict]:
    if not asset_id:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT payload FROM ge_content_assets WHERE id = %s", (asset_id,))
        row = cur.fetchone()
        return dict(row["payload"]) if row else None


# ── Scheduling tick ───────────────────────────────────────────────────────────

def _schedule_tick(conn):
    """Ask post_scheduler which slots are due; insert queue rows for each."""
    campaigns = _load_active_campaigns(conn)
    now = _now_iso()
    for camp in campaigns:
        brief = camp["brief"] if isinstance(camp["brief"], dict) else json.loads(camp["brief"])
        campaign = {
            "campaign_id": camp["id"],
            "cadence": brief.get("cadence", "daily"),
            "channels": brief.get("channels", []),
        }
        last_posted = _last_posted_per_channel(conn, camp["id"])
        env = schedule_check(campaign=campaign, last_posted=last_posted, now=now)
        if not env["success"]:
            logger.error("post_scheduler failed for %s: %s", camp["id"], env["errors"])
            continue
        for slot in env["data"]["due"]:
            connector = get_connector(slot["channel"])
            mode = connector.mode if connector else "draft"
            _upsert_queue_row(
                conn,
                campaign_id=slot["campaign_id"],
                asset_id=None,  # asset generated at publish time for now
                channel=slot["channel"],
                mode=mode,
                dedup_key=slot["dedup_key"],
                scheduled_for=slot["scheduled_for"],
            )
            logger.info("queued: %s / %s (mode=%s)", slot["campaign_id"], slot["channel"], mode)


# ── Publish ───────────────────────────────────────────────────────────────────

async def _publish_row(conn, row: dict):
    """Generate (if needed) and publish one queue row. Updates log + status."""
    queue_id = row["id"]
    channel = row["channel"]
    connector = get_connector(channel)
    if not connector:
        logger.error("no connector for channel %s", channel)
        _set_queue_status(conn, queue_id, "failed")
        return

    # Load or generate the asset text.
    asset = _load_asset(conn, row.get("asset_id"))
    if not asset:
        # Generate on-the-fly (no pre-stored asset yet).
        from growth_engine.generator.campaign import CampaignGenerator
        gen = CampaignGenerator()
        generated = None
        async for event, content in gen.daily_verse(channel):
            if event == "asset":
                generated = content
                break
        if not generated:
            logger.warning("generation failed for queue %s, will retry", queue_id)
            _set_queue_status(conn, queue_id, "pending", bump_attempts=True)
            return
        asset = generated

    # Policy gate — never send a bad post to the live API.
    check = policy_check(channel=channel, text=asset.get("text", ""))
    if not (check["success"] and check["data"]["ok"]):
        logger.error("policy rejected queue %s: %s", queue_id, check)
        _set_queue_status(conn, queue_id, "failed")
        _write_log(conn, queue_id, channel, "failed", error="policy_rejected")
        return

    # Fetch credentials.
    keys = vault.get(user_id=_campaign_user(conn, row), channel=channel)
    if not keys:
        logger.warning("no keys for %s/%s, draft-holding", channel, queue_id)
        _set_queue_status(conn, queue_id, "pending")
        return

    _set_queue_status(conn, queue_id, "publishing")
    try:
        raw = connector.publish(asset=asset, keys=keys)
        handle = keys.get("handle", "")
        env = normalize_response(channel=channel, raw=raw, handle=handle)
        if env["success"]:
            d = env["data"]
            _write_log(conn, queue_id, channel, "posted",
                       external_id=d["external_id"], external_url=d["external_url"])
            _set_queue_status(conn, queue_id, "posted")
            logger.info("POSTED %s → %s", channel, d["external_url"])
        else:
            err = env["errors"][0]["message"]
            attempts = row["attempts"] + 1
            status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
            _set_queue_status(conn, queue_id, status, bump_attempts=True)
            _write_log(conn, queue_id, channel, "failed", error=err)
            logger.warning("connector error %s (attempt %d): %s", channel, attempts, err)
    except Exception as e:
        attempts = row["attempts"] + 1
        status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
        _set_queue_status(conn, queue_id, status, bump_attempts=True)
        _write_log(conn, queue_id, channel, "failed", error=str(e))
        logger.error("publish exception %s: %s", channel, e)


def _campaign_user(conn, row: dict) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT user_id FROM ge_campaigns WHERE id = %s",
                    (row["campaign_id"],))
        r = cur.fetchone()
        return r["user_id"] if r else ""


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run_worker():
    global _stop
    logger.info("growth_engine worker starting (tick=%ds)", TICK_SECONDS)
    await ensure_http_client()
    try:
        while not _stop:
            conn = get_db_conn()
            if not conn:
                logger.warning("no DB — skipping tick")
            else:
                try:
                    _schedule_tick(conn)
                    pending = _drain_pending(conn)
                    for row in pending:
                        await _publish_row(conn, row)
                except Exception as e:
                    logger.error("tick error: %s", e)
                finally:
                    conn.close()
            await asyncio.sleep(TICK_SECONDS)
    finally:
        await close_http_client()
        logger.info("worker stopped")


def _handle_stop(*_):
    global _stop
    _stop = True
    logger.info("stop signal received")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    if not init_growth_schema():
        raise SystemExit("DB schema init failed — is VECTOR_DB_URL set?")
    asyncio.run(run_worker())
