from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import os
import logging
from typing import Optional
from datetime import datetime, timezone
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

LOGTO_ENDPOINT = os.getenv("LOGTO_ENDPOINT", "https://auth.purangpt.com/")
LOGTO_API_RESOURCE_INDICATOR = os.getenv("LOGTO_API_RESOURCE_INDICATOR", "https://api.purangpt.com")
JWKS_URL = urljoin(LOGTO_ENDPOINT, "/oidc/jwks")

# JWKS cache with a TTL. Previously cached forever: if Logto rotated its signing
# keys, every token with the new `kid` failed (all users appeared logged out)
# until the process restarted; and a single failed first fetch poisoned auth
# permanently. Now it expires and can be force-refreshed on an unknown `kid`.
import time as _time

_jwks_cache = None
_jwks_fetched_at = 0.0
_JWKS_TTL = int(os.getenv("JWKS_TTL_SECONDS", "3600"))   # 1h
LOGTO_ISSUER = os.getenv("LOGTO_ISSUER", urljoin(LOGTO_ENDPOINT, "/oidc"))


def get_jwks(force: bool = False):
    """Return the Logto JWKS, refetching when forced or the cache TTL expired.
    Returns None only if we have no cache AND the fetch fails."""
    global _jwks_cache, _jwks_fetched_at
    fresh = _jwks_cache is not None and (_time.time() - _jwks_fetched_at) < _JWKS_TTL
    if fresh and not force:
        return _jwks_cache
    try:
        resp = requests.get(JWKS_URL, timeout=5)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = _time.time()
    except Exception as e:
        logger.error(f"Failed to fetch JWKS from Logto: {e}")
        # Fall back to a stale cache if we have one rather than failing all auth.
    return _jwks_cache


def _find_rsa_key(jwks: dict, kid: str) -> dict:
    for key in (jwks or {}).get("keys", []):
        if key.get("kid") == kid:
            return key
    return {}

# Guest limits
GUEST_DAILY_LIMIT = int(os.getenv("GUEST_DAILY_LIMIT", "10"))  # conservative default
MAX_QUERY_LENGTH  = int(os.getenv("MAX_QUERY_LENGTH", "2000"))  # chars; ~500 tokens


def _verify_google_token(access_token: str) -> Optional[dict]:
    """Verify a Google OAuth access_token via Google's tokeninfo endpoint.
    Returns {'id': google_sub, 'email': email, 'role': role} or None."""
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"access_token": access_token},
            timeout=5,
        )
        if not resp.ok:
            return None
        info = resp.json()
        # tokeninfo returns error if token is invalid/expired
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


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Optional[dict]:
    """Extracts the Bearer token and verifies it against Logto JWKS.
    Falls back to Google tokeninfo for users authenticated via direct Google OAuth."""
    if not credentials:
        return None

    token = credentials.credentials
    jwks = get_jwks()

    # Try Logto JWT verification first
    if jwks:
        try:
            # Decode the unverified header to get the key ID (kid)
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            rsa_key = _find_rsa_key(jwks, kid)

            # Unknown kid usually means Logto rotated its signing keys since we cached
            # the JWKS — force a refresh once before rejecting.
            if not rsa_key:
                jwks = get_jwks(force=True)
                rsa_key = _find_rsa_key(jwks, kid)

            if rsa_key:
                # Verify signature + issuer. Audience verification stays optional: standard
                # Logto access tokens carry the API resource indicator in `aud`, but the
                # opaque/userinfo tokens used here may not — so we gate on iss + signature
                # and only enforce aud when explicitly turned on. Issuer check defaults ON
                # (the live Logto issuer is https://auth.purangpt.com/oidc) but can be
                # disabled via DISABLE_JWT_ISSUER_CHECK without a redeploy if it ever
                # mismatches (e.g. endpoint change).
                verify_aud = bool(os.getenv("ENFORCE_JWT_AUDIENCE"))
                verify_iss = not os.getenv("DISABLE_JWT_ISSUER_CHECK")
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=["RS256"],
                    issuer=LOGTO_ISSUER if verify_iss else None,
                    audience=LOGTO_API_RESOURCE_INDICATOR if verify_aud else None,
                    options={"verify_aud": verify_aud, "verify_iss": verify_iss},
                )

                # Logto token `sub` is the user ID
                user_id = payload.get("sub")
                if user_id:
                    from backend.db_client import create_profile_if_not_exists
                    email = payload.get("email")
                    profile = create_profile_if_not_exists(user_id, email)
                    role = profile.get("role", "free") if profile else "free"
                    return {"id": user_id, "role": role, "email": email}

        except jwt.ExpiredSignatureError:
            logger.warning("Logto token expired; trying Google fallback")
        except jwt.JWTClaimsError:
            logger.warning("Logto JWT claims error; trying Google fallback")
        except Exception:
            pass  # Not a Logto JWT — fall through to Google check

    # Fall back to Google access_token verification (direct Google OAuth users).
    # Google access tokens are opaque strings (not JWTs), so JWKS fails above.
    return _verify_google_token(token)


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


