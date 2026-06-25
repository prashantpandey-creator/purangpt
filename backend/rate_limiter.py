"""rate_limiter.py — per-IP sliding-window burst limiter (Redis-backed).

This is the APP-LAYER burst defense, complementary to (not a replacement for) the
per-day quota in db_client.check_rate_limit. The daily quota caps cost-per-user
over a day; this caps requests-per-second so a flood is rejected at the gate,
BEFORE the DB or LLM is touched.

Design notes (why this shape):
- **Redis-backed, not in-memory.** A multi-worker uvicorn deploy would let N
  workers each keep a separate in-memory counter → N× the intended rate slips
  through. A shared Redis sorted-set is the single source of truth across workers.
  Mirrors the graceful-degradation pattern already in query_processor.py.
- **Sliding window, not fixed bucket.** A fixed per-second bucket lets 2× burst
  straddle the boundary (end of one second + start of the next). A sorted-set of
  timestamps trimmed to `now - window` is a true rolling window.
- **Fail-OPEN, not fail-closed.** If Redis is unreachable, the limiter allows the
  request (and logs once). A rate limiter that takes the whole API down when its
  backing store hiccups is a worse outage than the abuse it prevents. The edge
  (Traefik pg-rl) is the durable backstop; this is defense-in-depth.

The limiter is exposed both as an importable check (for tests / direct use) and is
wired as ASGI middleware in main.py.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Reuse the same Redis the expansion cache uses; probe once, degrade gracefully.
_redis = None
try:
    import redis as _redis_sync
    import redis.asyncio as _redis_async

    _REDIS_URL = os.getenv("REDIS_URL", "")
    if _REDIS_URL:
        try:
            _probe = _redis_sync.from_url(_REDIS_URL, socket_connect_timeout=2)
            _probe.ping()
            _probe.close()
            _redis = _redis_async.from_url(_REDIS_URL)
        except Exception as _e:  # noqa: BLE001 — any connection failure → disabled
            logger.warning("Redis unavailable (%s) — burst limiter disabled (fail-open)", _e)
            _redis = None
except ImportError:
    _redis = None


# Default budget: 8 req/s sustained over a 1s window, matching the Traefik edge
# (pg-rl average=8). Per-route overrides are passed explicitly.
DEFAULT_LIMIT = int(os.getenv("BURST_LIMIT", "8"))
DEFAULT_WINDOW_SECONDS = float(os.getenv("BURST_WINDOW", "1"))


async def check_burst(
    key: str,
    limit: int = DEFAULT_LIMIT,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    *,
    now: Optional[float] = None,
) -> tuple[bool, int]:
    """Atomically record one hit for `key` and report whether it's within budget.

    Returns (allowed, remaining). `allowed` is False once `limit` hits have
    occurred within the trailing `window_seconds`. `now` is injectable for tests.

    Fail-open: if Redis is absent/unreachable, returns (True, limit) — never
    blocks on infrastructure failure.
    """
    if _redis is None:
        return True, limit

    t = time.time() if now is None else now
    window_start = t - window_seconds
    redis_key = f"rl:{key}"

    try:
        # One atomic pipeline: drop expired entries, add this hit, count, set TTL.
        pipe = _redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {f"{t}:{id(object())}": t})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, int(window_seconds) + 1)
        results = await pipe.execute()
        count = results[2]
    except Exception as e:  # noqa: BLE001 — Redis error mid-flight → fail open
        logger.warning("burst limiter Redis error (%s) — allowing (fail-open)", e)
        return True, limit

    remaining = max(0, limit - count)
    return count <= limit, remaining


def client_ip_from_scope(headers: dict, fallback: str = "unknown") -> str:
    """Resolve the real client IP for keying.

    Trafik appends the true client IP as the LAST hop of X-Forwarded-For (the
    edge pg-rl uses ipstrategy.depth=1 for the same reason). So we take the
    RIGHTMOST XFF entry, NOT the leftmost (which a client can forge). If no XFF,
    fall back to the direct peer.
    """
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]  # rightmost = appended by our own trusted proxy
    return headers.get("x-real-ip") or fallback
