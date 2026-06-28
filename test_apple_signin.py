"""Crypto tests for backend.apple_signin (Sign in with Apple, native flow).

Run:  venv/bin/python test_apple_signin.py     (must print ALL PASS and exit 0)

Self-contained: a locally-generated RSA keypair stands in for Apple's signing
key, and the JWK is injected directly — so NO network call to Apple is made.
This is the real-fixture-in / verdict-out shape: it catches the failures that a
pristine envelope hides (wrong audience, wrong issuer, expired, replayed nonce,
tampered session token).
"""
from __future__ import annotations

import json
import time
import hashlib
import sys

import jwt
from jwt.algorithms import RSAAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from backend.apple_signin import (
    verify_apple_identity_token,
    mint_session_token,
    verify_session_token,
    BUNDLE_ID,
    APPLE_ISSUER,
)

# --- a fake "Apple" signing key + the JWKS we inject ---
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIV_PEM = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
_PUB_JWK = json.loads(RSAAlgorithm.to_jwk(_key.public_key()))
_KID = "testkid-1"
_PUB_JWK.update({"kid": _KID, "alg": "RS256", "use": "sig"})
_JWKS = {"keys": [_PUB_JWK]}


def _mint_apple(sub="001999.deadbeef", email="seeker@privaterelay.appleid.com",
                aud=BUNDLE_ID, iss=APPLE_ISSUER, exp_delta=600, nonce_hash=None):
    now = int(time.time())
    payload = {"iss": iss, "aud": aud, "sub": sub, "email": email,
               "email_verified": "true", "iat": now, "exp": now + exp_delta}
    if nonce_hash is not None:
        payload["nonce"] = nonce_hash
    return jwt.encode(payload, _PRIV_PEM, algorithm="RS256", headers={"kid": _KID})


def test_valid():
    r = verify_apple_identity_token(_mint_apple(), keys=_JWKS)
    assert r is not None, "valid token should verify"
    assert r["sub"] == "001999.deadbeef", r
    assert r["email"] == "seeker@privaterelay.appleid.com", r
    assert r["email_verified"] is True, r
    print("ok  valid token verifies")


def test_bad_audience():
    tok = _mint_apple(aud="com.someone.else")
    assert verify_apple_identity_token(tok, keys=_JWKS) is None, "wrong aud must reject"
    print("ok  wrong audience rejected")


def test_bad_issuer():
    tok = _mint_apple(iss="https://evil.example.com")
    assert verify_apple_identity_token(tok, keys=_JWKS) is None, "wrong iss must reject"
    print("ok  wrong issuer rejected")


def test_expired():
    tok = _mint_apple(exp_delta=-30)
    assert verify_apple_identity_token(tok, keys=_JWKS) is None, "expired must reject"
    print("ok  expired token rejected")


def test_nonce():
    raw = "9f8c-random-nonce"
    h = hashlib.sha256(raw.encode()).hexdigest()
    tok = _mint_apple(nonce_hash=h)
    assert verify_apple_identity_token(tok, nonce=raw, keys=_JWKS) is not None, "matching nonce ok"
    assert verify_apple_identity_token(tok, nonce="wrong", keys=_JWKS) is None, "nonce mismatch rejects"
    print("ok  nonce match / mismatch")


def test_unknown_kid():
    # A token signed by a key whose kid is not in the injected JWKS → None.
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    now = int(time.time())
    tok = jwt.encode({"iss": APPLE_ISSUER, "aud": BUNDLE_ID, "sub": "x",
                      "iat": now, "exp": now + 600},
                     other_pem, algorithm="RS256", headers={"kid": "unknown-kid"})
    assert verify_apple_identity_token(tok, keys=_JWKS) is None, "unknown kid rejects"
    print("ok  unknown kid rejected")


def test_session_roundtrip():
    t = mint_session_token("001999.deadbeef", "a@b.com", "pro")
    c = verify_session_token(t)
    assert c is not None and c["sub"] == "001999.deadbeef", c
    assert c["role"] == "pro" and c["email"] == "a@b.com", c
    # tampering breaks the signature
    assert verify_session_token(t + "x") is None, "tampered session token must reject"
    # garbage / non-session tokens return None (so Logto fall-through is clean)
    assert verify_session_token("not.a.jwt") is None
    assert verify_session_token("") is None
    # an "Apple" RS256 token is NOT a valid session token
    assert verify_session_token(_mint_apple()) is None, "RS256 token is not an HS256 session"
    print("ok  session mint/verify roundtrip + rejects foreign tokens")


if __name__ == "__main__":
    try:
        test_valid()
        test_bad_audience()
        test_bad_issuer()
        test_expired()
        test_nonce()
        test_unknown_kid()
        test_session_roundtrip()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
    print("ALL PASS")
