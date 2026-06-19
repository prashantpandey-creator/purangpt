import sys, os
from dotenv import load_dotenv
load_dotenv(".env")
sys.path.insert(0, os.path.abspath("."))
from backend.db_client import get_db_conn

TEST_ID = "00000000-0000-0000-0000-000000000000"

conn = get_db_conn()
if not conn:
    print("No DB connection (VECTOR_DB_URL not set).")
    sys.exit(1)
try:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO profiles (id, role) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            (TEST_ID, "guest"),
        )
        cur.execute("SELECT id, role FROM profiles WHERE id = %s", (TEST_ID,))
        print("Inserted:", cur.fetchone())
        cur.execute("DELETE FROM profiles WHERE id = %s", (TEST_ID,))
    conn.commit()
    print("Insert + delete OK.")
except Exception as e:
    conn.rollback()
    print("Error:", e)
finally:
    conn.close()
