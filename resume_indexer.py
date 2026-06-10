import json
import os
import sys
from pathlib import Path

DB_DIR = Path("data/chroma_db")
CHUNKS_DIR = Path("data/chunks")
MASTER_FILE = CHUNKS_DIR / "all_chunks.jsonl"

def main():
    print("Resuming Indexer...")
    
    if not MASTER_FILE.exists():
        print("all_chunks.jsonl not found!")
        return
        
    all_chunks = []
    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_chunks.append(json.loads(line))
                
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        os.system(f'"{sys.executable}" -m pip install sentence-transformers chromadb -q')
        from sentence_transformers import SentenceTransformer
        import chromadb
        from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(DB_DIR), settings=Settings(anonymized_telemetry=False))
    col = client.get_or_create_collection("purana_verses", metadata={"hnsw:space": "cosine"})
    
    # Get existing IDs to skip
    print("Checking existing IDs in ChromaDB...")
    existing = col.get(include=[])
    existing_ids = set(existing["ids"])
    print(f"Found {len(existing_ids)} chunks already in DB.")
    
    # Filter remaining chunks
    remaining = [c for c in all_chunks if c["id"] not in existing_ids]
    print(f"Remaining chunks to embed: {len(remaining)}")
    
    if not remaining:
        print("Everything is already indexed!")
        return

    model = SentenceTransformer("intfloat/multilingual-e5-small")
    
    BATCH = 64
    indexed = len(existing_ids)
    total = len(all_chunks)
    
    for i in range(0, len(remaining), BATCH):
        batch = remaining[i:i+BATCH]
        texts = ["passage: " + c.get("text","")[:800] for c in batch]
        ids   = [c["id"] for c in batch]
        metas = [{
            "id":      c.get("id",""),
            "purana":  c.get("purana",""),
            "chapter": str(c.get("chapter","")),
            "verse_range": c.get("verse_range",""),
            "language":    c.get("language","sanskrit"),
            "source_file": c.get("source_file",""),
            "category":    c.get("category",""),
            "book_section":c.get("book_section",""),
        } for c in batch]
        
        embeddings = model.encode(texts, batch_size=BATCH, show_progress_bar=False, normalize_embeddings=True).tolist()
        col.upsert(ids=ids, embeddings=embeddings, documents=[c.get("text","") for c in batch], metadatas=metas)
        indexed += len(batch)
        
        if (indexed - len(existing_ids)) % 1280 == 0 or indexed == total:
            print(f"  {indexed:,}/{total:,} chunks indexed...", flush=True)

    print("✅ Indexing completely finished!")

if __name__ == "__main__":
    main()
