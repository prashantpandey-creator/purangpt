# doc_path_audit

Pre-flight orientation pass: extract backtick-quoted file-path claims from `.md`
docs and check whether each exists on disk. Run at session start to surface stale
maps before any action is taken.

**Does NOT measure:** server-side paths (`/root/...`), SSH/home paths (`~/.ssh/...`),
API routes (`/api/...`), git refs (`origin/main`), model names, URLs, env vars.
These appear in the missing list and are expected false positives — focus on
`*.py`, `*.ts`, `*.md`, and relative directory paths.

## Tool descriptor

```json
{
  "tool_name": "doc_path_audit",
  "input_schema": {
    "type": "object",
    "properties": {
      "docs":      { "type": "array", "items": { "type": "string" }, "description": "absolute paths to .md files" },
      "repo_root": { "type": "string", "description": "absolute path to resolve claims against" }
    },
    "required": []
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "missing":            { "type": "array", "items": { "type": "object" } },
      "present":            { "type": "array", "items": { "type": "object" } },
      "total_claims":       { "type": "integer" },
      "total_docs_scanned": { "type": "integer" }
    },
    "required": ["missing", "present", "total_claims", "total_docs_scanned"]
  }
}
```

## Usage

```bash
# from purangpt/ repo root — scans CLAUDE*.md + .agents/AGENTS.md by default
venv/bin/python -m tools.doc_path_audit.check           # human summary
venv/bin/python -m tools.doc_path_audit.check --json    # JSON envelope

# custom docs / root
venv/bin/python -m tools.doc_path_audit.check \
  --docs /abs/path/CLAUDE.md,/abs/path/OTHER.md \
  --root /abs/repo/root \
  --json
```

As a library:

```python
from tools.doc_path_audit.check import run
env = run(docs=["/path/CLAUDE.md"], repo_root="/path/to/repo")
assert env["success"]
for m in env["data"]["missing"]:
    print(f"STALE: {m['doc']}:{m['line']}  {m['path']}")
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `docs=[]` | `success=false`, `errors=[{code:"no_docs"}]`, exit 2 |
| `repo_root` not a directory | `success=false`, `errors=[{code:"bad_repo_root"}]`, exit 2 |
| Stale paths found | `success=true`, `data.missing` non-empty, exit 1 |
| All paths present | `success=true`, `data.missing=[]`, exit 0 |

## Tests

```bash
venv/bin/python -m tools.doc_path_audit.test_check   # 11 tests, all pass
```
