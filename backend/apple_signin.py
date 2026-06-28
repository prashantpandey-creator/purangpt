"""
Sign in with Apple — NATIVE flow verification + first-party session minting.

The iOS app obtains an Apple identity token via the native ASAuthorization
system sheet (Face ID). For the native flow the token's audience is the app's
**bundle id** (`com.fcpuru95.purangpt`), NOT a Services ID — so we need NO
"Sign in with Apple" key and NO Services ID. We verify the token against
Apple's PUBLIC JWKS, then mint our OWN session JWT (HS256) which the app sends
as the Bearer afterwards. This decouples our session lifetime from Apple's
~10-minute identity-token expiry and means `get_current_user` keeps verifying a
single Bearer for everyone (see auth.py).

Flow:
    iOS  --(identity_token, raw nonce)-->  POST /api/auth/apple
    here:  verify_apple_identity_token()  ->  create_profile_if_not_exists()
           mint_session_token()           ->  { token, expires_in, profile }
    iOS  --(Bearer = our session token)-->  /api/chat etc.
           auth.get_current_user() -> verify_session_token()
"""
from __future__ import annotations

import os
import json
import time
import hashlib
import logging

import requests
import jwt
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger(__name__)

# Native Sign in with Apple uses the app's bundle id as the token audience.
BUNDLE_ID = os.getenv("APPLE_BUNDLE_ID", "com.fcpuru95.purangpt")
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"

# Our first-party session token (the Bearer the app actually carries afterwards).
SESSION_ISSUER = "purangpt"
SESSION_TTL = int(os.getenv("SESSION_JWT_TTL", str(30 * 24 * 3600)))  # 30 days


def _session_secret() -> str:
    """HMAC secret for our session JWTs. Reuses FERNET_KEY (always set in prod)
    so we add NO new required deploy secret; overridable via SESSION_JWT_SECRET."""
    s = os.getenv("SESSION_JWT_SECRET") or os.getenv("FERNET_KEY")
    if not s:
        # Local dev only: stable within a process, not across restarts.
        logger.warning("[apple_signin] no SESSION_JWT_SECRET/FERNET_KEY — using ephemeral dev secret")
        s = "dev-insecure-secret-do-not-ship"
    return s


# ── Apple JWKS cache (TTL, mirrors auth.py's pattern) ────────────────────────
_jwks_cache = None
_jwks_at = 0.0
_JWKS_TTL = 3600.0


def _load_apple_keys(force: bool = False):
    """Return Apple's JWKS dict, refetching when forced or the TTL expired.
    Falls back to a stale cache rather than failing if a refetch errors."""
    global _jwks_cache, _jwks_at
    fresh = _jwks_cache is not None and (time.time() - _jwks_at) < _JWKS_TTL
    if fresh and not force:
        return _jwks_cache
    try:
        r = requests.get(APPLE_KEYS_URL, timeout=5)
        r.raise_for_status()
        _jwks_cache = r.json()
        _jwks_at = time.time()
    except Exception as e:
        logger.error("[apple_signin] JWKS fetch failed: %s", e)
    return _jwks_cache


def _key_for_kid(jwks, kid):
    for k in (jwks or {}).get("keys", []):
        if k.get("kid") == kid:
            return RSAAlgorithm.from_jwk(json.dumps(k))
    return None


def verify_apple_identity_token(identity_token, nonce=None, keys=None):
    """Verify a native Sign-in-with-Apple identity token.

    Returns {'sub', 'email', 'email_verified'} on success, else None.
    `keys` injects a JWKS dict for tests (bypasses the network fetch).
    `nonce` is the RAW nonce the app generated; Apple stores SHA256(raw) in the
    token, so we compare hashes to defeat replay.
    """
    if not identity_token:
        return None
    try:
        header = jwt.get_unverified_header(identity_token)
    except Exception:
        return None
    kid = header.get("kid")

    jwks = keys if keys is not None else _load_apple_keys()
    pub = _key_for_kid(jwks, kid)
    # Unknown kid usually means Apple rotated keys since we cached — force once.
    if pub is None and keys is None:
        jwks = _load_apple_keys(force=True)
        pub = _key_for_kid(jwks, kid)
    if pub is None:
        logger.info("[apple_signin] no signing key for kid=%s", kid)
        return None

    try:
        claims = jwt.decode(
            identity_token,
            pub,
            algorithms=["RS256"],
            audience=BUNDLE_ID,
            issuer=APPLE_ISSUER,
        )
    except Exception as e:
        logger.info("[apple_signin] identity token rejected: %s", e)
        return None

    if nonce is not None:
        expected = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        if claims.get("nonce") != expected:
            logger.info("[apple_signin] nonce mismatch")
            return None

    sub = claims.get("sub")
    if not sub:
        return None
    ev = claims.get("email_verified")
    return {
        "sub": sub,
        "email": claims.get("email"),
        "email_verified": (ev is True or ev == "true"),
    }


def mint_session_token(sub, email, role="free"):
    """Mint our own Bearer session JWT (HS256) after a successful Apple verify."""
    now = int(time.time())
    payload = {
        "iss": SESSION_ISSUER,
        "sub": sub,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + SESSION_TTL,
    }
    return jwt.encode(payload, _session_secret(), algorithm="HS256")


def verify_session_token(token):
    """Verify a first-party session JWT. Returns its claims or None.

    Safe to call on ANY Bearer: a Logto RS256 token fails the HS256/issuer check
    and returns None, so callers fall through to Logto verification cleanly."""
    if not token or token.count(".") != 2:
        return None
    try:
        claims = jwt.decode(
            token,
            _session_secret(),
            algorithms=["HS256"],
            issuer=SESSION_ISSUER,
        )
    except Exception:
        return None
    if not claims.get("sub"):
        return None
    return claims


def session_ttl():
    return SESSION_TTL
