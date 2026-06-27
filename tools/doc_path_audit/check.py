"""doc_path_audit — pre-flight orientation pass: surface stale file-path claims in .md docs.

Extracts backtick-quoted paths from markdown files and checks whether each
exists on disk relative to the repo root. Returns split lists of missing vs
present paths so the agent knows which doc claims are stale before acting.

Run at session start to catch stale-map errors before any action is taken.

Input contract:  run(docs, repo_root) -> envelope
Output contract (envelope.data on success):
  { missing, present, total_claims, total_docs_scanned }
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple


# Matches a backtick-quoted token that looks like a relative file path:
# - contains a / or ends in a known extension, or ends in /
# - does NOT look like a shell command (no spaces), env var (no ALL_CAPS_ONLY),
#   or URL (no ://)
_PATH_RE = re.compile(r"`([^`\s]+)`")

# Path-like heuristic: must contain / OR end in a file extension.
# Rejects: env vars (ALL_CAPS no slash/dot), shell flags (--foo), bare words.
_PATH_HEURISTIC = re.compile(
    r"(.*[/\\].*|.*\.[a-zA-Z0-9]{1,6}$)"
)
_SKIP_RE = re.compile(
    r"^[A-Z_][A-Z0-9_]*$"   # ALL_CAPS env var
    r"|^--"                   # CLI flag
    r"|://"                   # URL
    r"| "                     # contains space (shell command)
)


def extract_path_claims(text: str, doc_label: str) -> List[Dict[str, Any]]:
    """Extract backtick-quoted tokens that look like file/dir paths."""
    claims = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _PATH_RE.finditer(line):
            token = m.group(1)
            if _SKIP_RE.search(token):
                continue
            if not _PATH_HEURISTIC.match(token):
                continue
            # Strip trailing punctuation that leaked into the backtick match
            token = token.rstrip(".,;:")
            claims.append({"path": token, "doc": doc_label, "line": lineno})
    return claims


def audit_claims(
    claims: List[Dict[str, Any]], repo_root: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split claims into (missing, present) by checking existence on disk."""
    missing, present = [], []
    seen = set()
    for claim in claims:
        key = claim["path"]
        if key in seen:
            continue
        seen.add(key)
        full = os.path.join(repo_root, claim["path"].lstrip("/"))
        if os.path.exists(full):
            present.append(claim)
        else:
            missing.append(claim)
    return missing, present


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(
    docs: Optional[List[str]] = None,
    repo_root: str = ".",
) -> Dict[str, Any]:
    """Audit file-path claims in the given markdown docs against repo_root.

    docs      — list of absolute paths to .md files to scan
    repo_root — absolute path to the repo root (claims are resolved relative to it)
    """
    if not docs:
        return _envelope(False, None, {"repo_root": repo_root},
                         [{"code": "no_docs", "message": "no docs provided"}])
    if not os.path.isdir(repo_root):
        return _envelope(False, None, {"repo_root": repo_root},
                         [{"code": "bad_repo_root",
                           "message": f"repo_root does not exist: {repo_root}"}])

    all_claims: List[Dict[str, Any]] = []
    for doc_path in docs:
        if not os.path.isfile(doc_path):
            continue
        text = open(doc_path, encoding="utf-8").read()
        label = os.path.relpath(doc_path, repo_root)
        all_claims.extend(extract_path_claims(text, doc_label=label))

    missing, present = audit_claims(all_claims, repo_root)
    metadata = {
        "repo_root": repo_root,
        "docs_scanned": [os.path.relpath(d, repo_root)
                         if os.path.isabs(d) else d for d in docs],
    }
    data = {
        "missing": missing,
        "present": present,
        "total_claims": len(missing) + len(present),
        "total_docs_scanned": len(docs),
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv

    # Resolve defaults: scan all CLAUDE*.md in repo root (two levels up from tools/)
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    if "--root" in argv:
        repo_root = argv[argv.index("--root") + 1]

    docs: List[str] = []
    if "--docs" in argv:
        docs = argv[argv.index("--docs") + 1].split(",")
    else:
        # Default: scan CLAUDE*.md files at repo root and one level down
        for name in os.listdir(repo_root):
            if name.startswith("CLAUDE") and name.endswith(".md"):
                docs.append(os.path.join(repo_root, name))
        # Also include .agents/AGENTS.md if present
        agents_md = os.path.join(repo_root, ".agents", "AGENTS.md")
        if os.path.isfile(agents_md):
            docs.append(agents_md)

    env = run(docs=docs, repo_root=repo_root)

    if as_json:
        print(json.dumps(env, indent=2))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message']}")
        return 2
    else:
        d = env["data"]
        print(f"doc_path_audit: {d['total_claims']} claims in {d['total_docs_scanned']} docs")
        if d["missing"]:
            print(f"\nMISSING ({len(d['missing'])}):")
            for m in d["missing"]:
                print(f"  {m['doc']}:{m['line']}  {m['path']}")
        else:
            print("  all claimed paths exist on disk")

    return 1 if env.get("data") and env["data"]["missing"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
