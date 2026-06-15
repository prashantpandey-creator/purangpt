"""
PuranGPT — Sharma Raw Text Indexer
====================================
Indexes the raw .txt Shailendra Sharma files from data/raw_texts/sharma/
into ChromaDB + BM25, without clearing or rebuilding any existing data.

Files expected in data/raw_texts/sharma/:
  gorakh_bodh.txt         - Gorakh Bodh (Nath tradition)
  khechari_vidya.txt      - Khechari Vidya
  ojas_amrita.txt         - Ojas & Amrita
  shiv_sutra.txt          - Shiv Sutra (Kashmir Shaivism)
  yoga_alchemy.txt        - Yoga & Alchemy
  yogeshwari_gita.txt     - Yogeshwari (Bhagavad Gita yogic commentary)

Run: python index_sharma_texts.py
"""
from __future__ import annotations
import json, re, hashlib, logging, pickle, sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger("sharma_indexer")

BASE         = Path(__file__).parent
SHARMA_DIR   = BASE / "data/raw_texts/sharma"
CHUNKS_DIR   = BASE / "data/chunks"
INDEX_DIR    = BASE / "data/indexes"
CHROMA_DIR   = BASE / "data/chroma_db"

# ── Book metadata ─────────────────────────────────────────────────────────────
BOOK_META = {
    "gorakh_bodh": {
        "name":      "Gorakh Bodh — Shailendra Sharma Commentary",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "nath",
        "category":  "yogic-commentary",
        "language":  "English",
    },
    "khechari_vidya": {
        "name":      "Khechari Vidya — Shailendra Sharma",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "nath",
        "category":  "yogic-commentary",
        "language":  "English",
    },
    "ojas_amrita": {
        "name":      "Ojas & Amrita — Shailendra Sharma",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "kriya-yoga",
        "category":  "yogic-commentary",
        "language":  "English",
    },
    "shiv_sutra": {
        "name":      "Shiv Sutra — Kashmir Shaivism (Shailendra Sharma)",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "shaiva",
        "category":  "yogic-commentary",
        "language":  "English",
    },
    "yoga_alchemy": {
        "name":      "Yoga & Alchemy — Shailendra Sharma",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "kriya-yoga",
        "category":  "yogic-commentary",
        "language":  "English",
    },
    "yogeshwari_gita": {
        "name":      "Yogeshwari — Bhagavad Gita Commentary (Shailendra Sharma)",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "kriya-yoga",
        "category":  "yogic-commentary",
        "language":  "English",
    },
}


def chunk_text(text: str, book_key: str, meta: dict,
               chunk_size: int = 700, overlap: int = 100) -> list[dict]:
    """Split text into overlapping chunks with rich metadata."""
    chunks = []
    # Split on blank lines (paragraphs)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if len(p.strip()) > 40]

    chapter_pat = re.compile(
        r'^(?:Chapter|Part|Section|Sutra|Verse|Shloka|Book)\s+[\dIVXivx]+|'
        r'^[\dIVXivx]+[\.\)]\s+[A-Z]',
        re.MULTILINE | re.IGNORECASE
    )

    buffer   = ""
    chapter  = "Introduction"
    page_est = 1

    for para in paragraphs:
        m = chapter_pat.match(para)
        if m and len(para) < 120:
            chapter = para[:80].strip()

        buffer += para + "\n\n"

        if len(buffer) >= chunk_size:
            cid = hashlib.md5(f"{book_key}:{buffer[:60]}".encode()).hexdigest()[:12]
            chunks.append({
                "id":           f"sharma-{book_key}-{cid}",
                "purana":       meta["name"],
                "author":       meta["author"],
                "tradition":    meta["tradition"],
                "category":     meta["category"],
                "chapter":      chapter,
                "book_section": chapter,
                "verse_range":  "",
                "text":         buffer[:chunk_size + overlap].strip(),
                "language":     meta["language"],
                "source_file":  f"{book_key}.txt",
                "source_page":  page_est,
                "word_count":   len(buffer.split()),
            })
            buffer   = buffer[chunk_size:]
            page_est += 1

    if buffer.strip() and len(buffer.strip()) > 80:
        cid = hashlib.md5(f"{book_key}:{buffer[:60]}".encode()).hexdigest()[:12]
        chunks.append({
            "id":           f"sharma-{book_key}-{cid}",
            "purana":       meta["name"],
            "author":       meta["author"],
            "tradition":    meta["tradition"],
            "category":     meta["category"],
            "chapter":      chapter,
            "book_section": chapter,
            "verse_range":  "",
            "text":         buffer.strip(),
            "language":     meta["language"],
            "source_file":  f"{book_key}.txt",
            "source_page":  page_est,
            "word_count":   len(buffer.split()),
        })

    log.info("  %s → %d chunks", book_key, len(chunks))
    return chunks


