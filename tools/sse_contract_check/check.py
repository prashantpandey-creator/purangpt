"""sse_contract_check — detect drift between backend SSE event types and the
frontend ChatEvent contract.

See README.md (co-located) for the full purpose, JSON tool descriptor, the
{success,data,metadata,errors} output envelope, failure modes, and usage. This
module is the dogfood example for the workspace engineering rules in
.agents/AGENTS.md (tests-first, docs-as-code, JSON-contract).

Input contract:
    check_contract(backend_path: str, frontend_path: str) -> dict (envelope)
Output contract (envelope.data on success):
    {in_sync, backend_types, frontend_types, backend_only, frontend_only}
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List

# Matches  'type':'token'  and  "type": "done"  (single/double quotes, any spacing)
_BACKEND_TYPE_RE = re.compile(r"""['"]type['"]\s*:\s*['"]([a-z_]+)['"]""")
# Matches frontend union members:  | { type: "sources"; ... }
_FRONTEND_TYPE_RE = re.compile(r"""type:\s*['"]([a-z_]+)['"]""")


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    """Wrap a result in the standard tool envelope."""
    return {"success": success, "data": data,
            "metadata": metadata, "errors": errors}


def _slice_function(text: str, func_name: str) -> str:
    """Return the source of the named (async) function block.

    main.py hosts several SSE endpoints; we must only read the chat generator's
    emits, not every {"type":...} in the file. The block runs from its
    `def`/`async def` line to the next line that is dedented to <= the def's own
    indent (i.e. the next sibling statement), which for these generators is the
    `return EventSourceResponse(...)` that follows them.
    """
    lines = text.splitlines()
    start = None
    def_indent = 0
    pat = re.compile(r"^(\s*)(async\s+def|def)\s+" + re.escape(func_name) + r"\b")
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            start = i
            def_indent = len(m.group(1))
            break
    if start is None:
        return ""  # function not found → empty slice (caller reports no types)

    end = len(lines)
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent:
            end = j  # first sibling/dedented statement ends the block
            break
    return "\n".join(lines[start:end])


def _extract(path: str, regex: re.Pattern, scope=None) -> List[str]:
    """Extract matched types from `path`, optionally restricted to one or more
    generator functions.

    scope: None  → scan the whole file (legacy).
           str   → restrict to that one function's block.
           list  → UNION the blocks of every named function (e.g. /api/chat is
                   fed by both event_gen AND deep_research, which emit different
                   event types into the same frontend contract).
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if scope:
        names = [scope] if isinstance(scope, str) else list(scope)
        text = "\n".join(_slice_function(text, n) for n in names)
    return sorted(set(regex.findall(text)))


def check_contract(backend_path: str, frontend_path: str,
                   backend_scope=None) -> Dict[str, Any]:
    """Compare emitted backend SSE types vs declared frontend ChatEvent types.

    backend_scope: restrict which backend generator(s) count as the /api/chat
    contract. Accepts a single function name (str) or a LIST of them, whose
    emits are unioned. /api/chat is fed by MORE than one generator —
    `event_gen` (normal chat) and the deep-research path (`deep_research`),
    which emits `reasoning`/`info` — so a single scope misses those. This still
    excludes unrelated SSE endpoints (e.g. /api/sanskrit-search) in the same
    file. If None, the whole backend file is scanned (legacy behavior).

    Returns the standard envelope. On a missing/unreadable path, returns
    success=False with an errors[] entry (code="path_not_found"); never raises
    for that case, so callers and tests get a uniform contract.
    """
    metadata = {"backend_path": backend_path, "frontend_path": frontend_path}

    for label, path in (("backend", backend_path), ("frontend", frontend_path)):
        if not os.path.isfile(path):
            return _envelope(
                False, None, metadata,
                [{"code": "path_not_found",
                  "message": f"{label} path does not exist: {path}"}],
            )

    try:
        backend_types = _extract(backend_path, _BACKEND_TYPE_RE, scope=backend_scope)
        frontend_types = _extract(frontend_path, _FRONTEND_TYPE_RE)
    except OSError as exc:  # unreadable despite isfile (perms, etc.)
        return _envelope(False, None, metadata,
                         [{"code": "read_error", "message": str(exc)}])

    be, fe = set(backend_types), set(frontend_types)
    backend_only = sorted(be - fe)
    frontend_only = sorted(fe - be)

    data = {
        "in_sync": not backend_only and not frontend_only,
        "backend_scope": backend_scope,
        "backend_types": backend_types,
        "frontend_types": frontend_types,
        "backend_only": backend_only,
        "frontend_only": frontend_only,
    }
    return _envelope(True, data, metadata, [])


# Default paths relative to the backend repo root (purangpt/).
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_BACKEND = os.path.join(_REPO, "backend", "main.py")
_DEFAULT_FRONTEND = os.path.join(
    _REPO, "..", "purangpt-next", "src", "lib", "api.ts")


# /api/chat is served by MULTIPLE generators in backend/main.py: event_gen
# (normal chat) and deep_research (Deep Research mode, which emits reasoning/info).
# Both feed the same frontend ChatEvent contract, so both must be in scope.
# Scoping to this set still excludes unrelated endpoints (/api/sanskrit-search, etc.).
_DEFAULT_SCOPE = ["event_gen", "deep_research"]


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    backend = _DEFAULT_BACKEND
    frontend = _DEFAULT_FRONTEND
    scope = _DEFAULT_SCOPE
    if "--backend" in argv:
        backend = argv[argv.index("--backend") + 1]
    if "--frontend" in argv:
        frontend = argv[argv.index("--frontend") + 1]
    if "--scope" in argv:
        # comma-separated list, e.g. --scope event_gen,deep_research
        scope = [s.strip() for s in argv[argv.index("--scope") + 1].split(",") if s.strip()]
    if "--no-scope" in argv:
        scope = None  # scan whole backend file (legacy)

    env = check_contract(backend, frontend, backend_scope=scope)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        status = "✅ in sync" if d["in_sync"] else "⚠️  DRIFT"
        print(f"SSE contract: {status}")
        print(f"  backend types:  {d['backend_types']}")
        print(f"  frontend types: {d['frontend_types']}")
        if d["backend_only"]:
            print(f"  ⛔ backend emits, frontend can't parse: {d['backend_only']}")
        if d["frontend_only"]:
            print(f"  ℹ️  frontend declares, backend never emits: {d['frontend_only']}")

    if not env["success"]:
        return 2
    return 0 if env["data"]["in_sync"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
