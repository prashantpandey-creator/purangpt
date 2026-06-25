"""Smoke test for growth_engine schema bootstrap.

Run: venv/bin/python -m growth_engine.test_schema
Exits 0 on success. Tests that:
  - init_growth_schema() creates all 6 ge_* tables
  - it is idempotent (second call also succeeds, no error)
  - tables_present() reports all 6
Requires VECTOR_DB_URL (uses the shared pooled connection).
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from growth_engine.schema import init_growth_schema, tables_present, GE_TABLES  # noqa: E402


def main() -> int:
    conn_ok = init_growth_schema()
    if not conn_ok:
        print("FAIL: init_growth_schema returned False (no DB? check VECTOR_DB_URL)")
        return 1

    # Idempotency: a second run must also succeed without error.
    assert init_growth_schema() is True, "schema init not idempotent"

    present = tables_present()
    missing = sorted(set(GE_TABLES) - set(present))
    assert not missing, f"missing tables after init: {missing}"

    print(f"OK: all {len(GE_TABLES)} ge_* tables present and idempotent")
    print(f"   {present}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
