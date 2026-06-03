"""
PuranGPT — Shailendra Sharma Book Ingestion
=============================================
Ingests purchased PDF/EPUB books by Sri Sri Shailendra Sharma into
the RAG corpus so PuranGPT can cite them with full attribution.

USAGE:
    1. Purchase books at: https://shailendrasharmabooks.com
    2. Place PDFs in:  purangpt/data/sharma_books/
    3. Run:  python ingest_sharma_books.py
    4. Then: python run.py --index   (rebuilds the vector index)

BOOKS TO ACQUIRE (in priority order for this research system):
  ┌─────────────────────────────────────────┬────────────────────────────────┐
  │ Book                                    │ Relevance                      │
  ├─────────────────────────────────────────┼────────────────────────────────┤
  │ Yogeshwari (Bhagavad Gita commentary)   │ Highest — yogic Gita exegesis  │
  │ Yoga Darshan (Patanjali commentary)     │ High — Yoga Sutra insights     │
  │ Shiv Sutra (Kashmir Shaivism)           │ High — Trika Shaivism          │
  │ Hatha Yoga Pradipika (commentary)       │ High — Nath tradition          │
  │ Gorakh Bodh (Gorakhnath commentary)     │ High — Nath lineage            │
  │ Upanishad of Immortality                │ Medium — Kriya Yoga Q&A        │
  │ At the Right Hand of God                │ Medium — discourse collection  │
  │ The Twilight Language of Gorakh Bodh    │ Medium — Nath symbolism        │
  └─────────────────────────────────────────┴────────────────────────────────┘

Expected filenames (rename your PDFs to match):
  yogeshwari_bhagavad_gita.pdf
  yoga_darshan.pdf
  shiv_sutra.pdf
  hatha_yoga_pradipika_sharma.pdf
  gorakh_bodh.pdf
  upanishad_of_immortality.pdf
  at_the_right_hand_of_god.pdf
  twilight_language_gorakh_bodh.pdf

Note: These are copyrighted works. This script is for personal research use
with legitimately purchased copies only.
"""

from __future__ import annotations
import json
import re
import sys
import hashlib
import logging
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Install PyMuPDF first:  pip install pymupdf")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger("sharma_ingest")

BASE        = Path(__file__).parent
SHARMA_DIR  = BASE / "data/sharma_books"
CHUNKS_DIR  = BASE / "data/chunks"

# Metadata for each book
BOOK_META = {
    "yogeshwari_bhagavad_gita": {
        "name":      "Yogeshwari — Shrimad Bhagavad Gita",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "kriya-yoga",
        "category":  "yogic-commentary",
        "bias":      "✅ Yogiraj Shailendra Sharma",
        "edition":   "Shailendra Sharma Books (official)",
        "language":  "English/Hindi",
        "note":      "Yogic commentary revealing experiential meaning of the Gita",
    },
    "yoga_darshan": {
        "name":      "Yoga Darshan — Commentary on Patanjali's Yoga Sutras",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "kriya-yoga",
        "category":  "yogic-commentary",
        "bias":      "✅ Yogiraj Shailendra Sharma",
        "edition":   "Shailendra Sharma Books (official)",
        "language":  "English/Hindi",
        "note":      "Experiential commentary on Patanjali's 196 aphorisms",
    },
    "shiv_sutra": {
        "name":      "Shiv Sutra — Kashmir Shaivism",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "shaiva",
        "category":  "yogic-commentary",
        "bias":      "✅ Yogiraj Shailendra Sharma",
        "edition":   "Shailendra Sharma Books (official)",
        "language":  "English/Hindi",
        "note":      "Commentary on Vasugupta's Shiva Sutras from yogic practice",
    },
    "hatha_yoga_pradipika_sharma": {
        "name":      "Hatha Yoga Pradipika — Sharma Commentary",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "nath",
        "category":  "yogic-commentary",
        "bias":      "✅ Yogiraj Shailendra Sharma",
        "edition":   "Shailendra Sharma Books (official)",
        "language":  "English/Hindi",
        "note":      "Traditional Nath lineage commentary on Swatmarama's text",
    },
    "gorakh_bodh": {
        "name":      "Gorakh Bodh — Twilight Language Commentary",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "nath",
        "category":  "yogic-commentary",
        "bias":      "✅ Yogiraj Shailendra Sharma",
        "edition":   "Shailendra Sharma Books (official)",
        "language":  "English/Hindi",
        "note":      "Nath tradition commentary revealing hidden yogic symbolism",
    },
    "upanishad_of_immortality": {
        "name":      "Upanishad of Immortality",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "kriya-yoga",
        "category":  "discourse",
        "bias":      "✅ Yogiraj Shailendra Sharma",
        "edition":   "Shailendra Sharma Books (official)",
        "language":  "English",
        "note":      "Dialogues on yoga, self-realization and immortality",
    },
    "at_the_right_hand_of_god": {
        "name":      "At the Right Hand of God",
        "author":    "Sri Sri Shailendra Sharma",
        "tradition": "kriya-yoga",
        "category":  "discourse",
        "bias":      "✅ Yogiraj Shailendra Sharma",
        "edition":   "Shailendra Sharma Books (official)",
        "language":  "English",
        "note":      "Twenty years of daily discussions on Kriya Yoga and consciousness",
    },
}


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """Extract page-level text from PDF using PyMuPDF."""
    pages = []
    try:
        doc = fitz.open(str(pdf_path))
        for page_num, page in enumerate(doc, 1):
            text = page.get_text("text")
            if text.strip():
                pages.append({
                    "page":    page_num,
                    "text":    text.strip(),
                    "chars":   len(text),
                })
        doc.close()
        log.info("  Extracted %d pages, %d chars total",
                 len(pages), sum(p["chars"] for p in pages))
    except Exception as e:
        log.error("  Failed to extract %s: %s", pdf_path.name, e)
    return pages


