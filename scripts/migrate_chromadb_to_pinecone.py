import os
import sys
import chromadb
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.pinecone_client import init_pinecone, upsert_vectors

load_dotenv()

DB_DIR = "./data/chroma_db"
COLLECTION_NAME = "purana_verses"

def migrate():
    print("Initializing Pinecone...")
    if not init_pinecone():
        print("Pinecone initialization failed. Check PINECONE_API_KEY.")
        return

    print("Connecting to ChromaDB...")
    if not os.path.exists(DB_DIR):
        print(f"ChromaDB directory not found at {DB_DIR}")
        return
        
    client = chromadb.PersistentClient(path=DB_DIR)
    
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        print(f"Collection {COLLECTION_NAME} not found: {e}")
        return
        
    count = collection.count()
    print(f"Found {count} vectors in ChromaDB collection '{COLLECTION_NAME}'.")
    
    if count == 0:
        print("Nothing to migrate.")
        return
        
    chroma_batch_size = 1000
    pinecone_batch_size = 200
    migrated_count = 0
    
    print(f"Starting migration: fetching {chroma_batch_size} from ChromaDB, upserting {pinecone_batch_size} to Pinecone...")
    
    offset = 0
    while offset < count:
        # Get the embeddings, metadatas, and documents (text) for this batch using limit/offset
        batch_data = collection.get(
            limit=chroma_batch_size,
            offset=offset,
            include=["embeddings", "metadatas", "documents"]
        )
        
        batch_ids = batch_data["ids"]
        if not batch_ids:
            break
            
        for i in range(0, len(batch_ids), pinecone_batch_size):
            sub_ids = batch_ids[i : i + pinecone_batch_size]
            pinecone_vectors = []
            for j_idx in range(len(sub_ids)):
                j = i + j_idx
                metadata = batch_data["metadatas"][j]
                # Ensure no None values in metadata, Pinecone doesn't like None
                clean_metadata = {k: v for k, v in metadata.items() if v is not None}
                # Attach the document text to Pinecone metadata
                if batch_data["documents"] and j < len(batch_data["documents"]):
                    clean_metadata["text"] = batch_data["documents"][j]
                
                pinecone_vectors.append({
                    "id": batch_ids[j],
                    "values": batch_data["embeddings"][j],
                    "metadata": clean_metadata
                })
                
            max_retries = 5
            retry_delay = 2
            for attempt in range(max_retries):
                try:
                    upsert_vectors(pinecone_vectors)
                    break
                except Exception as e:
                    print(f"Error upserting batch at offset {offset}+{i} (attempt {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        print(f"FATAL: Failed to upsert batch after {max_retries} attempts.")
            
            migrated_count += len(sub_ids)
            print(f"Migrated {migrated_count}/{count} ({(migrated_count/count)*100:.1f}%)")
            
        offset += chroma_batch_size
            
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
