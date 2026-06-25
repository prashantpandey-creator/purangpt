"""growth_engine FastAPI app — dashboard API at :8100.

Routes:
  GET  /health
  POST /campaigns                  create campaign
  GET  /campaigns                  list campaigns (user-scoped)
  GET  /campaigns/{id}             campaign detail + assets
  POST /campaigns/{id}/generate    trigger content generation (SSE stream)
  GET  /queue                      approval queue (draft-mode items)
  POST /queue/{id}/approve         approve a draft post
  POST /queue/{id}/reject          reject a draft post
  POST /connections                store channel keys in vault
  GET  /connections                list connections (no plaintext)
  GET  /analytics                  post stats

Auth: expects X-User-Sub header (set by the Next.js proxy using INTERNAL_SERVICE_KEY,
same pattern as /api/v1/chat in purangpt-next). In dev, X-User-Sub is accepted
without verification; production wires the Logto sub through the proxy.

Start standalone:
  venv/bin/python -m growth_engine.app        # dev, auto-reload
  uvicorn growth_engine.app:app --port 8100   # production
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from growth_engine.schema import init_growth_schema
from growth_engine.db import get_db_conn
from growth_engine.vault import vault
from growth_engine.llm import ensure_http_client, close_http_client
from growth_engine.connectors.registry import CONNECTORS
from tools.campaign_brief_validate.check import run as validate_brief

logger = logging.getLogger(__name__)


# ── App + lifespan ────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not init_growth_schema():
        logger.warning("DB schema init failed — check VECTOR_DB_URL")
    await ensure_http_client()
    yield
    await close_http_client()


app = FastAPI(title="growth_engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("GE_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_user(request: Request) -> str:
    sub = request.headers.get("X-User-Sub") or request.headers.get("x-user-sub")
    if not sub:
        raise HTTPException(status_code=401, detail="X-User-Sub header required")
    return sub


# ── Models ────────────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    app_slug: str = "purangpt"
    goal: str = "app_installs"
    audience: str
    channels: list
    cadence: str = "daily"


class ConnectionCreate(BaseModel):
    channel: str
    keys: dict
    handle: Optional[str] = None


class ApproveRequest(BaseModel):
    pass


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "channels": list(CONNECTORS.keys())}


# ── Campaigns ─────────────────────────────────────────────────────────────────

@app.post("/campaigns", status_code=201)
async def create_campaign(body: CampaignCreate, user_sub: str = Depends(get_user)):
    brief = body.dict()
    env = validate_brief(brief=brief)
    if not env["success"]:
        raise HTTPException(status_code=422, detail=env["errors"])
    normalized = env["data"]["normalized"]
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ge_campaigns (user_id, app_slug, name, brief, status)
                VALUES (%s, %s, %s, %s, 'active')
                RETURNING id::text
                """,
                (user_sub, normalized["app_slug"], normalized["name"],
                 __import__("json").dumps(normalized)),
            )
            campaign_id = cur.fetchone()["id"]
        conn.commit()
        return {"id": campaign_id, "status": "active", "brief": normalized}
    finally:
        conn.close()


@app.get("/campaigns")
async def list_campaigns(user_sub: str = Depends(get_user)):
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, name, app_slug, status, created_at::text "
                "FROM ge_campaigns WHERE user_id = %s ORDER BY created_at DESC",
                (user_sub,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, user_sub: str = Depends(get_user)):
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, name, app_slug, brief, status, created_at::text "
                "FROM ge_campaigns WHERE id = %s AND user_id = %s",
                (campaign_id, user_sub),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="campaign not found")
            camp = dict(row)
            cur.execute(
                "SELECT id::text, kind, channel, payload, status, created_at::text "
                "FROM ge_content_assets WHERE campaign_id = %s ORDER BY created_at DESC",
                (campaign_id,),
            )
            camp["assets"] = [dict(r) for r in cur.fetchall()]
        return camp
    finally:
        conn.close()


