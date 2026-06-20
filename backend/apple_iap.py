"""
Apple StoreKit 2 JWS verification.

StoreKit 2 hands the app a `JWSTransaction` — a JWT signed by Apple with ES256.
The signing certificate chain is embedded in the JWT header's `x5c` field. We
verify the chain terminates at Apple's root CA, then trust the decoded payload.

This is fully self-contained (no network call to Apple) and is the fast path for
granting Pro the instant a purchase completes. App Store Server Notifications V2
remain the authoritative channel for renewals/cancellations (handled separately).
"""
import base64
import logging
from datetime import datetime, timezone
from typing import Optional

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

logger = logging.getLogger(__name__)

BUNDLE_ID = "com.fcpuru95.purangpt"
PRO_PRODUCT_IDS = {"purangpt_pro_monthly", "purangpt_pro_annual"}

# Apple Root CA - G3 (the root for StoreKit JWS cert chains).
# https://www.apple.com/certificateauthority/AppleRootCA-G3.cer (DER, base64).
APPLE_ROOT_CA_G3_B64 = (
    "MIICQzCCAcmgAwIBAgIILcX8iNLFS5UwCgYIKoZIzj0EAwMwZzEbMBkGA1UEAwwS"
    "QXBwbGUgUm9vdCBDQSAtIEczMSYwJAYDVQQLDB1BcHBsZSBDZXJ0aWZpY2F0aW9u"
    "IEF1dGhvcml0eTETMBEGA1UECgwKQXBwbGUgSW5jLjELMAkGA1UEBhMCVVMwHhcN"
    "MTQwNDMwMTgxOTA2WhcNMzkwNDMwMTgxOTA2WjBnMRswGQYDVQQDDBJBcHBsZSBS"
    "b290IENBIC0gRzMxJjAkBgNVBAsMHUFwcGxlIENlcnRpZmljYXRpb24gQXV0aG9y"
    "aXR5MRMwEQYDVQQKDApBcHBsZSBJbmMuMQswCQYDVQQGEwJVUzB2MBAGByqGSM49"
    "AgEGBSuBBAAiA2IABJjpLz1AcqTtkyJygRMc3RCV8cWjTnHcFBbZDuWmBSp3ZHtf"
    "TjjTuxxEtX/1H7YyYl3J6YRbTzBPEVoA/VhYDKX1DyxNB0cTddqXl5dvMVztK517"
    "IDvYuVTZXpmkOlEKMaNCMEAwHQYDVR0OBBYEFLuw3qFYM4iapIqZ3r6966/ayySr"
    "MA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMAoGCCqGSM49BAMDA2gA"
    "MGUCMQCD6cHEFl4aXTQY2e3v9GwOAEZLuN+yRhHFD/3meoyhpmvOwgPUnPWTxnS4"
    "at+qIxUCMG1mihDK1A3UT82NQz60imOlM27jbdoXt2QfyFMm+YhidDkLF1vLUagM"
    "6BgD56KyKA=="
)


def _b64url_decode(data: str) -> bytes:
    padding_len = -len(data) % 4
    return base64.urlsafe_b64decode(data + "=" * padding_len)


def _load_cert_from_x5c(b64_der: str) -> x509.Certificate:
    return x509.load_der_x509_certificate(base64.b64decode(b64_der))


def _verify_chain(certs: list[x509.Certificate]) -> bool:
    """Verify leaf → intermediate → root, with root pinned to Apple Root CA G3."""
    if len(certs) < 2:
        logger.warning("[apple_iap] cert chain too short")
        return False

    apple_root = x509.load_der_x509_certificate(base64.b64decode(APPLE_ROOT_CA_G3_B64))

    # The last cert in x5c should match Apple's root (compare public bytes).
    chain_root_pub = certs[-1].public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    )
    root_pub = apple_root.public_key().public_bytes(
        Encoding.DER, PublicFormat.SubjectPublicKeyInfo
    )
    if chain_root_pub != root_pub:
        logger.warning("[apple_iap] chain root does not match Apple Root CA G3")
        return False

    # Verify each cert is signed by the next one up the chain.
    for i in range(len(certs) - 1):
        child, issuer = certs[i], certs[i + 1]
        issuer_key = issuer.public_key()
        try:
            if isinstance(issuer_key, ec.EllipticCurvePublicKey):
                issuer_key.verify(
                    child.signature,
                    child.tbs_certificate_bytes,
                    ec.ECDSA(child.signature_hash_algorithm),
                )
            else:
                issuer_key.verify(
                    child.signature,
                    child.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    child.signature_hash_algorithm,
                )
        except Exception as e:
            logger.warning(f"[apple_iap] chain link {i} failed verification: {e}")
            return False

    # Expiry check on leaf.
    now = datetime.now(timezone.utc)
    leaf = certs[0]
    if leaf.not_valid_after_utc < now or leaf.not_valid_before_utc > now:
        logger.warning("[apple_iap] leaf certificate is expired or not yet valid")
        return False

    return True


