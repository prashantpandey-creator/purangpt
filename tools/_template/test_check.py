"""Tests for <tool_name> — write these FIRST (Rule 2), before implementing run().

Run: venv/bin/python -m tools._template.test_check   (from purangpt/ repo root)

These encode "what should I see if this works": the standard envelope shape, the
data schema on success, and the error envelope on failure. For filter tools,
ALSO commit 1-3 real captured upstream outputs as fixtures here and assert
real-fixture-in -> contract-envelope-out (see tools/sse_contract_check).
"""
from tools._template.check import run

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"echo", "length"}  # replace with your tool's output_schema keys


def test_envelope_shape():
    env = run("hello")
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True
    assert env["errors"] == []
    assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    print("ok: envelope_shape")


def test_success_data():
    env = run("hello")
    assert env["data"]["echo"] == "hello"
    assert env["data"]["length"] == 5
    print("ok: success_data")


def test_error_envelope():
    env = run("boom")
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] == "bad_input", env["errors"]
    print("ok: error_envelope")


if __name__ == "__main__":
    test_envelope_shape()
    test_success_data()
    test_error_envelope()
    print("\nALL TESTS PASSED")
