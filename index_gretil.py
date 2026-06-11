"""
PuranGPT — GRETIL Auto-Indexer
Chunks plain-text Sanskrit from GRETIL and builds ChromaDB + BM25 indexes.
"""

from __future__ import annotations

import json
import os
import pickle
import re
import sys
from typing import Optional
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
DANDA_RE   = re.compile(r'[।॥]|/{1,2}')
VERSE_RE   = re.compile(r'\b(\d+)\s*[.|,]\s*(\d+)\b') # E.g., 1.15

# Chapter detection regexes — checked in priority order
# 1. GRETIL standard: % chapter {N}
_CH_GRETIL     = re.compile(r'%\s*chapter\s*\{(\d+)\}', re.IGNORECASE)
# 2. "Book N  Chapter N" (Mahabharata online format)
_CH_BOOK       = re.compile(r'Book\s+\d+\s+Chapter\s+(\d+)', re.IGNORECASE)
# 3. IAST / transliterated chapter keyword + number (adhyāya, adhyaya, Chapter, Sarga, etc.)
_CH_ADHYAYA    = re.compile(
    r'(?:adhy[\u0101a][y]a[h\u1e25]?|chapter|sarga|k[\u0101a][n\u1e47][\u1e0da]a|parva|skandha|samhit[\u0101a]|khanda)\s+(\d+)',
    re.IGNORECASE,
)
# 4. Devanagari chapter/section markers
_CH_DEVA       = re.compile(r'(?:अध्याय|स्कन्ध|काण्ड|पर्व|सर्ग|खण्ड)\s*([\u0966-\u096F\d]+)')
# 5. GRETIL inline citation codes: prefix_CHAPTER.verse  (e.g. ap_1.001ab, mbh_01.001, garp_1,1.5)
_CH_CITATION   = re.compile(r'\b[a-z]{2,5}_([\d\.,]+)')

# Devanagari digit → ASCII digit translation
_DEVA_TO_ASCII = str.maketrans('०१२३४५६७८९', '0123456789')

# Known copyright/metadata keywords — lines containing these are filtered out
_HEADER_KEYWORDS = frozenset([
    'copyright', 'creative commons', 'gretil', 'göttingen', 'gottingen',
    'e-text', 'digitized', 'bibliotheca indica', 'database', 'licence',
    'license', 'permission', 'mailto:', 'input by', 'distributed under',
    'encoded by', 'ascii', 'unicode', 'encoding', 'revision', 'version',
    'editorial', 'sub göttingen', 'sub.uni-goettingen', 'tei encoding',
    'mass conversion', 'corpus from', 'provid', 'good faith',
])

def _detect_chapter(line: str) -> int | None:
    """
    Return the chapter number from a line, or None if no chapter marker found.
    Checks five patterns in priority order.
    """
    # Normalise Devanagari digits to ASCII for numeric parsing
    line_n = line.translate(_DEVA_TO_ASCII)

    for regex in (_CH_GRETIL, _CH_BOOK, _CH_ADHYAYA):
        m = regex.search(line_n)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

    # Devanagari chapter markers (search original line for Devanagari, parse normalised)
    m = _CH_DEVA.search(line)
    if m:
        try:
            return int(m.group(1).translate(_DEVA_TO_ASCII))
        except ValueError:
            pass

    return None


def _chapter_from_citation(line: str) -> int | None:
    """Extract chapter number from a GRETIL inline citation code."""
    m = _CH_CITATION.search(line)
    if m:
        parts = re.split(r'[,\.]', m.group(1))
        parts = [p for p in parts if p]
        
        # If there are multiple numeric components (e.g., skandha, chapter, verse)
        # the chapter is generally the second-to-last part.
        if len(parts) >= 2:
            try:
                # Strip non-digits from the end (e.g. '001ab' or '*')
                chap_str = re.sub(r'\D+$', '', parts[-2])
                return int(chap_str)
            except ValueError:
                pass
    return None


def _strip_header(full_text: str) -> str:
    """
    Strip the GRETIL file header, keeping only the body text.

    GRETIL files start with a '# Header' block and mark the text body with
    '# Text'.  If that marker is absent (non-GRETIL sources), fall back to
    removing any line that looks like metadata/copyright boilerplate.
    """
    # Primary: find '# Text' section marker and discard everything before it
    text_marker = re.search(r'^\s*#\s*Text\s*$', full_text, re.MULTILINE)
    if text_marker:
        return full_text[text_marker.end():].lstrip('\n')

    # Fallback: strip lines that are clearly metadata
    lines = full_text.splitlines()
    cleaned = []
    for line in lines:
        low = line.lower()
        if any(kw in low for kw in _HEADER_KEYWORDS):
            continue
        # Strip markdown-style header lines (## ...) that GRETIL uses for metadata
        if re.match(r'^\s*#{1,3}\s', line) and len(line) < 200:
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)

