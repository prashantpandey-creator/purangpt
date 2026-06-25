"""test_quota_atomicity.py — prove consume_message_unit gates atomically.

Run (needs the local dev Postgres):
  VECTOR_DB_URL=postgresql://badenath@127.0.0.1:5432/purangpt_dev \
    venv/bin/python -m backend.test_quota_atomicity

Verifies the fix for the non-atomic free-tier quota: under concurrency, a free
user at count=9 (limit 10) must have EXACTLY ONE of N simultaneous requests
succeed — never N. The old read-only check_rate_limit + post-stream fire-and-forget
increment let all N pass.
"""
import concurrent.futures
import sys
import uuid

from backend.db_client import get_db_conn, consume_message_unit


def _ensure_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            role TEXT DEFAULT 'free',
            daily_message_count INT DEFAULT 0,
            deep_research_count INT DEFAULT 0,
            daily_reset_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )


def test_concurrent_consume_caps_exactly():
    uid = "sec-test-" + uuid.uuid4().hex[:8]
    conn = get_db_conn()
    assert conn is not None, "needs a live DB (set VECTOR_DB_URL)"
    cur = conn.cursor()
    _ensure_schema(cur)
    cur.execute(
        "INSERT INTO profiles (id, role, daily_message_count, daily_reset_at) "
        "VALUES (%s,'free',9,NOW()) "
        "ON CONFLICT (id) DO UPDATE SET daily_message_count=9, daily_reset_at=NOW()",
        (uid,),
    )
    conn.commit()
    conn.close()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            results = list(ex.map(lambda _: consume_message_unit(uid, "free")[0], range(5)))
        allowed = sum(1 for a in results if a)
        assert allowed == 1, f"RACE: {allowed} passed, expected exactly 1"

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT daily_message_count FROM profiles WHERE id=%s", (uid,))
        final = cur.fetchone()["daily_message_count"]
        assert final == 10, f"OVERRUN: count={final}, expected 10"
    finally:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM profiles WHERE id=%s", (uid,))
        conn.commit()
        conn.close()


def test_pro_user_uncapped():
    allowed, rem = consume_message_unit("any-pro", "pro")
    assert allowed is True and rem == 999999, "pro must be uncapped with no DB write"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
