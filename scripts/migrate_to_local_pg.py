import os
import time
import psycopg2
import psycopg2.extras
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

LOCAL_DB_URL = "postgresql://postgres:postgres@localhost:5432/purangpt"
TABLE_NAME = "purana_verses"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE credentials missing.")
    exit(1)

print("Connecting to Supabase...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Connecting to local Postgres...")
# Add wait mechanism for Docker Postgres
max_retries = 10
conn = None
for i in range(max_retries):
    try:
        conn = psycopg2.connect(LOCAL_DB_URL)
        break
    except psycopg2.OperationalError:
        print(f"Waiting for Postgres to start (attempt {i+1}/{max_retries})...")
        time.sleep(2)

if not conn:
    print("Failed to connect to local Postgres.")
    exit(1)

cur = conn.cursor()

print("Setting up local database schema...")
cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

cur.execute(f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id TEXT PRIMARY KEY,
    content TEXT,
    metadata JSONB,
    embedding vector(384),
    fts tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
);
""")

cur.execute(f"""
CREATE INDEX IF NOT EXISTS {TABLE_NAME}_fts_idx ON {TABLE_NAME} USING GIN (fts);
""")
conn.commit()

cur.execute(f"""
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding vector(384),
    match_count INT,
    filter_metadata JSONB DEFAULT '{{}}'::jsonb
) RETURNS TABLE (
    id TEXT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    WITH semantic_search AS (
        SELECT 
            pv.id,
            pv.content,
            pv.metadata,
            1 - (pv.embedding <=> query_embedding) as sim,
            ROW_NUMBER() OVER (ORDER BY pv.embedding <=> query_embedding) as semantic_rank
        FROM purana_verses pv
        WHERE pv.metadata @> filter_metadata
        ORDER BY pv.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    keyword_search AS (
        SELECT 
            pv.id,
            ts_rank(pv.fts, websearch_to_tsquery('simple', query_text)) as fts_rank,
            ROW_NUMBER() OVER (ORDER BY ts_rank(pv.fts, websearch_to_tsquery('simple', query_text)) DESC) as keyword_rank
        FROM purana_verses pv
        WHERE pv.fts @@ websearch_to_tsquery('simple', query_text)
          AND pv.metadata @> filter_metadata
        ORDER BY fts_rank DESC
        LIMIT match_count * 2
    )
    SELECT 
        COALESCE(ss.id, ks.id) as id,
        COALESCE(ss.content, (SELECT p.content FROM purana_verses p WHERE p.id = ks.id)) as content,
        COALESCE(ss.metadata, (SELECT p.metadata FROM purana_verses p WHERE p.id = ks.id)) as metadata,
        -- RRF calculation
        COALESCE(1.0 / (60 + ss.semantic_rank), 0.0) + COALESCE(1.0 / (60 + ks.keyword_rank), 0.0) as similarity
    FROM semantic_search ss
    FULL OUTER JOIN keyword_search ks ON ss.id = ks.id
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;
""")
conn.commit()

# Create standard pgvector index for fast semantic search
cur.execute(f"""
CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops);
""")
conn.commit()

count_res = supabase.table(TABLE_NAME).select("id", count="exact").limit(1).execute()
total_count = count_res.count
print(f"Found {total_count} verses in Supabase.")

BATCH_SIZE = 1000
offset = 0

print("Starting migration...")
while offset < total_count:
    res = supabase.table(TABLE_NAME).select("*").range(offset, offset + BATCH_SIZE - 1).execute()
    data = res.data
    
    if not data:
        break
        
    args_list = []
    for row in data:
        emb = row['embedding']
        if isinstance(emb, str):
            emb = emb.strip("[]").split(",")
            emb = [float(e) for e in emb]
            
        args_list.append((row['id'], row['content'], psycopg2.extras.Json(row['metadata']), emb))
        
    psycopg2.extras.execute_values(
        cur,
        f"INSERT INTO {TABLE_NAME} (id, content, metadata, embedding) VALUES %s ON CONFLICT (id) DO NOTHING",
        args_list
    )
    conn.commit()
    
    offset += len(data)
    print(f"Migrated {offset}/{total_count} verses...")

print("Migration complete!")
cur.close()
conn.close()
