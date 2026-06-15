"""
PuranGPT — Comprehensive Indexer
================================
Reads ALL .jsonl files in data/chunks/ and:
1. Adds any missing chunks to ChromaDB (fixing the 170k vs 339k mismatch).
2. Adds any missing chunks to the BM25 chunk_map.
3. Rebuilds the BM25 index.

Run: python index_all_new_texts.py
"""
from __future__ import annotations
import json, logging, pickle, sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("indexer")

BASE       = Path(__file__).parent
CHUNKS_DIR = BASE / "data/chunks"
INDEX_DIR  = BASE / "data/indexes"
CHROMA_DIR = BASE / "data/chroma_db"

def load_all_chunks() -> list[dict]:
    all_chunks = []
    # Avoid loading all_chunks.jsonl which is an aggregate of others, we just load all individual .jsonl files
    # Actually, all_chunks.jsonl was created by the old indexer. Let's just load all .jsonl, but use a dict to deduplicate by ID.
    unique_chunks = {}
    for jsonl_file in CHUNKS_DIR.glob("*.jsonl"):
        log.info("Loading %s", jsonl_file.name)
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    c = json.loads(line)
                    if "id" in c:
                        unique_chunks[c["id"]] = c
                except Exception as e:
                    pass
    
    chunks_list = list(unique_chunks.values())
    log.info("Loaded %d unique chunks from disk.", len(chunks_list))
    return chunks_list

def sync_chroma(chunks: list[dict]) -> None:
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        log.error("Missing package: %s", e)
        return

    import os; os.environ["TOKENIZERS_PARALLELISM"] = "false"
    embed_model = SentenceTransformer("intfloat/multilingual-e5-small")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
    col = client.get_or_create_collection("purana_verses")

    existing = set(col.get(include=[])["ids"])
    log.info("ChromaDB currently has %d documents.", len(existing))
    
    to_add = [c for c in chunks if c["id"] not in existing]
    
    if not to_add:
        log.info("All chunks already in ChromaDB. Nothing to add.")
        return

    log.info("Embedding and inserting %d missing chunks into ChromaDB...", len(to_add))
    BATCH = 128
    for i in range(0, len(to_add), BATCH):
        batch = to_add[i:i+BATCH]
        texts  = [f"passage: {c.get('text', '')}" for c in batch]
        embeds = embed_model.encode(texts, normalize_embeddings=True).tolist()
        ids    = [c["id"] for c in batch]
        metas  = []
        for c in batch:
            # Metadata values must be str, int, float or bool
            m = {k: v for k, v in c.items() if k not in ("text",) and isinstance(v, (str, int, float, bool))}
            metas.append(m)
        docs = [c.get("text", "") for c in batch]
        col.add(ids=ids, embeddings=embeds, metadatas=metas, documents=docs)
        log.info("  Inserted batch %d-%d into ChromaDB", i+1, i+len(batch))

    log.info("✓ ChromaDB sync complete. Total: %d", col.count())

def sync_bm25(chunks: list[dict]) -> None:
    bm25_path      = INDEX_DIR / "bm25_index.pkl"
    chunk_map_path = INDEX_DIR / "chunk_map.json"

    chunk_map = []
    if chunk_map_path.exists():
        log.info("Loading existing BM25 chunk_map...")
        with open(chunk_map_path) as f:
            chunk_map = json.load(f)

    existing_ids = {c.get("id") for c in chunk_map if "id" in c}
    to_add = [c for c in chunks if c["id"] not in existing_ids]

    if not to_add:
        log.info("All chunks already in chunk_map. BM25 up to date.")
        return

    log.info("Adding %d new chunks to chunk_map...", len(to_add))
    chunk_map.extend(to_add)

    log.info("Saving updated chunk_map (%d total)...", len(chunk_map))
    with open(chunk_map_path, "w", encoding="utf-8") as f:
        json.dump(chunk_map, f, ensure_ascii=False)

    log.info("Rebuilding BM25 index (may take a few minutes)...")
    try:
        from rank_bm25 import BM25Okapi
        import re

        def _tokenize(text: str) -> list[str]:
            tokens = re.findall(r'[\u0900-\u097F]+|[a-zA-Z]+', text.lower())
            return [t for t in tokens if len(t) > 1]

        corpus = [_tokenize(c.get("text", "")) for c in chunk_map]
        bm25   = BM25Okapi(corpus)

        with open(bm25_path, "wb") as f:
            pickle.dump(bm25, f)
        log.info("✓ BM25 rebuilt: %d docs", len(corpus))
    except ImportError:
        log.warning("rank_bm25 not installed — BM25 rebuild skipped")

def main():
    log.info("=== PuranGPT Reindexer Started ===")
    chunks = load_all_chunks()
    sync_chroma(chunks)
    sync_bm25(chunks)
    log.info("✅ Full reindexing complete!")

if __name__ == "__main__":
    main()
