import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

load_dotenv()

CHUNKS_DIR = Path("data/chunks")
INDEX_NAME = "purangpt-verses"
EMBED_MODEL = "intfloat/multilingual-e5-small"
BATCH_SIZE = 2048  # Batch size for SentenceTransformer (GPU)
PINECONE_BATCH_SIZE = 200  # Batch size for Pinecone upserts

DERIVED_FILES = {
    "all_chunks.jsonl",
    "shailendra_sharma_mock.jsonl",
}

def load_chunks():
    all_chunks = []
    seen_ids = set()
    dup_count = 0

    jsonl_files = sorted(CHUNKS_DIR.glob("*.jsonl"))
    jsonl_files = [p for p in jsonl_files if p.name not in DERIVED_FILES]

    print(f"Loading chunks from {len(jsonl_files)} JSONL files...")
    for path in jsonl_files:
        count_before = len(all_chunks)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                
                cid = chunk.get("id")
                if not (chunk.get("text") and cid):
                    continue
                if cid in seen_ids:
                    dup_count += 1
                    continue
                seen_ids.add(cid)
                all_chunks.append(chunk)
        count = len(all_chunks) - count_before
        print(f"  {path.name}: {count:,} chunks")

    print(f"Total unique chunks to index: {len(all_chunks):,}")
    if dup_count:
        print(f"Skipped {dup_count:,} duplicates")
    return all_chunks

def chunk_to_metadata(chunk):
    meta = {}
    str_fields = ["id", "purana", "book_section", "verse_range",
                  "language", "source_file", "category"]
    int_fields = ["chapter", "source_page", "word_count"]

    for field in str_fields:
        val = chunk.get(field)
        if val is not None:
            meta[field] = str(val)

    for field in int_fields:
        val = chunk.get(field)
        if val is not None:
            try:
                meta[field] = int(val)
            except (ValueError, TypeError):
                meta[field] = 0
                
    meta["text"] = chunk.get("text", "")
    return meta

def main():
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("PINECONE_API_KEY not found in .env")
        return

    # Initialize Pinecone
    print("Initializing Pinecone...")
    pc = Pinecone(api_key=api_key)
    
    # Ensure index exists
    existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index: {INDEX_NAME}")
        pc.create_index(
            name=INDEX_NAME,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
    
    index = pc.Index(INDEX_NAME)
    
    # Load chunks
    chunks = load_chunks()
    if not chunks:
        print("No chunks found!")
        return

    # Load Model on GPU/MPS
    device = "cpu"
    print(f"Loading SentenceTransformer model {EMBED_MODEL} on '{device}'...")
    model = SentenceTransformer(EMBED_MODEL, device=device)
    print("Model loaded successfully.")

    # Process and upload
    print(f"Embedding and uploading {len(chunks):,} vectors to Pinecone...")
    
    from concurrent.futures import ThreadPoolExecutor

    # We will embed and upload in chunks
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        
        # Prepare text with multilingual-e5 prefix
        texts = ["passage: " + c.get("text", "")[:1000] for c in batch]
        ids = [c["id"] for c in batch]
        
        # Embed
        embeddings = model.encode(
            texts,
            batch_size=256,  # encode in small batches inside SentenceTransformer for optimal memory
            show_progress_bar=False,
            normalize_embeddings=True
        ).tolist()
        
        # Prepare Pinecone payload
        pinecone_vectors = []
        for j in range(len(batch)):
            clean_meta = chunk_to_metadata(batch[j])
            pinecone_vectors.append({
                "id": ids[j],
                "values": embeddings[j],
                "metadata": clean_meta
            })
            
        # Segment into sub-batches for parallel upsert
        sub_batches = [
            pinecone_vectors[k : k + PINECONE_BATCH_SIZE]
            for k in range(0, len(pinecone_vectors), PINECONE_BATCH_SIZE)
        ]
        
        def upload_sub_batch(sub_batch):
            max_retries = 5
            retry_delay = 2
            for attempt in range(max_retries):
                try:
                    index.upsert(vectors=sub_batch)
                    return True
                except Exception as e:
                    print(f"Error upserting to Pinecone (attempt {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        print("FATAL: Failed to upsert batch to Pinecone.")
            return False

        # Upload concurrently using a thread pool
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(upload_sub_batch, sub_batches))
                        
        print(f"Uploaded {min(i + BATCH_SIZE, len(chunks)):,}/{len(chunks):,} ({(min(i + BATCH_SIZE, len(chunks))/len(chunks))*100:.1f}%)")
        
    print("Reindexing to Pinecone completed successfully!")

if __name__ == "__main__":
    main()
