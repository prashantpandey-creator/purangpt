"""
chunk_sharma_texts.py — Chunk Guruji Shailendra Sharma's published texts into
the pgvector-ready JSONL format used by indexer/pg_ingest.py.

Texts processed:
  - yogeshwari_gita_full.txt  (545 KB — full Yogic Gita commentary)
  - shiv_sutra.txt            (Shiv Sutra commentary)
  - gorakh_bodh.txt           (Gorakh Bodh commentary)
  - ojas_amrita.txt           (Ojas & Amrita darshan)
  - yoga_alchemy.txt          (Yoga & Alchemy darshan)
  - khechari_vidya.txt        (Khechari Vidya darshan)
  - yogeshwari_gita.txt       (short version)

Produces: data/chunks/sharma_texts.jsonl

Then run:  VECTOR_DB_URL=... python3 -m indexer.pg_ingest --chunks-dir data/chunks/
"""
from __future__ import annotations
import json, hashlib, re, sys
from pathlib import Path

SHARMA_DIR = Path("data/raw_texts/sharma")
OUT_FILE   = Path("data/chunks/sharma_texts.jsonl")

CHUNK_SIZE   = 600    # target chars per chunk
CHUNK_OVERLAP = 80    # char overlap between consecutive chunks

TEXT_CONFIGS = [
    {
        "file": "yogeshwari_gita_full.txt",
        "source": "Yogeshwari Srimad Bhagavad Gita (Shailendra Sharma Commentary)",
        "tradition": "Kriya Yoga / Yogic Commentary",
        "text_name": "Yogeshwari Gita",
        "author": "Shailendra Sharma",
    },
    {
        "file": "shiv_sutra.txt",
        "source": "Shiv Sutra Commentary (Shailendra Sharma)",
        "tradition": "Kashmir Shaivism / Kriya Yoga",
        "text_name": "Shiv Sutra",
        "author": "Shailendra Sharma",
    },
    {
        "file": "gorakh_bodh.txt",
        "source": "Gorakh Bodh Commentary (Shailendra Sharma)",
        "tradition": "Nath / Kriya Yoga",
        "text_name": "Gorakh Bodh",
        "author": "Shailendra Sharma",
    },
    {
        "file": "ojas_amrita.txt",
        "source": "Ojas & Amrita — Shailendra Sharma Darshan",
        "tradition": "Kriya Yoga / Nath",
        "text_name": "Ojas Amrita",
        "author": "Shailendra Sharma",
    },
    {
        "file": "yoga_alchemy.txt",
        "source": "Yoga & Alchemy — Shailendra Sharma Darshan",
        "tradition": "Kriya Yoga / Rasayana",
        "text_name": "Yoga Alchemy",
        "author": "Shailendra Sharma",
    },
    {
        "file": "khechari_vidya.txt",
        "source": "Khechari Vidya — Shailendra Sharma Darshan",
        "tradition": "Nath / Kriya Yoga",
        "text_name": "Khechari Vidya",
        "author": "Shailendra Sharma",
    },
]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks on paragraph/sentence boundaries."""
    # Clean excessive whitespace but preserve paragraph breaks
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    paragraphs = re.split(r'\n\n+', text)

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If paragraph fits in current chunk, add it
        if len(current) + len(para) + 2 <= size:
            current = (current + "\n\n" + para).strip()
        else:
            # Save current chunk if non-empty
            if current:
                chunks.append(current)
                # Start new chunk with overlap: keep last overlap chars of current
                current = current[-overlap:].strip() + "\n\n" + para
            else:
                # Single paragraph too large — split by sentence
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= size:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            chunks.append(current)
                            current = current[-overlap:].strip() + " " + sent
                        else:
                            # Sentence too long — hard split
                            for i in range(0, len(sent), size - overlap):
                                chunks.append(sent[i:i+size])
                            current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks


def make_chunk_id(source_key: str, idx: int) -> str:
    return hashlib.md5(f"{source_key}::{idx}".encode()).hexdigest()


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    total = 0

    with open(OUT_FILE, "w", encoding="utf-8") as fout:
        for cfg in TEXT_CONFIGS:
            fpath = SHARMA_DIR / cfg["file"]
            if not fpath.exists():
                print(f"[SKIP] {cfg['file']} not found", file=sys.stderr)
                continue

            raw = fpath.read_text(encoding="utf-8")
            # Strip header lines (source/tradition metadata at top)
            lines = raw.split("\n")
            content_start = 0
            for i, line in enumerate(lines[:10]):
                if line.startswith("Source:") or line.startswith("Tradition:") or line.strip() in ("", cfg.get("text_name", "")):
                    content_start = i + 1
            text = "\n".join(lines[content_start:]).strip()

            chunks = chunk_text(text)
            source_key = cfg["file"].replace(".txt", "")

            for idx, chunk in enumerate(chunks):
                if len(chunk.strip()) < 30:
                    continue  # skip tiny fragments
                record = {
                    "id": make_chunk_id(source_key, idx),
                    "text": chunk.strip(),
                    "metadata": {
                        "source": cfg["source"],
                        "tradition": cfg["tradition"],
                        "text_name": cfg["text_name"],
                        "author": cfg["author"],
                        "chunk_index": idx,
                        "is_guruji_text": True,  # flag for personality-RAG future use
                    }
                }
                fout.write(json.dumps(record, ensure_ascii=False) + "\n")
                total += 1

            print(f"[OK] {cfg['file']:40s}  {len(chunks):4d} chunks")

    print(f"\nTotal chunks written: {total} → {OUT_FILE}")
    print("\nNext: VECTOR_DB_URL=<your_url> python3 -m indexer.pg_ingest --chunks-dir data/chunks/")


if __name__ == "__main__":
    main()
