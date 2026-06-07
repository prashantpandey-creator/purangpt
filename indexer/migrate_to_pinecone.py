import os
import sys
import argparse
from pathlib import Path

# Ensure the backend module can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.pinecone_client import init_pinecone, upsert_vectors
import chromadb

def migrate():
    print("Starting migration from local ChromaDB to Pinecone Serverless...")
    
    # Check Pinecone init
    if not init_pinecone():
        print("Failed to initialize Pinecone. Please check your PINECONE_API_KEY in .env")
        sys.exit(1)
        
    print("Pinecone initialized successfully.")
    
    # Connect to local ChromaDB
    db_dir = "./data/chroma_db"
    if not os.path.exists(db_dir):
        print(f"Local ChromaDB not found at {db_dir}")
        sys.exit(1)
        
    print("Connecting to local ChromaDB...")
    client = chromadb.PersistentClient(path=db_dir)
    
    try:
        collection = client.get_collection("purana_verses")
    except ValueError:
        print("Collection 'purana_verses' not found in ChromaDB.")
        sys.exit(1)
        
    count = collection.count()
    print(f"Found {count} vectors in ChromaDB collection 'purana_verses'.")
    
    if count == 0:
        print("No vectors to migrate.")
        return

    # Fetch and upsert in batches
    batch_size = 100
    total_migrated = 0
    
    for offset in range(0, count, batch_size):
        batch = collection.get(
            include=["embeddings", "metadatas", "documents"],
            limit=batch_size,
            offset=offset
        )
        
        pinecone_vectors = []
        for i in range(len(batch["ids"])):
            id_str = batch["ids"][i]
            embedding = batch["embeddings"][i]
            metadata = batch["metadatas"][i]
            document = batch["documents"][i]
            
            # Pinecone requires metadata values to be strings, numbers, booleans, or lists of strings
            # We must ensure text is stored in metadata for retrieval
            if metadata is None:
                metadata = {}
            metadata["text"] = document
            
            pinecone_vectors.append({
                "id": id_str,
                "values": embedding,
                "metadata": metadata
            })
            
        print(f"Upserting batch {offset} to {offset + len(pinecone_vectors)}...")
        upsert_vectors(pinecone_vectors)
        total_migrated += len(pinecone_vectors)
        
    print(f"Migration complete! Successfully migrated {total_migrated} vectors to Pinecone.")

if __name__ == "__main__":
    migrate()
