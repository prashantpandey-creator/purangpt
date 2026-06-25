# snapshot_untracked — back up untracked tool trees before a checkout sweeps them

Deterministic Rule-0 tool. Tars every **untracked** file under a guarded set of
`paths` into a timestamped `~/sutradhar-backups/snapshot-*.tar.gz`, pruning to the
last N. Wired to the git `post-checkout` hook so a branch switch can never silently
delete the read_pass "moat", growth_engine, or the validators. See memory
`[[moat-branch-fragile]]` — this trap has been hit twice (untracked files swept on
switchback; uncommitted tracked edits discarded on switch).

## Tool descriptor

```json
{
  "tool_name": "snapshot_untracked",
  "input_schema": {
    "type": "object",
    "properties": {
      "repo_root": { "type": "string" },
      "dest_dir":  { "type": "string" },
      "paths":     { "type": "array", "items": { "type": "string" } },
      "keep":      { "type": "integer", "default": 10 },
      "dry_run":   { "type": "boolean", "default": false },
      "label":     { "type": "string" }
    },
    "required": ["repo_root", "paths"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "archive":    { "type": ["string", "null"] },
      "file_count": { "type": "integer" },
      "files":      { "type": "array", "items": { "type": "string" } },
      "pruned":     { "type": "integer" },
      "dry_run":    { "type": "boolean" }
    },
    "required": ["archive", "file_count", "files", "pruned", "dry_run"]
  }
}
```

## Output envelope

```json
{ "success": true,
  "data": { "archive": "~/sutradhar-backups/snapshot-checkout-...tar.gz",
            "file_count": 71, "files": ["tools/read_pass/decode.py", "..."],
            "pruned": 0, "dry_run": false },
  "metadata": { "repo_root": "...", "paths": ["..."], "keep": 10 }, "errors": [] }
```

On failure: `success=false`, `data=null`, `errors=[{"code","message"}]`. It never
raises for an expected failure — so the post-checkout hook can never block a switch.

## Usage

```bash
# from purangpt/ repo root — dry run (enumerate, write nothing)
venv/bin/python -m tools.snapshot_untracked.check --json --dry-run \
    --dest ~/sutradhar-backups --path tools/read_pass

# real snapshot, keep last 10
venv/bin/python -m tools.snapshot_untracked.check \
    --dest ~/sutradhar-backups --path tools/read_pass --path tools/growth_engine \
    --keep 10 --label "manual-$(date +%Y%m%d-%H%M%S)"
```

As a library:

```python
from tools.snapshot_untracked.check import run
env = run(repo_root=".", dest_dir="~/sutradhar-backups",
          paths=["tools/read_pass"], keep=10)
assert env["success"]
```

## Install the post-checkout hook (per clone — hooks are NOT version-controlled)

The hook lives in `.git/hooks/post-checkout`, which git does not track. A tracked,
installable copy is kept at `tools/snapshot_untracked/post-checkout.hook`. To arm a
fresh clone:

```bash
cp tools/snapshot_untracked/post-checkout.hook .git/hooks/post-checkout
chmod +x .git/hooks/post-checkout
```

The hook fires only on **branch** checkouts (git flag `$3==1`), backgrounds the
snapshot, discards output, and always exits 0 — a backup failure never becomes a
git failure.

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `repo_root` is not a git work tree | `success=false`, `errors=[{code:"not_a_repo"}]`, exit 2 |
| `git ls-files` itself fails | `success=false`, `errors=[{code:"git_failed"}]` |
| Real snapshot requested but no `dest_dir` | `success=false`, `errors=[{code:"no_dest"}]` |
| `dest_dir` cannot be created | `success=false`, `errors=[{code:"bad_dest"}]` |
| tar write fails (half-archive removed) | `success=false`, `errors=[{code:"write_failed"}]` |
| Nothing untracked under `paths` | `success=true`, `archive=null`, `file_count=0` (clean no-op) |
| `dry_run=true` | `success=true`, `archive=null`, enumerates `files` only |
| Normal snapshot | `success=true`, `archive` set, exit 0 |

## Tests

`venv/bin/python -m tools.snapshot_untracked.test_check` — asserts envelope shape,
dry-run-writes-nothing, real-tarball-is-readable, **the moat guard** (read_pass
untracked files are captured), prune-keeps-N, and every failure envelope. Sub-second
(~100ms for a real snapshot), so it never slows a checkout.
