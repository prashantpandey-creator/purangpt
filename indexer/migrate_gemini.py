import os
import sys
import json
import time
from pathlib import Path

# Ensure backend module can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.pinecone_client import init_pinecone, upsert_vectors
from google import genai
from dotenv import load_dotenv

load_dotenv()

def migrate():
    print("Starting migration to Pinecone (Gemini Embeddings)...")
    
    if not init_pinecone():
        print("Failed to initialize Pinecone. Please check PINECONE_API_KEY in .env")
        sys.exit(1)
        
    client = genai.Client()
    
    chunks_dir = Path("data/chunks")
    if not chunks_dir.exists():
        print(f"Chunks directory not found at {chunks_dir}")
        sys.exit(1)
        
    # Read all chunks
    all_chunks = []
    seen_ids = set()
    
    jsonl_files = [p for p in sorted(chunks_dir.glob("*.jsonl")) 
                  if p.name not in {"all_chunks.jsonl", "shailendra_sharma_mock.jsonl"}]
    
    print(f"Loading chunks from {len(jsonl_files)} files...")
    for path in jsonl_files:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    chunk = json.loads(line)
                    cid = chunk.get("id")
                    if cid and chunk.get("text") and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_chunks.append(chunk)
                except Exception:
                    pass

    print(f"Loaded {len(all_chunks)} unique chunks.")
    
    if not all_chunks:
        print("No chunks to process.")
        return

    # Gemini allows 100 texts per embedding call
    batch_size = 100
    total_migrated = 0
    
    for offset in range(0, len(all_chunks), batch_size):
        batch = all_chunks[offset:offset+batch_size]
        texts = [c["text"] for c in batch]
        
        # Generate embeddings
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=texts
                )
                
                pinecone_vectors = []
                for i, emb in enumerate(response.embeddings):
                    chunk = batch[i]
                    metadata = {
                        "text": chunk["text"],
                        "purana": str(chunk.get("purana", "")),
                        "book_section": str(chunk.get("book_section", "")),
                        "chapter": str(chunk.get("chapter", "")),
                        "verse_range": str(chunk.get("verse_range", "")),
                        "language": str(chunk.get("language", ""))
                    }
                    pinecone_vectors.append({
                        "id": chunk["id"],
                        "values": emb.values,
                        "metadata": metadata
                    })
                    
                print(f"Upserting batch {offset} to {offset + len(pinecone_vectors)}...")
                upsert_vectors(pinecone_vectors)
                total_migrated += len(pinecone_vectors)
                break # Success, exit retry loop
                
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "Quota exceeded" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    sleep_time = 31 * (attempt + 1)
                    print(f"Rate limit hit at batch {offset}. Sleeping for {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    print(f"Error processing batch {offset}: {e}")
                    break # Not a rate limit error, skip batch
            
    print(f"Migration complete! Uploaded {total_migrated} vectors.")

if __name__ == "__main__":
    migrate()
