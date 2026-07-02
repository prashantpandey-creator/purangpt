"""
PuranGPT Authentication — Google OAuth only.

No Logto. No JWKS fetch. No email/password. Google OAuth is the single
auth provider for web. Apple Session Token for native iOS Sign in with Apple.
"""

from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Guest limits
GUEST_DAILY_LIMIT = int(os.getenv("GUEST_DAILY_LIMIT", "50"))
MAX_QUERY_LENGTH  = int(os.getenv("MAX_QUERY_LENGTH", "2000"))


def _verify_google_token(access_token: str) -> Optional[dict]:
    """Verify a Google OAuth access_token via Google's tokeninfo endpoint."""
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"access_token": access_token},
            timeout=5,
        )
        if not resp.ok:
            return None
        info = resp.json()
        if "error" in info or not info.get("sub"):
            return None
        user_id = info["sub"]
        email = info.get("email")
        from backend.db_client import create_profile_if_not_exists
        profile = create_profile_if_not_exists(user_id, email)
        role = profile.get("role", "free") if profile else "free"
        return {"id": user_id, "role": role, "email": email}
    except Exception as e:
        logger.error(f"Google token verification failed: {e}")
        return None


def _verify_x_token(access_token: str) -> Optional[dict]:
    """Verify an X (Twitter) OAuth 2.0 access token via X's /users/me endpoint."""
    try:
        resp = requests.get(
            "https://api.x.com/2/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        if not resp.ok:
            return None
        data = resp.json().get("data", {})
        x_id = data.get("id")
        if not x_id:
            return None
        user_id = f"x:{x_id}"
        email = None  # X OAuth 2.0 doesn't expose email
        from backend.db_client import create_profile_if_not_exists
        profile = create_profile_if_not_exists(user_id, email)
        role = profile.get("role", "free") if profile else "free"
        return {"id": user_id, "role": role, "email": email,
                "name": data.get("name"), "username": data.get("username")}
    except Exception as e:
        logger.error(f"X token verification failed: {e}")
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[dict]:
    """Verify Bearer token. Google OAuth, X OAuth, or Apple Session (iOS)."""

    if not credentials:
        return None

    token = credentials.credentials

    # Apple session token (iOS native) — cheap HS256, checked first
    try:
        from backend.apple_signin import verify_session_token
        _sess = verify_session_token(token)
        if _sess:
            return {"id": _sess.get("sub"), "role": _sess.get("role", "free"),
                    "email": _sess.get("email")}
    except Exception:
        pass

    # Google OAuth — default web provider
    user = _verify_google_token(token)
    if user:
        return user

    # X (Twitter) OAuth 2.0 — secondary web provider
    return _verify_x_token(token)


def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(allowed_roles: list):
    def role_checker(user: dict = Depends(require_auth)):
        if user.get("role") not in allowed_roles and user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker


def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("X-Forwarded-For", "")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("X-Real-IP", "")
    if x_real_ip:
        return x_real_ip.strip()
    return request.client.host if request.client else "unknown"


def get_guest_id(request: Request) -> str:
    device_id = request.headers.get("X-Device-ID", "")
    if device_id:
        return f"guest-{device_id}"
    return f"guest-{get_client_ip(request)}"


def validate_query(query: str) -> None:
    stripped = query.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(stripped) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long ({len(stripped)} chars). Maximum is {MAX_QUERY_LENGTH}.",
        )


# ── Guest rate limiting ────────────────────────────────────────────────────
# Kept simple — in-memory counter per guest, resets at midnight UTC.

from datetime import datetime, timezone
from collections import defaultdict

_guest_usage: dict = defaultdict(lambda: {"count": 0, "date": ""})


def check_guest_rate_limit(guest_id: str):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = _guest_usage[guest_id]
    if entry["date"] != today:
        entry["count"] = 0
        entry["date"] = today
    remaining = GUEST_DAILY_LIMIT - entry["count"]
    return entry["count"] < GUEST_DAILY_LIMIT, max(0, remaining)


def consume_guest_unit(guest_id: str):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = _guest_usage[guest_id]
    if entry["date"] != today:
        entry["count"] = 0
        entry["date"] = today
    entry["count"] += 1
    return True, max(0, GUEST_DAILY_LIMIT - entry["count"])


def increment_guest_usage(guest_id: str, tokens: int = 1):
    """Increment guest token usage (for token-based billing, future use)."""
    pass  # Reserved for future token-based guest limits
