"""<tool_name> — one-line purpose.

COPY-ME TEMPLATE. To make a new Rule-0 tool:
  cp -r tools/_template tools/<name>
then rename this module's logic, fill in `run()`, update README.md, and write
tests FIRST in test_check.py (Rule 0, precondition A). Keep the
{success,data,metadata,errors} envelope and the --json CLI exactly as-is so the
tool is a drop-in sub-agent replacement (Rule 0, precondition B) and chainable.

Input contract:  run(<your args>) -> dict (envelope)
Output contract (envelope.data on success): { ... your fields ... }

See tools/sse_contract_check/ for a complete, real implementation of this shape.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    """Wrap a result in the standard tool envelope (do not change the shape)."""
    return {"success": success, "data": data,
            "metadata": metadata, "errors": errors}


def run(example_input: str = "") -> Dict[str, Any]:
    """Do the deterministic work and return the standard envelope.

    Replace this body. On bad input / failure, return success=False with an
    errors[] entry ({"code","message"}) and data=None — never raise for the
    expected-failure case, so callers and tests get a uniform contract.
    """
    metadata = {"example_input": example_input}
    if example_input == "boom":  # demo error path — replace
        return _envelope(False, None, metadata,
                         [{"code": "bad_input", "message": "example failure"}])
    data = {"echo": example_input, "length": len(example_input)}  # replace
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    example_input = ""
    if "--input" in argv:
        example_input = argv[argv.index("--input") + 1]

    env = run(example_input)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        print(f"OK: {env['data']}")

    if not env["success"]:
        return 2
    # Convention: exit 1 signals a "finding" (e.g. drift detected); adjust per tool.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
