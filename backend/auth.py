from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import os
import logging
from typing import Optional

from backend.supabase_client import get_profile

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
# Usually the JWT secret is in the dashboard. For now, we can use the Supabase python SDK 
# which can fetch the user, but doing JWT verification locally is faster.
# Since we don't have the JWT secret yet, let's use the Supabase client to fetch the user.
from backend.supabase_client import get_supabase

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[dict]:
    """Extracts the Bearer token and fetches the user profile."""
    if not credentials:
        return None
        
    token = credentials.credentials
    supabase = get_supabase()
    if not supabase:
        return None
        
    try:
        # Use the Supabase client to get the user from the JWT
        user_resp = supabase.auth.get_user(token)
        if not user_resp or not user_resp.user:
            return None
            
        user_id = user_resp.user.id
        # Fetch the profile to get role and limits
        profile = get_profile(user_id)
        if profile:
            return profile
        else:
            # Fallback if profile doesn't exist yet (before trigger runs)
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

def get_guest_id(request: Request) -> str:
    """Extract client Device ID for guest rate limiting."""
    device_id = request.headers.get("X-Device-ID")
    if device_id:
        return device_id
    # Fallback to IP if no device ID
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host

# Simple in-memory rate limiting for guests
_guest_usage = {}
from datetime import datetime, timezone

def check_guest_rate_limit(guest_id: str) -> tuple[bool, int]:
    """Check if guest has exceeded 10 messages/day."""
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    
    if guest_id not in _guest_usage:
        _guest_usage[guest_id] = {"date": today, "count": 0}
        
    # Reset if new day
    if _guest_usage[guest_id]["date"] != today:
        _guest_usage[guest_id] = {"date": today, "count": 0}
        
    count = _guest_usage[guest_id]["count"]
    if count >= 10:
        return False, 0
    return True, 10 - count

def increment_guest_usage(guest_id: str):
    if guest_id in _guest_usage:
        _guest_usage[guest_id]["count"] += 1