def get_metadata(text_dir: Path) -> dict:
    """Load provenance metadata if available."""
    meta_path = text_dir / "provenance.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def chunk_text(txt_path: Path, text_id: str, meta: dict) -> list[dict]:
    """Read text, split by verses, chunk, and return dicts."""
    purana_name = meta.get("name", text_id.replace("_", " ").title())
    print(f"\n📖 Chunking: {purana_name}")

    with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
        full_text = f.read()

    # Strip GRETIL / metadata headers, keep only body text
    full_text = _strip_header(full_text)

    chunks: list[dict] = []

    # Danda-based (Sanskrit/Hindi verse) vs line-based (prose/HTML) chunking
    has_dandas = '।' in full_text or '॥' in full_text or '/' in full_text

    current_chapter = 0
    verse_num       = 0
    text_buffer: list[str] = []
    line_buffer: list[int] = []

    lines = full_text.splitlines()

    def _make_chunk(buf: list[str], lbuf: list[int], separator: str) -> None:
        nonlocal verse_num, current_chapter
        verse_num += 1
        chunk_body = separator.join(buf)
        if separator == ' । ':
            chunk_body += ' ॥'
        chunk_id = f"{text_id}-{current_chapter}-{verse_num}"
        section  = f"Chapter {current_chapter}" if current_chapter else ""
        chunks.append({
            "id":           chunk_id,
            "purana":       purana_name,
            "category":     meta.get("tradition", "other"),
            "book_section": section,
            "chapter":      current_chapter,
            "verse_range":  str(verse_num),
            "text":         chunk_body[:1200],
            "language":     "sanskrit",
            "source_file":  txt_path.name,
            "source_page":  lbuf[0] if lbuf else 0,
            "word_count":   len(chunk_body.split()),
        })

    if has_dandas:
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # --- Chapter detection (parse actual number, never increment blindly) ---
            ch = _detect_chapter(line)
            if ch is not None and ch > 0:
                current_chapter = ch
            else:
                # Fallback: extract chapter from GRETIL inline citation code
                ch_cite = _chapter_from_citation(line)
                if ch_cite is not None and ch_cite > 0:
                    current_chapter = ch_cite

            for part in DANDA_RE.split(line):
                part = part.strip()
                if len(part) < 10:
                    continue
                text_buffer.append(part)
                line_buffer.append(i + 1)

                if len(text_buffer) >= 3:
                    _make_chunk(text_buffer, line_buffer, ' । ')
                    text_buffer = text_buffer[-1:]   # 1-verse overlap
                    line_buffer = line_buffer[-1:]

        if text_buffer:
            _make_chunk(text_buffer, line_buffer, ' । ')

    else:
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            ch = _detect_chapter(line)
            if ch is not None and ch > 0:
                current_chapter = ch
                continue  # chapter-header lines are not content
            else:
                ch_cite = _chapter_from_citation(line)
                if ch_cite is not None and ch_cite > 0:
                    current_chapter = ch_cite

            text_buffer.append(line)
            line_buffer.append(i + 1)

            if len(text_buffer) >= 5:
                _make_chunk(text_buffer, line_buffer, '\n')
                text_buffer = text_buffer[-2:]   # 2-line overlap
                line_buffer = line_buffer[-2:]

        if text_buffer:
            _make_chunk(text_buffer, line_buffer, '\n')

    print(f"  ✓  {len(chunks):,} chunks  (chapters detected: "
          f"{len({c['chapter'] for c in chunks if c['chapter'] > 0})})")
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

    all_chunks: list[dict] = []

    text_dirs = sorted([d for d in RAW_DIR.iterdir() if d.is_dir()])

    for text_dir in text_dirs:
        txt_files = list(text_dir.glob("*.txt"))
        if not txt_files:
            continue

        txt_path = txt_files[0]
        text_id  = text_dir.name
        meta     = get_metadata(text_dir)

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
    # Build indexes (delegated to build_index.py for incremental safety)
    # build_bm25_index(all_chunks)
    # build_vector_index(all_chunks)

    print(f"\n{'='*55}")
    print(f"✅ Indexing complete!")
    print(f"   Texts:  {len(set(c.get('purana', '') for c in all_chunks))}")
    print(f"   Chunks: {len(all_chunks):,}")

if __name__ == "__main__":
    main()
