"""test_rate_limiter.py — verify the burst limiter's deterministic logic.

Run: venv/bin/python -m backend.test_rate_limiter   (must exit 0)

The Redis-dependent path (check_burst with a live store) is an integration
concern; here we test the parts that are pure decision-trees and must be correct
regardless of Redis: the fail-open contract and the IP-resolution logic (which is
the security-critical bit — getting it wrong reintroduces the XFF spoof).
"""
import asyncio
import sys

from backend import rate_limiter
from backend.rate_limiter import check_burst, client_ip_from_scope


def test_fail_open_when_no_redis():
    """With Redis absent, every call must be allowed (never block on infra)."""
    saved = rate_limiter._redis
    rate_limiter._redis = None
    try:
        allowed, remaining = asyncio.run(check_burst("any-key", limit=8))
        assert allowed is True, "must fail OPEN when Redis is down"
        assert remaining == 8
    finally:
        rate_limiter._redis = saved


def test_ip_resolution_takes_rightmost_xff():
    """The real client IP is the RIGHTMOST XFF hop (appended by our proxy).

    Taking the leftmost would trust an attacker-forgeable value — the exact
    vulnerability the depth=1 edge setting closes. This must match.
    """
    # Attacker forges a leftmost entry; our proxy appends the true IP last.
    headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8, 203.0.113.9"}
    assert client_ip_from_scope(headers) == "203.0.113.9", "must take rightmost, not forged leftmost"


def test_ip_resolution_single_value():
    headers = {"x-forwarded-for": "203.0.113.9"}
    assert client_ip_from_scope(headers) == "203.0.113.9"


def test_ip_resolution_falls_back_to_real_ip():
    headers = {"x-real-ip": "198.51.100.2"}
    assert client_ip_from_scope(headers) == "198.51.100.2"


def test_ip_resolution_fallback_when_no_headers():
    assert client_ip_from_scope({}, fallback="peer") == "peer"


def test_ip_resolution_ignores_empty_xff():
    headers = {"x-forwarded-for": "  ,  ", "x-real-ip": "198.51.100.3"}
    assert client_ip_from_scope(headers) == "198.51.100.3"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"  ✓ {t.__name__}")
    print(f"\n{passed}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
