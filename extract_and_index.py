"""
PuranGPT — PDF Extractor + Auto-Indexer
Extracts text from downloaded PDFs using PyMuPDF, chunks them,
then builds the ChromaDB + BM25 indexes.
Run after fetch_texts.py completes.
"""

import json, pickle, re, sys, os, time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

RAW_DIR    = Path("data/raw_pdfs")
CHUNKS_DIR = Path("data/chunks")
INDEX_DIR  = Path("data/indexes")
DB_DIR     = Path("data/chroma_db")

CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

# Shloka boundary patterns
DANDA_RE   = re.compile(r'[।॥]')
CHAPTER_RE = re.compile(r'(?:अध्याय|Chapter|CHAPTER|Adhyaya)\s*[\d०-९]+', re.IGNORECASE)
VERSE_RE   = re.compile(r'^\s*[\d०-९]+[-–]\d+', re.MULTILINE)


def devanagari_to_int(s):
    """Convert Devanagari digit string to int."""
    mapping = str.maketrans('०१२३४५६७८९', '0123456789')
    return int(s.translate(mapping)) if s else 0


def extract_pdf(pdf_path: Path, text_id: str, purana_name: str) -> list[dict]:
    """Extract text from PDF and return list of chunk dicts."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("  Installing PyMuPDF…")
        os.system(f"{sys.executable} -m pip install PyMuPDF -q")
        import fitz

    chunks = []
    try:
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        print(f"  Pages: {total_pages}")

        current_chapter = 0
        verse_num       = 0
        text_buffer     = []
        page_buffer     = []

        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text("text")

            if not text.strip():
                continue

            # Detect chapter markers
            ch_match = CHAPTER_RE.search(text)
            if ch_match:
                current_chapter += 1

            # Split on danda (verse boundaries)
            parts = DANDA_RE.split(text)
            for part in parts:
                part = part.strip()
                if len(part) < 15:
                    continue
                text_buffer.append(part)
                page_buffer.append(page_num + 1)

                # Create a chunk every 3 verses
                if len(text_buffer) >= 3:
                    verse_num += 1
                    chunk_text = ' । '.join(text_buffer) + ' ॥'
                    chunk_id   = f"{text_id}-{current_chapter}-{verse_num}"

                    chunks.append({
                        "id":          chunk_id,
                        "purana":      purana_name,
                        "category":    _get_category(text_id),
                        "book_section": f"Chapter {current_chapter}" if current_chapter else "",
                        "chapter":     current_chapter,
                        "verse_range": str(verse_num),
                        "text":        chunk_text[:1200],
                        "language":    detect_language(chunk_text),
                        "source_file": pdf_path.name,
                        "source_page": page_buffer[0],
                        "word_count":  len(chunk_text.split()),
                    })
                    text_buffer = text_buffer[-1:]  # 1-verse overlap
                    page_buffer = page_buffer[-1:]

        # Flush remaining buffer
        if len(text_buffer) >= 1:
            verse_num += 1
            chunk_text = ' । '.join(text_buffer)
            chunk_id   = f"{text_id}-{current_chapter}-{verse_num}"
            chunks.append({
                "id": chunk_id, "purana": purana_name,
                "category": _get_category(text_id),
                "chapter": current_chapter,
                "verse_range": str(verse_num),
                "text": chunk_text[:1200],
                "language": detect_language(chunk_text),
                "source_file": pdf_path.name,
                "source_page": page_buffer[0] if page_buffer else 0,
                "word_count": len(chunk_text.split()),
            })

        doc.close()
        print(f"  ✓  Extracted {len(chunks)} chunks")
    except Exception as e:
        print(f"  ✗  Extraction error: {e}")

    return chunks


def detect_language(text: str) -> str:
    devanagari = len(re.findall(r'[\u0900-\u097F]', text))
    latin       = len(re.findall(r'[a-zA-Z]', text))
    if devanagari > latin:
        return "hindi"
    return "english"


def _get_category(text_id: str) -> str:
    mahapuranas = {"agni","bhagavata","bhavishya","brahma","brahmanda",
                   "brahma_vaivarta","garuda","kurma","linga","markandeya",
                   "matsya","narada","padma","shiva","skanda","vamana","varaha","vishnu"}
    if text_id in mahapuranas: return "mahapurana"
    if text_id in {"ramayana","mahabharata","bhagavad_gita"}: return "epic"
    if text_id in {"yoga_sutras","hatha_yoga","yoga_vasistha"}: return "yoga"
    if text_id in {"upanishads"}: return "upanishad"
    return "other"


PURANA_NAMES = {
    "agni":           "Agni Purana",
    "bhagavata":      "Bhagavata Purana",
    "bhavishya":      "Bhavishya Purana",
    "brahma":         "Brahma Purana",
    "brahmanda":      "Brahmanda Purana",
    "brahma_vaivarta":"Brahma Vaivarta Purana",
    "garuda":         "Garuda Purana",
    "kurma":          "Kurma Purana",
    "linga":          "Linga Purana",
    "markandeya":     "Markandeya Purana",
    "matsya":         "Matsya Purana",
    "narada":         "Narada Purana",
    "padma":          "Padma Purana",
    "shiva":          "Shiva Purana",
    "skanda":         "Skanda Purana",
    "vamana":         "Vamana Purana",
    "varaha":         "Varaha Purana",
    "vishnu":         "Vishnu Purana",
    "bhagavad_gita":  "Bhagavad Gita",
    "ramayana":       "Valmiki Ramayana",
    "mahabharata":    "Mahabharata",
    "yoga_sutras":    "Yoga Sutras of Patanjali",
    "hatha_yoga":     "Hatha Yoga Pradipika",
    "upanishads":     "Principal Upanishads",
}


def build_bm25_index(all_chunks: list[dict]):
    """Build BM25 sparse keyword index."""
    print("\n📊 Building BM25 keyword index…")
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        os.system(f"{sys.executable} -m pip install rank-bm25 -q")
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
    print("  (First time downloads ~500MB — subsequent runs use cache)")

    try:
        from sentence_transformers import SentenceTransformer
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        os.system(f"{sys.executable} -m pip install sentence-transformers chromadb -q")
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
            "language":    c.get("language","hindi"),
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
        print(f"  {indexed:,}/{len(all_chunks):,} chunks indexed…", flush=True)

    print(f"  ✓  Vector index: {indexed:,} documents in ChromaDB")


def main():
    print("\n🕉️  PuranGPT — Extract & Index Pipeline")
    print("=" * 55)

    # Collect all PDFs
    pdf_dirs = sorted(RAW_DIR.iterdir()) if RAW_DIR.exists() else []
    if not pdf_dirs:
        print("No PDFs found. Run: python fetch_texts.py first")
        return

    all_chunks = []

    # Extract text from each PDF
    for text_dir in pdf_dirs:
        if not text_dir.is_dir():
            continue
        pdfs = list(text_dir.glob("*.pdf"))
        if not pdfs:
            continue

        text_id = text_dir.name
        name    = PURANA_NAMES.get(text_id, text_id.replace("_"," ").title())

        # Check if already chunked
        chunk_file = CHUNKS_DIR / f"{text_id}.jsonl"
        if chunk_file.exists() and chunk_file.stat().st_size > 1000:
            print(f"\n⏭  {name} — loading cached chunks")
            with open(chunk_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        all_chunks.append(json.loads(line))
            continue

        print(f"\n📖 Extracting: {name}")
        pdf_path = pdfs[0]
        chunks   = extract_pdf(pdf_path, text_id, name)

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
    print(f"   Texts:  {len(set(c['purana'] for c in all_chunks))}")
    print(f"   Chunks: {len(all_chunks):,}")
    print(f"\nRestart the server to activate RAG: python run.py")


if __name__ == "__main__":
    main()
