"""retrieval_qc — measure retrieval efficacy & source quality of PuranGPT search.

Answers, with hard numbers, the questions the user raised:
  - Is one source (e.g. Agni Purana) over-represented? Is it alphabetic bias?
  - Is the corpus richness actually explored, or do the same texts always win?
  - Is the source metadata clean (QC), or fragmented into file-ids?
  - Should Guruji's texts live in a separate store (used for cognition, not citation)?

This is the ANALYSIS + CLI half (pure, fixture-tested). The live-DB query
collection is in `collect.py` (run on the server / in the backend container),
which emits a JSON payload this consumes. Splitting them keeps the decision
logic deterministic and testable without a database (Rule 0, precondition A).

Usage:
  # Analyze a collected/captured payload (the normal path):
  venv/bin/python -m tools.retrieval_qc.check --payload run.json --json
  # Self-check on the built-in healthy fixture:
  venv/bin/python -m tools.retrieval_qc.check --json
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from tools.retrieval_qc.analyze import analyze


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(payload: Optional[Dict[str, Any]] = None,
        expectations: Optional[List[dict]] = None) -> Dict[str, Any]:
    """Analyze a collected search-results payload and return the standard envelope.

    `payload` shape is documented in analyze.py. `expectations` is the optional
    known-item list [{query, expect_source_contains, top_k}]. On empty/invalid
    payload, returns success=False with an errors[] entry (never raises).
    """
    metadata = {"tool": "retrieval_qc"}
    if not payload or not isinstance(payload, dict):
        return _envelope(False, None, metadata,
                         [{"code": "no_payload", "message": "payload dict required"}])

    queries = payload.get("queries", [])
    metadata["num_queries"] = len(queries)
    if not queries:
        return _envelope(False, None, metadata,
                         [{"code": "empty_payload",
                           "message": "payload has no queries — nothing to analyze"}])

    expectations = expectations or payload.get("expectations", [])
    data = analyze(payload, expectations)
    metadata["healthy"] = data["healthy"]
    return _envelope(True, data, metadata, [])


def _load_payload(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _builtin_demo_payload() -> Dict[str, Any]:
    """Tiny healthy fixture so `--json` with no args still demonstrates the shape."""
    return {"queries": [
        {"query": "dharma", "kind": "hybrid", "results": [
            {"source": "Mahabharata", "score": 0.82, "rank": 0, "fts_hit": False},
            {"source": "Manusmriti", "score": 0.78, "rank": 1, "fts_hit": True},
        ]},
    ]}


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    if "--payload" in argv:
        payload = _load_payload(argv[argv.index("--payload") + 1])
    else:
        payload = _builtin_demo_payload()

    env = run(payload)

    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"Retrieval health: {'✓ HEALTHY' if d['healthy'] else '✗ ISSUES'}")
        if d["failed_checks"]:
            print(f"Failed checks: {', '.join(d['failed_checks'])}")
        for name, c in d["checks"].items():
            mark = "✓" if c.get("pass") else "✗"
            print(f"  {mark} {name}")
        sep = d["checks"].get("corpus_separation", {})
        if sep.get("recommendation"):
            print(f"\nGuruji corpus: {sep['recommendation']}")

    if not env["success"]:
        return 2
    return 0 if env["data"]["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
