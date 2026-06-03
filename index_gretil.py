"""
PuranGPT — GRETIL Auto-Indexer
Chunks plain-text Sanskrit from GRETIL and builds ChromaDB + BM25 indexes.
"""

import json
import os
import pickle
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

RAW_DIR    = Path("data/raw_texts/gretil")
CHUNKS_DIR = Path("data/chunks")
INDEX_DIR  = Path("data/indexes")
DB_DIR     = Path("data/chroma_db")

CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

# Shloka boundary patterns
DANDA_RE   = re.compile(r'[।॥]')
CHAPTER_RE = re.compile(r'(?:adhy[Aā]ya|chapter|sarga|adhyaya)\s*[\d]+', re.IGNORECASE)
VERSE_RE   = re.compile(r'\b(\d+)\s*[.|,]\s*(\d+)\b') # E.g., 1.15

def get_metadata(text_dir: Path) -> dict:
    """Load provenance metadata if available."""
    meta_path = text_dir / "provenance.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def chunk_text(txt_path: Path, text_id: str, meta: dict) -> list[dict]:
    """Read text, split by verses, chunk, and return dicts."""
    print(f"\n📖 Chunking: {meta.get('name', text_id)}")
    
    with open(txt_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    chunks = []
    
    # Simple lines based chunking if dandas aren't prevalent
    has_dandas = '।' in full_text or '॥' in full_text
    
    current_chapter = 0
    verse_num = 0
    text_buffer = []
    line_buffer = []
    
    lines = full_text.splitlines()
    
    if has_dandas:
        # Verse based
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue
            
            # Detect chapter
            if CHAPTER_RE.search(line):
                current_chapter += 1
                
            parts = DANDA_RE.split(line)
            for part in parts:
                part = part.strip()
                if len(part) < 10:
                    continue
                text_buffer.append(part)
                line_buffer.append(i + 1)
                
                if len(text_buffer) >= 3:
                    verse_num += 1
                    chunk_text = ' । '.join(text_buffer) + ' ॥'
                    chunk_id   = f"{text_id}-{current_chapter}-{verse_num}"
                    
                    chunks.append({
                        "id":          chunk_id,
                        "purana":      meta.get("name", text_id.replace("_", " ").title()),
                        "category":    meta.get("tradition", "other"),
                        "book_section": f"Chapter {current_chapter}" if current_chapter else "",
                        "chapter":     current_chapter,
                        "verse_range": str(verse_num),
                        "text":        chunk_text[:1200],
                        "language":    "sanskrit",
                        "source_file": txt_path.name,
                        "source_page": line_buffer[0], # Using line num as 'page'
                        "word_count":  len(chunk_text.split()),
                    })
                    text_buffer = text_buffer[-1:]  # 1-verse overlap
                    line_buffer = line_buffer[-1:]
                    
        # Flush remaining buffer
        if len(text_buffer) >= 1:
            verse_num += 1
            chunk_text = ' । '.join(text_buffer)
            chunk_id   = f"{text_id}-{current_chapter}-{verse_num}"
            chunks.append({
                "id": chunk_id, "purana": meta.get("name", text_id),
                "category": meta.get("tradition", "other"),
                "chapter": current_chapter,
                "verse_range": str(verse_num),
                "text": chunk_text[:1200],
                "language": "sanskrit",
                "source_file": txt_path.name,
                "source_page": line_buffer[0] if line_buffer else 0,
                "word_count": len(chunk_text.split()),
            })
    else:
        # Line-based chunking (for texts without dandas)
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue
            
            if CHAPTER_RE.search(line):
                current_chapter += 1
                
            text_buffer.append(line)
            line_buffer.append(i + 1)
            
            if len(text_buffer) >= 5:
                verse_num += 1
                chunk_text = '\n'.join(text_buffer)
                chunk_id   = f"{text_id}-{current_chapter}-{verse_num}"
                
                chunks.append({
                    "id":          chunk_id,
                    "purana":      meta.get("name", text_id.replace("_", " ").title()),
                    "category":    meta.get("tradition", "other"),
                    "book_section": f"Chapter {current_chapter}" if current_chapter else "",
                    "chapter":     current_chapter,
                    "verse_range": str(verse_num),
                    "text":        chunk_text[:1200],
                    "language":    "sanskrit",
                    "source_file": txt_path.name,
                    "source_page": line_buffer[0],
                    "word_count":  len(chunk_text.split()),
                })
                text_buffer = text_buffer[-2:]  # overlap
                line_buffer = line_buffer[-2:]
                
        if len(text_buffer) >= 1:
            verse_num += 1
            chunk_text = '\n'.join(text_buffer)
            chunk_id   = f"{text_id}-{current_chapter}-{verse_num}"
            chunks.append({
                "id": chunk_id, "purana": meta.get("name", text_id),
                "category": meta.get("tradition", "other"),
                "chapter": current_chapter,
                "verse_range": str(verse_num),
                "text": chunk_text[:1200],
                "language": "sanskrit",
                "source_file": txt_path.name,
                "source_page": line_buffer[0] if line_buffer else 0,
                "word_count": len(chunk_text.split()),
            })

    print(f"  ✓  Extracted {len(chunks)} chunks")
    return chunks

def build_bm25_index(all_chunks: list[dict]):
    """Build BM25 sparse keyword index."""
    print("\n📊 Building BM25 keyword index…")
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        os.system(f'"{sys.executable}" -m pip install rank-bm25 -q')
        from rank_bm25 import BM25Okapi

    def tokenize(text):
        tokens = re.findall(r'[\u0900-\u097F]+|[a-zA-Z]+', text.lower())
        return [t for t in tokens if len(t) > 1]

    corpus = [tokenize(c.get("text","")) for c in all_chunks]
    bm25   = BM25Okapi(corpus)

    bm25_path = INDEX_DIR / "bm25_index.pkl"
    with open(bm25_path, "wb") as f:
        pickle.dump(bm25, f)

    chunk_map = [{
        "id": c.get("id",""), "purana": c.get("purana",""),
        "book_section": c.get("book_section",""), "chapter": c.get("chapter"),
        "verse_range": c.get("verse_range",""), "text": c.get("text","")[:500],
        "language": c.get("language",""), "source_file": c.get("source_file",""),
        "category": c.get("category",""),
    } for c in all_chunks]

    with open(INDEX_DIR / "chunk_map.json", "w", encoding="utf-8") as f:
        json.dump(chunk_map, f, ensure_ascii=False)

    print(f"  ✓  BM25 index: {len(all_chunks):,} documents")

def build_vector_index(all_chunks: list[dict]):
    """Build ChromaDB dense vector index using multilingual embeddings."""
    print("\n🔍 Building semantic vector index…")
    print("  Loading embedding model (intfloat/multilingual-e5-small)…")
    
    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        os.system(f'"{sys.executable}" -m pip install sentence-transformers chromadb -q')
        from sentence_transformers import SentenceTransformer
        import chromadb
        from chromadb.config import Settings

    model  = SentenceTransformer("intfloat/multilingual-e5-small")
    client = chromadb.PersistentClient(path=str(DB_DIR),
                                       settings=Settings(anonymized_telemetry=False))

    try:
        client.delete_collection("purana_verses")
    except Exception:
        pass
    col = client.create_collection("purana_verses", metadata={"hnsw:space": "cosine"})

    BATCH = 64
    indexed = 0
    for i in range(0, len(all_chunks), BATCH):
        batch = all_chunks[i:i+BATCH]
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

        embeddings = model.encode(texts, batch_size=BATCH,
                                  show_progress_bar=False,
                                  normalize_embeddings=True).tolist()
        col.upsert(ids=ids, embeddings=embeddings,
                   documents=[c.get("text","") for c in batch], metadatas=metas)
        indexed += len(batch)
        if indexed % 1280 == 0 or indexed == len(all_chunks):
            print(f"  {indexed:,}/{len(all_chunks):,} chunks indexed…", flush=True)

    print(f"  ✓  Vector index: {indexed:,} documents in ChromaDB")


def main():
    print("\n🕉️  PuranGPT — GRETIL Extract & Index Pipeline")
    print("=" * 55)

    if not RAW_DIR.exists():
        print(f"Directory {RAW_DIR} not found. Run fetch_gretil.py first.")
        return

    all_chunks = []
    
    text_dirs = sorted([d for d in RAW_DIR.iterdir() if d.is_dir()])
    
    for text_dir in text_dirs:
        txt_files = list(text_dir.glob("*.txt"))
        if not txt_files: continue
        
        txt_path = txt_files[0]
        text_id = text_dir.name
        meta = get_metadata(text_dir)
        
        chunk_file = CHUNKS_DIR / f"{text_id}.jsonl"
        if chunk_file.exists() and chunk_file.stat().st_size > 1000:
            print(f"\n⏭  {meta.get('name', text_id)} — loading cached chunks")
            with open(chunk_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        all_chunks.append(json.loads(line))
            continue
            
        chunks = chunk_text(txt_path, text_id, meta)
        
        if chunks:
            with open(chunk_file, "w", encoding="utf-8") as f:
                for c in chunks:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
            all_chunks.extend(chunks)
            print(f"  Saved {len(chunks):,} chunks → {chunk_file.name}")
            
    if not all_chunks:
        print("\nNo text could be extracted.")
        return

    # Save master chunks file
    master_file = CHUNKS_DIR / "all_chunks.jsonl"
    with open(master_file, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\n✓ Total chunks: {len(all_chunks):,}")

    # Build indexes
    build_bm25_index(all_chunks)
    build_vector_index(all_chunks)

    print(f"\n{'='*55}")
    print(f"✅ Indexing complete!")
    print(f"   Texts:  {len(set(c.get('purana', '') for c in all_chunks))}")
    print(f"   Chunks: {len(all_chunks):,}")

if __name__ == "__main__":
    main()