def _decode_verified_jws(signed_jws: str) -> Optional[dict]:
    """
    Verify the ES256 signature + Apple cert chain of any StoreKit/ASSN JWS and
    return its decoded payload. Does NOT apply transaction-specific field checks
    (bundle/product/expiry) — callers do that. Returns None on any failure.
    """
    try:
        header = jwt.get_unverified_header(signed_jws)
        x5c = header.get("x5c")
        if not x5c:
            logger.warning("[apple_iap] no x5c in JWS header")
            return None

        certs = [_load_cert_from_x5c(c) for c in x5c]
        if not _verify_chain(certs):
            return None

        leaf_pub = certs[0].public_key()
        return jwt.decode(
            signed_jws,
            key=leaf_pub,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
    except Exception as e:
        logger.error(f"[apple_iap] JWS decode failed: {e}")
        return None


def verify_transaction_jws(signed_jws: str) -> Optional[dict]:
    """
    Verify a StoreKit 2 JWSTransaction. Returns the decoded transaction payload
    if the signature, cert chain, bundle id, and product are all valid; else None.
    """
    try:
        payload = _decode_verified_jws(signed_jws)
        if payload is None:
            return None

        if payload.get("bundleId") != BUNDLE_ID:
            logger.warning(f"[apple_iap] bundleId mismatch: {payload.get('bundleId')}")
            return None

        product_id = payload.get("productId")
        if product_id not in PRO_PRODUCT_IDS:
            logger.warning(f"[apple_iap] unexpected productId: {product_id}")
            return None

        # Reject revoked / expired.
        if payload.get("revocationDate"):
            logger.info("[apple_iap] transaction is revoked")
            return None
        expires_ms = payload.get("expiresDate")
        if expires_ms:
            expires = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc)
            if expires < datetime.now(timezone.utc):
                logger.info("[apple_iap] transaction is expired")
                return None

        return payload
    except Exception as e:
        logger.error(f"[apple_iap] JWS verification failed: {e}")
        return None


def plan_for_product(product_id: str) -> str:
    return "pro" if product_id in PRO_PRODUCT_IDS else "free"


def period_days_for_product(product_id: str) -> int:
    return 365 if "annual" in product_id else 30


# Notification types that mean the user currently HAS Pro.
ACTIVE_NOTIFICATION_TYPES = {
    "SUBSCRIBED",
    "DID_RENEW",
    "OFFER_REDEEMED",
    "DID_CHANGE_RENEWAL_STATUS",  # may be re-enable; check transaction expiry
}
# Notification types that mean Pro should be revoked immediately.
REVOKE_NOTIFICATION_TYPES = {
    "EXPIRED",
    "REFUND",
    "REVOKE",
    "GRACE_PERIOD_EXPIRED",
}


def decode_server_notification(signed_payload: str) -> Optional[dict]:
    """
    Decode an App Store Server Notification V2 (`signedPayload`).

    Returns a normalized dict:
      { notificationType, subtype, original_transaction_id, product_id,
        plan, expires_date (datetime|None), is_active (bool) }
    or None if the outer payload or nested transaction fails verification.
    """
    outer = _decode_verified_jws(signed_payload)
    if outer is None:
        return None

    notification_type = outer.get("notificationType")
    subtype = outer.get("subtype")

    data = outer.get("data") or {}
    if data.get("bundleId") and data["bundleId"] != BUNDLE_ID:
        logger.warning(f"[apple_iap] ASSN bundleId mismatch: {data.get('bundleId')}")
        return None

    signed_tx = data.get("signedTransactionInfo")
    if not signed_tx:
        logger.warning("[apple_iap] ASSN missing signedTransactionInfo")
        return None

    tx = _decode_verified_jws(signed_tx)
    if tx is None:
        return None

    product_id = tx.get("productId")
    expires_ms = tx.get("expiresDate")
    expires_dt = (
        datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc) if expires_ms else None
    )

    is_active = notification_type in ACTIVE_NOTIFICATION_TYPES
    if notification_type in REVOKE_NOTIFICATION_TYPES:
        is_active = False
    if tx.get("revocationDate"):
        is_active = False
    if expires_dt and expires_dt < datetime.now(timezone.utc):
        is_active = False

    return {
        "notificationType": notification_type,
        "subtype": subtype,
        "original_transaction_id": str(
            tx.get("originalTransactionId") or tx.get("transactionId") or ""
        ),
        "product_id": product_id,
        "plan": plan_for_product(product_id) if product_id in PRO_PRODUCT_IDS else "free",
        "expires_date": expires_dt,
        "is_active": is_active,
    }
