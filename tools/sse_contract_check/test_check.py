"""Tests for sse_contract_check — written BEFORE the implementation (TDD).

Run: venv/bin/python -m tools.sse_contract_check.test_check

These encode "what should I see happen if this works":
  - the standard tool envelope shape is always returned,
  - data conforms to the declared output_schema,
  - drift is detected when backend/frontend type sets differ,
  - in_sync is True when they match,
  - a missing path yields the error envelope (success=False).
"""
import os
import tempfile

from tools.sse_contract_check.check import check_contract

# Minimal fixtures mimicking the two source files' relevant lines.
BACKEND_FIXTURE = """
async def event_gen():
    yield f"data: {json.dumps({'type':'token','content':item})}\\n\\n"
    yield f"data: {json.dumps({'type':'status','message':content})}\\n\\n"
    yield f"data: {json.dumps({'type':'done'})}\\n\\n"
    yield {"type": "error", "message": "boom"}
    return EventSourceResponse(event_gen())

async def other_endpoint_gen():
    # Events from a DIFFERENT endpoint — must NOT be counted as chat drift.
    yield {"type": "search_complete", "count": 0}
    yield {"type": "translation_ready", "result_index": 0}
"""

FRONTEND_IN_SYNC = """
export type ChatEvent =
  | { type: "token"; content: string }
  | { type: "status"; message: string }
  | { type: "error"; message: string }
  | { type: "done"; session_id?: string };
"""

FRONTEND_DRIFTED = """
export type ChatEvent =
  | { type: "token"; content: string }
  | { type: "status"; message: string }
  | { type: "error"; message: string }
  | { type: "done"; session_id?: string }
  | { type: "phantom_event" };
"""

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"in_sync", "backend_scope", "backend_types", "frontend_types",
             "backend_only", "frontend_only"}


def _write(tmp, name, content):
    p = os.path.join(tmp, name)
    with open(p, "w") as f:
        f.write(content)
    return p


def test_envelope_shape():
    with tempfile.TemporaryDirectory() as tmp:
        be = _write(tmp, "main.py", BACKEND_FIXTURE)
        fe = _write(tmp, "api.ts", FRONTEND_IN_SYNC)
        env = check_contract(be, fe)
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True
    assert isinstance(env["errors"], list) and env["errors"] == []
    assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    print("ok: envelope_shape")


def test_in_sync_true_when_matching():
    with tempfile.TemporaryDirectory() as tmp:
        be = _write(tmp, "main.py", BACKEND_FIXTURE)
        fe = _write(tmp, "api.ts", FRONTEND_IN_SYNC)
        env = check_contract(be, fe, backend_scope="event_gen")
    d = env["data"]
    assert d["in_sync"] is True, d
    assert d["backend_only"] == [] and d["frontend_only"] == []
    assert d["backend_types"] == ["done", "error", "status", "token"], d["backend_types"]
    print("ok: in_sync_true_when_matching")


def test_drift_detected():
    with tempfile.TemporaryDirectory() as tmp:
        be = _write(tmp, "main.py", BACKEND_FIXTURE)
        fe = _write(tmp, "api.ts", FRONTEND_DRIFTED)
        env = check_contract(be, fe, backend_scope="event_gen")
    d = env["data"]
    assert d["in_sync"] is False, d
    assert d["frontend_only"] == ["phantom_event"], d["frontend_only"]
    assert d["backend_only"] == [], d["backend_only"]
    print("ok: drift_detected")


def test_error_envelope_on_missing_path():
    env = check_contract("/no/such/backend.py", "/no/such/frontend.ts")
    assert env["success"] is False, env
    assert env["data"] is None
    assert len(env["errors"]) >= 1
    assert env["errors"][0]["code"] == "path_not_found", env["errors"]
    print("ok: error_envelope_on_missing_path")


def test_scoped_to_endpoint_excludes_other_functions():
    """Events emitted by a different generator (other_endpoint_gen) must be
    ignored when scope is the chat generator (event_gen). This is the v2 fix:
    don't conflate multiple SSE endpoints living in one file."""
    with tempfile.TemporaryDirectory() as tmp:
        be = _write(tmp, "main.py", BACKEND_FIXTURE)
        fe = _write(tmp, "api.ts", FRONTEND_IN_SYNC)
        env = check_contract(be, fe, backend_scope="event_gen")
    d = env["data"]
    assert "search_complete" not in d["backend_types"], d["backend_types"]
    assert "translation_ready" not in d["backend_types"], d["backend_types"]
    assert d["in_sync"] is True, d
    assert d["backend_scope"] == "event_gen", d
    print("ok: scoped_to_endpoint_excludes_other_functions")


if __name__ == "__main__":
    test_envelope_shape()
    test_in_sync_true_when_matching()
    test_drift_detected()
    test_error_envelope_on_missing_path()
    test_scoped_to_endpoint_excludes_other_functions()
    print("\nALL TESTS PASSED")