@app.post("/campaigns/{campaign_id}/generate")
async def generate_campaign(campaign_id: str, user_sub: str = Depends(get_user)):
    """SSE stream: generate content for all channels in this campaign."""
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT brief FROM ge_campaigns WHERE id = %s AND user_id = %s",
                (campaign_id, user_sub),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="campaign not found")
            import json as _json
            brief = row["brief"] if isinstance(row["brief"], dict) else _json.loads(row["brief"])
    finally:
        conn.close()

    from growth_engine.generator.campaign import CampaignGenerator

    async def event_stream():
        gen = CampaignGenerator(brief.get("app_slug", "purangpt"))
        async for event, content in gen.execute(brief):
            import json as _j
            payload = _j.dumps({"type": event, "content": content})
            yield f"data: {payload}\n\n"
            if event == "done":
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Queue (approval) ──────────────────────────────────────────────────────────

@app.get("/queue")
async def get_queue(user_sub: str = Depends(get_user)):
    """List draft-mode posts pending approval."""
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT q.id::text, q.channel, q.mode, q.status, q.scheduled_for::text,
                       a.payload
                FROM ge_post_queue q
                LEFT JOIN ge_content_assets a ON a.id = q.asset_id
                JOIN ge_campaigns c ON c.id = q.campaign_id
                WHERE c.user_id = %s AND q.mode = 'draft' AND q.status = 'pending'
                ORDER BY q.scheduled_for
                """,
                (user_sub,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@app.post("/queue/{queue_id}/approve")
async def approve_queue(queue_id: str, user_sub: str = Depends(get_user)):
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ge_post_queue q SET status='approved', approved_by=%s
                FROM ge_campaigns c
                WHERE q.id = %s AND q.campaign_id = c.id AND c.user_id = %s
                  AND q.mode = 'draft' AND q.status = 'pending'
                """,
                (user_sub, queue_id, user_sub),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="queue item not found")
        conn.commit()
        return {"status": "approved"}
    finally:
        conn.close()


@app.post("/queue/{queue_id}/reject")
async def reject_queue(queue_id: str, user_sub: str = Depends(get_user)):
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ge_post_queue q SET status='rejected'
                FROM ge_campaigns c
                WHERE q.id = %s AND q.campaign_id = c.id AND c.user_id = %s
                  AND q.mode = 'draft' AND q.status = 'pending'
                """,
                (queue_id, user_sub),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="queue item not found")
        conn.commit()
        return {"status": "rejected"}
    finally:
        conn.close()


# ── Channel connections (vault) ───────────────────────────────────────────────

@app.post("/connections", status_code=201)
async def add_connection(body: ConnectionCreate, user_sub: str = Depends(get_user)):
    """Store encrypted channel credentials. Keys never touch the response."""
    connector = CONNECTORS.get(body.channel)
    if not connector:
        raise HTTPException(status_code=422, detail=f"unknown channel: {body.channel}")
    ok = vault.put(
        user_id=user_sub,
        channel=body.channel,
        mode=connector.mode,
        keys=body.keys,
        handle=body.handle,
    )
    if not ok:
        raise HTTPException(status_code=503, detail="vault write failed")
    return {"channel": body.channel, "mode": connector.mode, "status": "active"}


@app.get("/connections")
async def list_connections(user_sub: str = Depends(get_user)):
    return vault.list(user_id=user_sub)


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/analytics")
async def get_analytics(user_sub: str = Depends(get_user), days: int = 7):
    conn = get_db_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.channel,
                       COUNT(*) FILTER (WHERE l.result = 'posted') AS posts,
                       COUNT(*) FILTER (WHERE l.result = 'failed') AS failures,
                       MAX(l.posted_at)::text AS last_posted
                FROM ge_post_log l
                JOIN ge_post_queue q ON q.id = l.queue_id
                JOIN ge_campaigns c ON c.id = q.campaign_id
                WHERE c.user_id = %s
                  AND l.posted_at >= NOW() - (INTERVAL '1 day' * %s)
                GROUP BY l.channel
                ORDER BY l.channel
                """,
                (user_sub, days),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("growth_engine.app:app", host="0.0.0.0", port=8100, reload=True)