def chunk_pages(pages: list[dict], book_key: str, meta: dict,
                chunk_size: int = 800, overlap: int = 100) -> list[dict]:
    """
    Chunk extracted pages into RAG-ready pieces.
    Splits on paragraph/section boundaries, targeting ~800 chars per chunk.
    """
    chunks = []
    full_text = "\n\n".join(p["text"] for p in pages)

    # Split into paragraphs first
    paragraphs = re.split(r'\n\s*\n', full_text)
    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 30]

    buffer = ""
    page_est = 1
    chapter = "Introduction"

    # Detect chapter headings
    chapter_pat = re.compile(
        r'^(?:Chapter|Adhyaya|Part|Section|Book|Shloka|Verse|Sutra)\s+[\dIVXivx]+|'
        r'^[\dIVXivx]+\.\s+[A-Z]',
        re.MULTILINE | re.IGNORECASE
    )

    for para in paragraphs:
        # Update chapter if heading detected
        m = chapter_pat.match(para)
        if m and len(para) < 120:
            chapter = para[:80].strip()

        buffer += para + "\n\n"

        if len(buffer) >= chunk_size:
            chunk_id = hashlib.md5(f"{book_key}:{buffer[:60]}".encode()).hexdigest()[:12]
            chunks.append({
                "id":           f"sharma-{book_key}-{chunk_id}",
                "purana":       meta["name"],
                "author":       meta["author"],
                "tradition":    meta["tradition"],
                "category":     meta["category"],
                "book_section": chapter,
                "chapter":      chapter,
                "verse_range":  "",
                "text":         buffer[:chunk_size + overlap].strip(),
                "language":     meta["language"],
                "source_file":  pdf_path.name if 'pdf_path' in dir() else book_key,
                "source_page":  page_est,
                "word_count":   len(buffer.split()),
                "edition":      meta["edition"],
                "bias":         meta["bias"],
                "note":         meta["note"],
            })
            # Keep overlap
            buffer = buffer[chunk_size:]
            page_est += 1

    # Final buffer
    if buffer.strip() and len(buffer.strip()) > 100:
        chunk_id = hashlib.md5(f"{book_key}:{buffer[:60]}".encode()).hexdigest()[:12]
        chunks.append({
            "id":           f"sharma-{book_key}-{chunk_id}",
            "purana":       meta["name"],
            "author":       meta["author"],
            "tradition":    meta["tradition"],
            "category":     meta["category"],
            "book_section": chapter,
            "chapter":      chapter,
            "verse_range":  "",
            "text":         buffer.strip(),
            "language":     meta["language"],
            "source_file":  book_key,
            "source_page":  page_est,
            "word_count":   len(buffer.split()),
            "edition":      meta["edition"],
            "bias":         meta["bias"],
            "note":         meta["note"],
        })

    return chunks


def ingest_book(pdf_path: Path) -> int:
    """Ingest a single book PDF. Returns number of chunks created."""
    stem = pdf_path.stem
    meta = BOOK_META.get(stem)

    if not meta:
        # Try fuzzy match
        for key in BOOK_META:
            if key in stem or stem in key:
                meta = BOOK_META[key]
                stem = key
                break

    if not meta:
        log.warning("No metadata for %s — skipping. Add an entry to BOOK_META.", pdf_path.name)
        return 0

    log.info("\n▶ Ingesting: %s", meta["name"])
    log.info("  File: %s", pdf_path.name)

    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        return 0

    chunks = chunk_pages(pages, stem, meta)
    log.info("  Created %d chunks", len(chunks))

    # Write to JSONL
    out_path = CHUNKS_DIR / f"sharma_{stem}.jsonl"
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # Also append to all_chunks.jsonl
    all_chunks = CHUNKS_DIR / "all_chunks.jsonl"
    with open(all_chunks, "a", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    log.info("  Written to: %s", out_path)
    return len(chunks)


def main():
    SHARMA_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = list(SHARMA_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"""
No PDFs found in: {SHARMA_DIR}

NEXT STEPS:
1. Purchase books at https://shailendrasharmabooks.com
2. Place the PDFs in: {SHARMA_DIR}
3. Rename them to match these filenames:
   • yogeshwari_bhagavad_gita.pdf
   • yoga_darshan.pdf
   • shiv_sutra.pdf
   • hatha_yoga_pradipika_sharma.pdf
   • gorakh_bodh.pdf
   • upanishad_of_immortality.pdf
   • at_the_right_hand_of_god.pdf
4. Run this script again:  python ingest_sharma_books.py
5. Then rebuild the index: python run.py --index
""")
        return

    total = 0
    for pdf in pdfs:
        total += ingest_book(pdf)

    print(f"\n✓ Done — {total} chunks from {len(pdfs)} books.")
    print("Now run:  python run.py --index   to add them to the vector index.")


if __name__ == "__main__":
    main()
