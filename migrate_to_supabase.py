import os
import time
import chromadb
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Required environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

CHROMA_DIR = "./data/chroma_db"  # Local path
TABLE_NAME = "purana_verses"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) must be set in .env")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Connecting to local ChromaDB...")
client = chromadb.PersistentClient(path=CHROMA_DIR)
try:
    collection = client.get_collection("purana_verses")
except Exception as e:
    print(f"Error getting collection: {e}")
    exit(1)

count = collection.count()
print(f"Found {count} items in ChromaDB.")

if count == 0:
    print("No items to migrate.")
    exit(0)

BATCH_SIZE = 100
offset = 0

print(f"Starting migration to Supabase table '{TABLE_NAME}'...")
while offset < count:
    batch = collection.get(include=["embeddings", "metadatas", "documents"], limit=BATCH_SIZE, offset=offset)
    
    ids = batch["ids"]
    embeddings = batch["embeddings"]
    metadatas = batch["metadatas"]
    documents = batch["documents"]
    
    if not ids:
        break

    supabase_rows = []
    for i in range(len(ids)):
        meta = metadatas[i] or {}
        # Ensure metadata is clean
        clean_meta = {}
        for k, v in meta.items():
            if v is not None:
                clean_meta[k] = v
                
        supabase_rows.append({
            "id": str(ids[i]),
            "content": documents[i] if documents[i] else "",
            "metadata": clean_meta,
            "embedding": embeddings[i].tolist() if hasattr(embeddings[i], "tolist") else embeddings[i]
        })

    # Insert into Supabase
    try:
        # Use upsert to avoid failing on duplicates if script is run multiple times
        response = supabase.table(TABLE_NAME).upsert(supabase_rows).execute()
        offset += len(ids)
        print(f"Upserted {offset}/{count} vectors to Supabase...")
    except Exception as e:
        print(f"Failed to upsert batch at offset {offset}: {e}")
        # Optionally break or retry
        # break
        time.sleep(1) # simple backoff
        continue

print("Migration complete!")
