import psycopg2

with open("schema.sql") as f:
    sql = f.read()

conn = psycopg2.connect(
    host="db.qpnbjhahxvjwncscyrde.supabase.co",
    database="postgres",
    user="postgres",
    password="PuranGPT2026Secure!",
    port=5432
)
conn.autocommit = True

try:
    with conn.cursor() as cur:
        cur.execute(sql)
    print("Schema applied successfully!")
except Exception as e:
    print(f"Error applying schema: {e}")
finally:
    conn.close()
