"""Smoke test for monitor.check — verifies envelope shape and offline behaviour."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.monitor.check import run, _envelope, _now, _hours_ago


def test_envelope_shape():
    env = _envelope(True, {"test": 1}, {"ms": 5}, [])
    assert env["success"] is True
    assert env["data"] == {"test": 1}
    assert env["metadata"] == {"ms": 5}
    assert env["errors"] == []

    env_fail = _envelope(False, None, {}, [{"code": "X", "message": "fail"}])
    assert env_fail["success"] is False
    assert env_fail["data"] is None


def test_run_produces_valid_shape():
    """Should not crash even if DB/backend are unreachable."""
    env = run()
    assert isinstance(env, dict)
    assert "success" in env
    assert "data" in env
    assert "metadata" in env
    assert "errors" in env
    assert "timestamp" in env["data"]
    assert "backend" in env["data"]
    assert "sessions" in env["data"]
    assert "users" in env["data"]
    assert "usage" in env["data"]
    print("✓ run() produces valid envelope (backend may be unreachable locally)")


def test_time_helpers():
    assert _now().endswith("+00:00") or "Z" in _now()
    assert _hours_ago(24) < _now()


if __name__ == "__main__":
    test_envelope_shape()
    test_run_produces_valid_shape()
    test_time_helpers()
    print("\n✓ All monitor tests passed")
