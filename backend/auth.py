from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import os
import logging
from typing import Optional
from datetime import datetime, timezone

from backend.supabase_client import get_profile, get_supabase

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Guest limits
GUEST_DAILY_LIMIT = int(os.getenv("GUEST_DAILY_LIMIT", "10"))  # conservative default
MAX_QUERY_LENGTH  = int(os.getenv("MAX_QUERY_LENGTH", "2000"))  # chars; ~500 tokens


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[dict]:
    """Extracts the Bearer token and fetches the user profile."""
    if not credentials:
        return None

    token = credentials.credentials
    supabase = get_supabase()
    if not supabase:
        return None

    try:
        user_resp = supabase.auth.get_user(token)
        if not user_resp or not user_resp.user:
            return None

        user_id = user_resp.user.id
        profile = get_profile(user_id)
        if profile:
            return profile
        # Fallback if profile row doesn't exist yet (before DB trigger runs)
        return {"id": user_id, "role": "free"}
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        return None


def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """Dependency that requires a valid authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(allowed_roles: list):
    """Dependency factory to require specific roles."""
    def role_checker(user: dict = Depends(require_auth)):
        if user.get("role") not in allowed_roles and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker


def get_client_ip(request: Request) -> str:
    """
    Resolve the real client IP, respecting X-Forwarded-For from a trusted proxy.
    IP is the authoritative rate-limit key for guests — unlike X-Device-ID it
    cannot be trivially rotated per-request.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first (leftmost) IP — that's the original client
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip
    return request.client.host or "unknown"


def get_guest_id(request: Request) -> str:
    """
    Build a composite guest identifier: IP + optional Device-ID fingerprint.
    Using IP as the primary axis makes rotation much harder than Device-ID alone.
    Device-ID is kept as a secondary signal so the same IP on different browsers
    still gets separate counters (better UX, slightly stricter abuse prevention).
    """
    ip = get_client_ip(request)
    device_id = request.headers.get("X-Device-ID", "")[:64]  # cap length
    # Combine them — attacker needs to change both simultaneously
    return f"{ip}|{device_id}" if device_id else ip


# ── In-memory guest rate store ─────────────────────────────────────────────
# Capped at 50,000 entries to prevent unbounded memory growth.
# On restart the counts reset — acceptable for a soft per-day limit.
_guest_usage: dict = {}
_MAX_STORE_SIZE = 50_000


def _evict_old_entries(today: str) -> None:
    """Remove yesterday's entries when the store gets large."""
    if len(_guest_usage) < _MAX_STORE_SIZE:
        return
    stale = [k for k, v in _guest_usage.items() if v["date"] != today]
    for k in stale:
        del _guest_usage[k]


def check_guest_rate_limit(guest_id: str) -> tuple[bool, int]:
    """Return (allowed, remaining) for a guest identifier."""
    now   = datetime.now(timezone.utc)
    today = now.date().isoformat()

    _evict_old_entries(today)

    entry = _guest_usage.get(guest_id)
    if entry is None or entry["date"] != today:
        _guest_usage[guest_id] = {"date": today, "count": 0}
        entry = _guest_usage[guest_id]

    count = entry["count"]
    if count >= GUEST_DAILY_LIMIT:
        return False, 0
    return True, GUEST_DAILY_LIMIT - count


def increment_guest_usage(guest_id: str) -> None:
    if guest_id in _guest_usage:
        _guest_usage[guest_id]["count"] += 1


def validate_query(query: str) -> None:
    """
    Raise 400 if the query is empty or exceeds the configured max length.
    Prevents prompt-injection via huge payloads that burn API credits.
    """
    stripped = query.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(stripped) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long ({len(stripped)} chars). Maximum is {MAX_QUERY_LENGTH}.",
        )