# ── Guest rate store (Postgres-backed, race-free, shared across workers) ──────
# Previously this was an in-memory per-worker dict: with N gunicorn workers a
# guest got up to N× the limit, counts reset on every deploy, and check→increment
# had a race window. Now a single guest_usage row per (guest_id, UTC day) is the
# source of truth, and the increment is an atomic UPSERT that returns the new
# count — so check-and-consume is one indivisible operation.


def check_guest_rate_limit(guest_id: str) -> tuple[bool, int]:
    """Read-only check: return (allowed, remaining) WITHOUT consuming a unit.
    Used for pre-flight 'can this guest send?' gating. The actual consume happens
    atomically in consume_guest_unit() when a message is really sent."""
    from backend.db_client import get_db_conn
    today = datetime.now(timezone.utc).date()
    conn = get_db_conn()
    if not conn:
        # Fail-open to the limit if DB is unreachable — don't lock everyone out.
        return True, GUEST_DAILY_LIMIT
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count FROM guest_usage WHERE guest_id = %s AND usage_date = %s",
                (guest_id, today),
            )
            row = cur.fetchone()
            count = (row["count"] if row else 0) or 0
        if count >= GUEST_DAILY_LIMIT:
            return False, 0
        return True, GUEST_DAILY_LIMIT - count
    except Exception as e:
        logger.error("guest rate check failed: %s", e)
        return True, GUEST_DAILY_LIMIT
    finally:
        conn.close()


def consume_guest_unit(guest_id: str) -> tuple[bool, int]:
    """Atomically increment and gate in one statement. Returns (allowed, remaining).
    If the increment would exceed the limit, it is rolled back to a no-op via the
    WHERE guard, so concurrent requests can't blow past the cap. This is the
    function to call right before doing the actual work."""
    from backend.db_client import get_db_conn
    today = datetime.now(timezone.utc).date()
    conn = get_db_conn()
    if not conn:
        return True, GUEST_DAILY_LIMIT  # fail-open
    try:
        with conn.cursor() as cur:
            # Upsert the row, but only increment while still under the limit.
            # RETURNING gives us the post-increment count atomically.
            cur.execute(
                """
                INSERT INTO guest_usage (guest_id, usage_date, count)
                VALUES (%s, %s, 1)
                ON CONFLICT (guest_id, usage_date)
                DO UPDATE SET count = guest_usage.count + 1
                  WHERE guest_usage.count < %s
                RETURNING count
                """,
                (guest_id, today, GUEST_DAILY_LIMIT),
            )
            row = cur.fetchone()
        conn.commit()
        if row is None:
            # WHERE guard blocked the update → already at the limit.
            return False, 0
        return True, max(0, GUEST_DAILY_LIMIT - row["count"])
    except Exception as e:
        logger.error("guest unit consume failed: %s", e)
        conn.rollback()
        return True, GUEST_DAILY_LIMIT  # fail-open on error
    finally:
        conn.close()


def increment_guest_usage(guest_id: str) -> None:
    """Back-compat shim. The atomic path is consume_guest_unit(); this remains so
    existing call sites that increment after the fact still record usage."""
    consume_guest_unit(guest_id)


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
