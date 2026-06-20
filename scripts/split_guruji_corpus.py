"""
PuranGPT — one-off Guruji corpus split.

Moves Guruji Sri Shailendra Sharma's commentary/discourse rows out of
`purana_verses` and into the dedicated `guruji_texts` table so they can be
retrieved + cited reliably alongside the Puranas via the mode-aware quota merge
(see indexer/search.py search_corpora).

This is a PURE ROW MOVE — embeddings, ids, content and metadata are preserved
exactly. The destination table + hybrid_search_guruji function must already exist
(run scripts/migrate_to_local_pg.py first, or apply that DDL to the live DB).

Usage:
    VECTOR_DB_URL=postgresql://... python scripts/split_guruji_corpus.py

Idempotent: INSERT ... ON CONFLICT (id) DO NOTHING, then DELETE only the rows
that now exist in guruji_texts. Safe to re-run.
"""

import os
import sys
import psycopg2

# Rows belonging to the Guruji corpus. Mirrors the live id/category conventions:
#   - metadata.category in ('yogic-commentary', 'yogic-discourse')
#   - id like 'sharma-%'   (e.g. sharma-darshan_...)
#   - id like 'darshan-%'  (legacy id prefix)
PREDICATE = """
    metadata->>'category' IN ('yogic-commentary', 'yogic-discourse')
    OR id LIKE 'sharma-%'
    OR id LIKE 'darshan-%'
"""

DB_URL = os.environ.get("VECTOR_DB_URL")
if not DB_URL:
    print("Error: VECTOR_DB_URL not set.")
    sys.exit(1)


def count(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table};")
    return cur.fetchone()[0]


def main() -> None:
    print("Connecting to Postgres via VECTOR_DB_URL...")
    conn = psycopg2.connect(DB_URL)
    try:
        cur = conn.cursor()

        print("\n── Before ──")
        print(f"  purana_verses: {count(cur, 'purana_verses')}")
        print(f"  guruji_texts:  {count(cur, 'guruji_texts')}")

        # How many purana_verses rows match the Guruji predicate?
        cur.execute(f"SELECT COUNT(*) FROM purana_verses WHERE {PREDICATE};")
        to_move = cur.fetchone()[0]
        print(f"  guruji rows still in purana_verses: {to_move}")

        # Transaction: copy then delete the rows that landed in guruji_texts.
        cur.execute(f"""
            INSERT INTO guruji_texts (id, content, metadata, embedding)
            SELECT id, content, metadata, embedding
            FROM purana_verses
            WHERE {PREDICATE}
            ON CONFLICT (id) DO NOTHING;
        """)
        inserted = cur.rowcount

        cur.execute(f"""
            DELETE FROM purana_verses pv
            WHERE ({PREDICATE.replace('metadata', 'pv.metadata').replace('id LIKE', 'pv.id LIKE')})
              AND EXISTS (SELECT 1 FROM guruji_texts g WHERE g.id = pv.id);
        """)
        deleted = cur.rowcount

        conn.commit()

        print("\n── Moved ──")
        print(f"  inserted into guruji_texts: {inserted}")
        print(f"  deleted from purana_verses: {deleted}")

        print("\n── After ──")
        print(f"  purana_verses: {count(cur, 'purana_verses')}")
        print(f"  guruji_texts:  {count(cur, 'guruji_texts')}")

        cur.close()
        print("\nSplit complete.")
    except Exception as e:
        conn.rollback()
        print(f"Error (rolled back): {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
