"""Tests for snapshot_untracked — written FIRST (Rule 0 precondition A).

Run: venv/bin/python -m tools.snapshot_untracked.test_check   (from purangpt/ repo root)

The contract under test:
  run(repo_root, dest_dir, paths, keep=N, dry_run=False, label=None)
    -> {success, data:{archive, file_count, files, pruned, dry_run}, metadata, errors}

  - Enumerates UNTRACKED files (git ls-files --others --exclude-standard) under the
    given `paths`, tars them to dest_dir/snapshot-<label>.tar.gz, prunes old
    snapshots beyond `keep`, returns the envelope.
  - dry_run=True: lists what WOULD be captured, writes nothing.
  - A non-repo root, or an uncreatable dest, returns success=False with an errors[]
    entry — never raises for the expected-failure case.
  - The whole point: it must run in well under a second and never block a checkout,
    and it must capture the moat (tools/read_pass) when read_pass is untracked.
"""
import os
import tarfile
import tempfile

from tools.snapshot_untracked.check import run

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"archive", "file_count", "files", "pruned", "dry_run"}

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)  # purangpt/


def _fresh_dest():
    return tempfile.mkdtemp(prefix="snap_test_")


def test_envelope_shape():
    dest = _fresh_dest()
    env = run(REPO_ROOT, dest, ["tools/snapshot_untracked"], keep=3, dry_run=True)
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True, env
    assert env["errors"] == [], env["errors"]
    assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    print("ok: envelope_shape")


def test_dry_run_writes_nothing_but_lists():
    dest = _fresh_dest()
    env = run(REPO_ROOT, dest, ["tools/snapshot_untracked"], keep=3, dry_run=True)
    assert env["success"] is True
    assert env["data"]["dry_run"] is True
    assert env["data"]["archive"] is None, "dry-run must not name a real archive"
    # this very tool is untracked → it must see its own files
    assert env["data"]["file_count"] >= 1, "dry-run should still enumerate"
    assert not os.listdir(dest), "dry-run must write NOTHING to dest"
    print("ok: dry_run_writes_nothing_but_lists")


def test_real_snapshot_creates_readable_tarball():
    dest = _fresh_dest()
    env = run(REPO_ROOT, dest, ["tools/snapshot_untracked"], keep=3, label="t1")
    assert env["success"] is True, env
    arc = env["data"]["archive"]
    assert arc and os.path.exists(arc), f"archive must exist: {arc}"
    assert arc.endswith(".tar.gz")
    # it must be a valid, readable gzip tar containing real files
    with tarfile.open(arc, "r:gz") as tf:
        names = [n for n in tf.getnames() if not n.endswith("/")]
    assert any("snapshot_untracked" in n for n in names), names[:5]
    assert env["data"]["file_count"] == len(names)
    print("ok: real_snapshot_creates_readable_tarball")


def test_captures_read_pass_when_untracked():
    """The moat guard: if tools/read_pass has untracked files, the snapshot must
    include them. (Self-adjusts if, on some future branch, read_pass is fully
    tracked — then there's simply nothing to capture and the list is empty.)"""
    dest = _fresh_dest()
    env = run(REPO_ROOT, dest, ["tools/read_pass"], keep=2, dry_run=True)
    assert env["success"] is True, env
    files = env["data"]["files"]
    rp = [f for f in files if f.startswith("tools/read_pass")]
    if files:  # anything untracked under read_pass MUST be captured
        assert rp, f"read_pass untracked files not captured: {files[:5]}"
    print(f"ok: captures_read_pass_when_untracked ({len(rp)} read_pass files)")


def test_prune_keeps_only_N():
    dest = _fresh_dest()
    env = None
    for i in range(4):  # 4 snapshots, keep=2 → 2 remain
        env = run(REPO_ROOT, dest, ["tools/snapshot_untracked"], keep=2, label=f"p{i}")
        assert env["success"] is True, env
    remaining = sorted(f for f in os.listdir(dest) if f.endswith(".tar.gz"))
    assert len(remaining) == 2, f"keep=2 should leave 2, found {len(remaining)}: {remaining}"
    assert env["data"]["pruned"] >= 1, env["data"]
    print(f"ok: prune_keeps_only_N (remaining={remaining})")


def test_non_repo_root_errors():
    dest = _fresh_dest()
    env = run("/tmp", dest, ["tools/snapshot_untracked"], keep=2)
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] in ("not_a_repo", "git_failed"), env["errors"]
    print("ok: non_repo_root_errors")


def test_bad_dest_errors():
    # a dest under a file (cannot be a directory) → clean failure envelope
    bad = os.path.join(tempfile.gettempdir(), "snap_a_file")
    with open(bad, "w") as fh:
        fh.write("x")
    env = run(REPO_ROOT, os.path.join(bad, "sub"), ["tools/snapshot_untracked"], keep=2)
    assert env["success"] is False, env
    assert env["errors"], env
    print("ok: bad_dest_errors")


def test_empty_paths_is_noop_success():
    dest = _fresh_dest()
    env = run(REPO_ROOT, dest, [], keep=2)
    assert env["success"] is True, env
    assert env["data"]["file_count"] == 0
    assert env["data"]["archive"] is None, "nothing to capture → no archive"
    print("ok: empty_paths_is_noop_success")


if __name__ == "__main__":
    test_envelope_shape()
    test_dry_run_writes_nothing_but_lists()
    test_real_snapshot_creates_readable_tarball()
    test_captures_read_pass_when_untracked()
    test_prune_keeps_only_N()
    test_non_repo_root_errors()
    test_bad_dest_errors()
    test_empty_paths_is_noop_success()
    print("\nALL TESTS PASSED")
