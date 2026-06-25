"""snapshot_untracked — back up UNTRACKED tool trees before they can be swept.

WHY THIS EXISTS (hit twice, see memory [[moat-branch-fragile]]):
  - Untracked files under tools/ (the read_pass "moat", growth_engine, the
    validators) are deleted from the working tree when another session runs
    `git checkout` to a branch that tracks them elsewhere.
  - Uncommitted tracked edits to shared files are discarded on the same switch.
This tool tars every untracked file under a guarded set of `paths` into a
timestamped archive, keeping the last N. Wired to the git `post-checkout` hook it
snapshots on EVERY branch change, so a sweep is always recoverable from a tarball.

It is a deterministic Rule-0 tool: zero LLM, JSON in / JSON out, sub-second, and
it NEVER raises for an expected failure (non-repo, bad dest) — it returns the
{success:false,...} envelope so the hook never blocks or slows a checkout.

  venv/bin/python -m tools.snapshot_untracked.check --json \
      --dest ~/sutradhar-backups --path tools/read_pass --path tools/growth_engine

See README.md for the failure table + the post-checkout install snippet.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
from typing import Any, Dict, List, Optional


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _untracked_under(repo_root: str, paths: List[str]) -> List[str]:
    """Return repo-relative untracked (and not-ignored) files under `paths`.
    Uses `git ls-files --others --exclude-standard` so .gitignored corpora
    (out/, node_modules, etc.) are correctly skipped."""
    if not paths:
        return []
    cmd = ["git", "-C", repo_root, "ls-files", "--others",
           "--exclude-standard", "--"] + list(paths)
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git ls-files failed")
    return [line for line in out.stdout.splitlines() if line.strip()]


def _is_git_repo(repo_root: str) -> bool:
    r = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True, timeout=15,
    )
    return r.returncode == 0 and r.stdout.strip() == "true"


def _prune(dest_dir: str, keep: int) -> int:
    """Keep only the `keep` newest snapshot-*.tar.gz; delete the rest. Returns
    the number pruned. Sorted by mtime so order is deterministic regardless of label."""
    snaps = [os.path.join(dest_dir, f) for f in os.listdir(dest_dir)
             if f.startswith("snapshot-") and f.endswith(".tar.gz")]
    snaps.sort(key=lambda p: os.path.getmtime(p))  # oldest first
    pruned = 0
    while len(snaps) > keep:
        victim = snaps.pop(0)
        try:
            os.remove(victim)
            pruned += 1
        except OSError:
            pass
    return pruned


def run(repo_root: str = ".", dest_dir: str = "", paths: Optional[List[str]] = None,
        keep: int = 10, dry_run: bool = False,
        label: Optional[str] = None) -> Dict[str, Any]:
    """Snapshot untracked files under `paths` into dest_dir/snapshot-<label>.tar.gz.

    On dry_run, enumerate only (archive=None, write nothing). Returns the standard
    envelope; data = {archive, file_count, files, pruned, dry_run}.
    """
    paths = paths or []
    repo_root = os.path.abspath(os.path.expanduser(repo_root))
    metadata = {"repo_root": repo_root, "paths": paths, "keep": keep}

    if not _is_git_repo(repo_root):
        return _envelope(False, None, metadata,
                         [{"code": "not_a_repo",
                           "message": f"not a git work tree: {repo_root}"}])

    # Enumerate the at-risk set.
    try:
        files = _untracked_under(repo_root, paths)
    except Exception as e:  # git itself failed — expected-failure envelope
        return _envelope(False, None, metadata,
                         [{"code": "git_failed", "message": str(e)}])

    # Nothing untracked → clean no-op success (e.g. paths fully tracked).
    if not files:
        return _envelope(True,
                         {"archive": None, "file_count": 0, "files": [],
                          "pruned": 0, "dry_run": dry_run},
                         metadata, [])

    if dry_run:
        return _envelope(True,
                         {"archive": None, "file_count": len(files),
                          "files": files, "pruned": 0, "dry_run": True},
                         metadata, [])

    # Real snapshot. Create dest, tar the files (repo-relative names), prune.
    dest_dir = os.path.abspath(os.path.expanduser(dest_dir)) if dest_dir else ""
    if not dest_dir:
        return _envelope(False, None, metadata,
                         [{"code": "no_dest", "message": "dest_dir required for a real snapshot"}])
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        return _envelope(False, None, metadata,
                         [{"code": "bad_dest", "message": f"cannot create dest {dest_dir}: {e}"}])

    name = "snapshot-" + (label or "snap") + ".tar.gz"
    archive = os.path.join(dest_dir, name)
    try:
        with tarfile.open(archive, "w:gz") as tf:
            for rel in files:
                abs_path = os.path.join(repo_root, rel)
                if os.path.exists(abs_path):
                    tf.add(abs_path, arcname=rel)
    except Exception as e:
        # leave no half-written archive masquerading as a good backup
        try:
            os.remove(archive)
        except OSError:
            pass
        return _envelope(False, None, metadata,
                         [{"code": "write_failed", "message": f"tar failed: {e}"}])

    pruned = _prune(dest_dir, keep)
    return _envelope(True,
                     {"archive": archive, "file_count": len(files),
                      "files": files, "pruned": pruned, "dry_run": False},
                     metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    repo_root = "."
    dest_dir = ""
    paths: List[str] = []
    keep = 10
    dry_run = "--dry-run" in argv
    label = None

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--repo" and i + 1 < len(argv):
            repo_root = argv[i + 1]; i += 1
        elif a == "--dest" and i + 1 < len(argv):
            dest_dir = argv[i + 1]; i += 1
        elif a == "--path" and i + 1 < len(argv):
            paths.append(argv[i + 1]); i += 1
        elif a == "--keep" and i + 1 < len(argv):
            keep = int(argv[i + 1]); i += 1
        elif a == "--label" and i + 1 < len(argv):
            label = argv[i + 1]; i += 1
        i += 1

    env = run(repo_root, dest_dir, paths, keep=keep, dry_run=dry_run, label=label)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR [{env['errors'][0]['code']}]: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        if d["archive"]:
            print(f"snapshot: {d['archive']}  ({d['file_count']} files, pruned {d['pruned']})")
        elif d["dry_run"]:
            print(f"dry-run: would capture {d['file_count']} files")
        else:
            print("nothing untracked to snapshot")

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
