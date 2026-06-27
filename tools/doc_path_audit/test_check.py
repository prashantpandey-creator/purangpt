"""Tests for doc_path_audit — written FIRST (Rule 0 precondition A), before run().

Run: venv/bin/python -m tools.doc_path_audit.test_check   (from purangpt/ repo root)

These encode the contract: given markdown text claiming certain paths exist,
the tool correctly identifies which paths are present vs absent on disk.
Fixtures use a temp directory — no real filesystem coupling.
"""
import os
import tempfile
from tools.doc_path_audit.check import extract_path_claims, audit_claims, run

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"missing", "present", "total_claims", "total_docs_scanned"}


# ---- Unit: path claim extraction ----

def test_extracts_backtick_paths():
    md = "DB access lives in `backend/db_client.py` (psycopg2)"
    claims = extract_path_claims(md, doc_label="test.md")
    paths = [c["path"] for c in claims]
    assert "backend/db_client.py" in paths, paths
    print("ok: extracts_backtick_paths")


def test_skips_non_path_backticks():
    md = "Use `npm install` and set `NEXT_PUBLIC_API_URL` in the env."
    claims = extract_path_claims(md, doc_label="test.md")
    paths = [c["path"] for c in claims]
    assert "npm install" not in paths, paths
    assert "NEXT_PUBLIC_API_URL" not in paths, paths
    print("ok: skips_non_path_backticks")


def test_extracts_see_pattern():
    md = "See `secrets/README.md` for details."
    claims = extract_path_claims(md, doc_label="test.md")
    paths = [c["path"] for c in claims]
    assert "secrets/README.md" in paths, paths
    print("ok: extracts_see_pattern")


def test_no_claims_in_empty_doc():
    claims = extract_path_claims("", doc_label="empty.md")
    assert claims == [], claims
    print("ok: no_claims_in_empty_doc")


# ---- Unit: audit_claims against real temp dir ----

def test_present_file_detected():
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "backend"))
        open(os.path.join(root, "backend", "main.py"), "w").close()
        claims = [{"path": "backend/main.py", "doc": "test.md", "line": 1}]
        missing, present = audit_claims(claims, root)
        assert len(present) == 1
        assert len(missing) == 0
    print("ok: present_file_detected")


def test_missing_file_detected():
    with tempfile.TemporaryDirectory() as root:
        claims = [{"path": "engine/query_engine.py", "doc": "test.md", "line": 1}]
        missing, present = audit_claims(claims, root)
        assert len(missing) == 1
        assert missing[0]["path"] == "engine/query_engine.py"
    print("ok: missing_file_detected")


def test_directory_path_detected():
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "backend", "agents"))
        claims = [{"path": "backend/agents/", "doc": "test.md", "line": 1}]
        missing, present = audit_claims(claims, root)
        assert len(present) == 1
    print("ok: directory_path_detected")


# ---- Integration: run() envelope ----

def test_run_clean_returns_success():
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "backend"))
        open(os.path.join(root, "backend", "main.py"), "w").close()
        md_path = os.path.join(root, "CLAUDE.md")
        with open(md_path, "w") as f:
            f.write("Server logic lives in `backend/main.py`.\n")
        env = run(docs=[md_path], repo_root=root)
        assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
        assert env["success"] is True
        assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
        assert env["data"]["total_claims"] >= 1
        assert len(env["data"]["missing"]) == 0
    print("ok: run_clean_returns_success")


def test_run_stale_path_surfaces_in_missing():
    with tempfile.TemporaryDirectory() as root:
        md_path = os.path.join(root, "CLAUDE.md")
        with open(md_path, "w") as f:
            f.write("Query engine lives in `engine/query_engine.py`.\n")
        env = run(docs=[md_path], repo_root=root)
        assert env["success"] is True  # tool succeeds even when paths are missing
        missing_paths = [m["path"] for m in env["data"]["missing"]]
        assert "engine/query_engine.py" in missing_paths, missing_paths
    print("ok: run_stale_path_surfaces_in_missing")


def test_run_no_docs_returns_error():
    env = run(docs=[], repo_root="/tmp")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "no_docs"
    print("ok: run_no_docs_returns_error")


def test_run_missing_repo_root_returns_error():
    env = run(docs=["/nonexistent/CLAUDE.md"], repo_root="/nonexistent/root")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "bad_repo_root"
    print("ok: run_missing_repo_root_returns_error")


if __name__ == "__main__":
    test_extracts_backtick_paths()
    test_skips_non_path_backticks()
    test_extracts_see_pattern()
    test_no_claims_in_empty_doc()
    test_present_file_detected()
    test_missing_file_detected()
    test_directory_path_detected()
    test_run_clean_returns_success()
    test_run_stale_path_surfaces_in_missing()
    test_run_no_docs_returns_error()
    test_run_missing_repo_root_returns_error()
    print("\nALL TESTS PASSED")
