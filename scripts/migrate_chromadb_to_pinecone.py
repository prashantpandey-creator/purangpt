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
        
    batch_size = 100
    migrated_count = 0
    
    # We fetch all IDs first
    all_data = collection.get(include=["metadatas"])
    all_ids = all_data["ids"]
    
    print(f"Starting migration in batches of {batch_size}...")
    
    for i in range(0, len(all_ids), batch_size):
        batch_ids = all_ids[i:i + batch_size]
        
        # Get the embeddings and metadatas for this batch
        batch_data = collection.get(
            ids=batch_ids,
            include=["embeddings", "metadatas"]
        )
        
        pinecone_vectors = []
        for j in range(len(batch_ids)):
            metadata = batch_data["metadatas"][j]
            # Ensure no None values in metadata, Pinecone doesn't like None
            clean_metadata = {k: v for k, v in metadata.items() if v is not None}
            
            pinecone_vectors.append({
                "id": batch_ids[j],
                "values": batch_data["embeddings"][j],
                "metadata": clean_metadata
            })
            
        try:
            upsert_vectors(pinecone_vectors)
            migrated_count += len(batch_ids)
            print(f"Migrated {migrated_count}/{count} ({(migrated_count/count)*100:.1f}%)")
        except Exception as e:
            print(f"Error upserting batch {i}: {e}")
            
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