def load_all_sharma_chunks() -> list[dict]:
    """Read and chunk all Sharma .txt files."""
    all_chunks: list[dict] = []
    for txt_path in sorted(SHARMA_DIR.glob("*.txt")):
        stem = txt_path.stem
        meta = BOOK_META.get(stem)
        if not meta:
            log.warning("No metadata for %s — skipping", txt_path.name)
            continue
        log.info("Processing %s", txt_path.name)
        text = txt_path.read_text(encoding="utf-8", errors="ignore")
        chunks = chunk_text(text, stem, meta)
        all_chunks.extend(chunks)

        # Save per-book JSONL
        out = CHUNKS_DIR / f"sharma_{stem}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        log.info("  Written → %s", out)
    return all_chunks


def add_to_chroma(chunks: list[dict]) -> None:
    """Embed chunks with multilingual-e5-small and upsert into ChromaDB."""
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        log.error("Missing package: %s  (pip install chromadb sentence-transformers)", e)
        sys.exit(1)

    log.info("Loading embedding model…")
    import os; os.environ["TOKENIZERS_PARALLELISM"] = "false"
    embed_model = SentenceTransformer("intfloat/multilingual-e5-small")

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False)
    )
    col = client.get_or_create_collection("purana_verses")

    # Fetch existing IDs to avoid duplicates
    existing = set(col.get(include=[])["ids"])
    new_chunks = [c for c in chunks if c["id"] not in existing]

    if not new_chunks:
        log.info("All %d Sharma chunks already in ChromaDB — nothing to add.", len(chunks))
        return

    log.info("Embedding and inserting %d new chunks into ChromaDB…", len(new_chunks))
    BATCH = 64
    for i in range(0, len(new_chunks), BATCH):
        batch = new_chunks[i:i+BATCH]
        texts  = [f"passage: {c['text']}" for c in batch]
        embeds = embed_model.encode(texts, normalize_embeddings=True).tolist()
        ids    = [c["id"] for c in batch]
        metas  = []
        for c in batch:
            m = {k: v for k, v in c.items() if k not in ("text",) and isinstance(v, (str, int, float, bool))}
            metas.append(m)
        docs = [c["text"] for c in batch]
        col.add(ids=ids, embeddings=embeds, metadatas=metas, documents=docs)
        log.info("  Inserted batch %d-%d", i+1, i+len(batch))

    log.info("✓ ChromaDB: %d Sharma chunks added. Total now: %d", len(new_chunks), col.count())


def add_to_bm25(new_chunks: list[dict]) -> None:
    """Append Sharma chunks to BM25 index and chunk_map, rebuilding BM25."""
    bm25_path      = INDEX_DIR / "bm25_index.pkl"
    chunk_map_path = INDEX_DIR / "chunk_map.json"

    if not chunk_map_path.exists():
        log.warning("chunk_map.json not found — BM25 update skipped")
        return

    log.info("Loading existing BM25 chunk_map (%s)…", chunk_map_path)
    with open(chunk_map_path) as f:
        chunk_map: list[dict] = json.load(f)

    existing_ids = {c.get("id") for c in chunk_map}
    to_add = [c for c in new_chunks if c["id"] not in existing_ids]

    if not to_add:
        log.info("All Sharma chunks already in chunk_map — BM25 already up to date.")
        return

    log.info("Adding %d new chunks to chunk_map…", len(to_add))
    chunk_map.extend(to_add)

    log.info("Saving updated chunk_map (%d total)…", len(chunk_map))
    with open(chunk_map_path, "w", encoding="utf-8") as f:
        json.dump(chunk_map, f, ensure_ascii=False)

    # Rebuild BM25
    log.info("Rebuilding BM25 index (this may take ~30s)…")
    try:
        from rank_bm25 import BM25Okapi
        import re as _re

        def _tokenize(text: str) -> list[str]:
            tokens = _re.findall(r'[\u0900-\u097F]+|[a-zA-Z]+', text.lower())
            return [t for t in tokens if len(t) > 1]

        corpus = [_tokenize(c.get("text", "")) for c in chunk_map]
        bm25   = BM25Okapi(corpus)

        with open(bm25_path, "wb") as f:
            pickle.dump(bm25, f)
        log.info("✓ BM25 rebuilt: %d docs", len(corpus))
    except ImportError:
        log.warning("rank_bm25 not installed — BM25 update skipped")


def main():
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=== Shailendra Sharma Text Indexer ===")
    log.info("Source dir: %s", SHARMA_DIR)

    txt_files = list(SHARMA_DIR.glob("*.txt"))
    if not txt_files:
        log.error("No .txt files found in %s", SHARMA_DIR)
        sys.exit(1)

    log.info("Found %d Sharma text files: %s",
             len(txt_files), [f.name for f in txt_files])

    # Step 1: Chunk
    all_chunks = load_all_sharma_chunks()
    log.info("Total chunks produced: %d", len(all_chunks))

    # Step 2: Add to ChromaDB (semantic search)
    add_to_chroma(all_chunks)

    # Step 3: Add to BM25 (keyword search)
    add_to_bm25(all_chunks)

    log.info("")
    log.info("✅ Done! Sharma texts are now searchable.")
    log.info("   Restart the backend container to reload the BM25 index:")
    log.info("   docker compose restart backend")


if __name__ == "__main__":
    main()
