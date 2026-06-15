"""
PuranGPT — Index Cleaner
========================
Removes chunks with `chapter == 0` or containing known HTML boilerplate 
from ChromaDB and BM25's chunk_map, and rebuilds BM25.

Run on the server: docker exec purangpt_backend python3 clean_indexes.py
"""
from __future__ import annotations
import json, logging, pickle, sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("cleaner")

BASE       = Path(__file__).parent
INDEX_DIR  = BASE / "data/indexes"
CHROMA_DIR = BASE / "data/chroma_db"

def is_bad_chunk(c: dict) -> bool:
    # Remove HTML headers/footers in Yoga Vasistha, or copyright pages (chapter 0)
    chapter = c.get("chapter")
    if chapter == 0 or chapter == "0" or str(chapter).strip() == "0":
        return True
    
    text = c.get("text", "")
    if "<!DOCTYPE html>" in text or "<html" in text or "<meta " in text or "<script" in text:
        return True
        
    if "This program is free software" in text and "javascript" in text.lower():
        return True

    return False

def clean_chroma() -> set[str]:
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError as e:
        log.error("Missing chromadb: %s", e)
        return set()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    col = client.get_or_create_collection("purana_verses")

    # Fetch all metadata and ids
    data = col.get(include=["metadatas"])
    ids = data["ids"]
    metas = data["metadatas"]
    
    bad_ids = set()
    for i, meta in enumerate(metas):
        # We also need to check text, but text is in 'documents' which might be huge to load entirely.
        # But we can check metadata first.
        if is_bad_chunk(meta):
            bad_ids.add(ids[i])
            
    # For HTML check, let's also fetch documents specifically for yoga vasistha if possible,
    # or just fetch all documents
    log.info("Fetching documents to check for HTML boilerplate...")
    all_data = col.get(include=["documents", "metadatas"])
    for i, doc in enumerate(all_data["documents"]):
        if doc and is_bad_chunk({"chapter": all_data["metadatas"][i].get("chapter"), "text": doc}):
            bad_ids.add(all_data["ids"][i])

    if bad_ids:
        log.info("Found %d bad chunks in ChromaDB. Deleting...", len(bad_ids))
        # Delete in batches
        bad_ids_list = list(bad_ids)
        BATCH = 500
        for i in range(0, len(bad_ids_list), BATCH):
            batch = bad_ids_list[i:i+BATCH]
            col.delete(ids=batch)
        log.info("Deleted %d chunks from ChromaDB. Remaining: %d", len(bad_ids_list), col.count())
    else:
        log.info("No bad chunks found in ChromaDB.")
        
    return bad_ids

def clean_bm25(bad_ids: set[str]) -> None:
    bm25_path      = INDEX_DIR / "bm25_index.pkl"
    chunk_map_path = INDEX_DIR / "chunk_map.json"

    if not chunk_map_path.exists():
        log.warning("chunk_map.json not found")
        return

    with open(chunk_map_path) as f:
        chunk_map = json.load(f)

    original_count = len(chunk_map)
    new_chunk_map = []
    removed_count = 0
    
    for c in chunk_map:
        cid = c.get("id")
        if cid in bad_ids or is_bad_chunk(c):
            removed_count += 1
            bad_ids.add(cid) # ensuring we catch anything missing in chroma but present here
        else:
            new_chunk_map.append(c)

    if removed_count == 0:
        log.info("No bad chunks found in BM25 chunk_map.")
        return

    log.info("Removed %d chunks from BM25 chunk_map. Saving...", removed_count)
    with open(chunk_map_path, "w", encoding="utf-8") as f:
        json.dump(new_chunk_map, f, ensure_ascii=False)

    log.info("Rebuilding BM25 index (may take a few minutes)...")
    try:
        from rank_bm25 import BM25Okapi
        import re

        def _tokenize(text: str) -> list[str]:
            tokens = re.findall(r'[\u0900-\u097F]+|[a-zA-Z]+', text.lower())
            return [t for t in tokens if len(t) > 1]

        corpus = [_tokenize(c.get("text", "")) for c in new_chunk_map]
        bm25   = BM25Okapi(corpus)

        with open(bm25_path, "wb") as f:
            pickle.dump(bm25, f)
        log.info("✓ BM25 rebuilt: %d docs", len(corpus))
    except ImportError:
        log.warning("rank_bm25 not installed — BM25 rebuild skipped")

def main():
    log.info("=== PuranGPT Data Cleaner Started ===")
    bad_ids = clean_chroma()
    clean_bm25(bad_ids)
    log.info("✅ Cleanup complete!")

if __name__ == "__main__":
    main()
