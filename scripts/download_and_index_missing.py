import os
import sys
import re
import json
import urllib.request
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexer.build_index import EmbeddingIndexer

CHUNKS_DIR = Path("data/chunks")
DB_DIR = Path("data/chroma_db")
INDEX_DIR = Path("data/indexes")

# Direct download links for the raw OCR txt files from archive.org
MISSING_TEXTS = {
    "brahma_vaivarta": {
        "name": "Brahma Vaivarta Purana",
        "files": [
            {
                "url": "https://ia801507.us.archive.org/16/items/brahma-vaivarta-purana-gitapress-hindi/Brahma%20Vaivarta%20Purana%20-%20Gitapress%20%28Hindi%29_djvu.txt",
                "filename": "brahma_vaivarta_gitapress_hindi.txt",
                "section": "Complete"
            }
        ]
    },
    "bhavishya": {
        "name": "Bhavishya Purana",
        "files": [
            {
                "url": "https://dn720003.ca.archive.org/0/items/evTF_shri-bhavishya-purana-hindi-commentary-by-pt.-shri-durga-prasad-pages-partly-dam/Shri%20Bhavishya%20Purana%20Hindi%20Commentary%20By%20Pt.%20Shri%20Durga%20Prasad%2C%20%28Pages%20Partly%20Damaged%29%2C%201886%2C%20Lucknow%20-%20Munshi%20Naval%20Kishore%20Press%2C%20Lucknow_djvu.txt",
                "filename": "bhavishya_purana_durga_prasad.txt",
                "section": "Complete"
            }
        ]
    },
    "padma": {
        "name": "Padma Purana",
        "files": [
            {
                "url": "https://dn760106.eu.archive.org/0/items/padma-puran-gita-press-gorakhpur/Padma%20Puran%20-%20Gita%20Press%20Gorakhpur_djvu.txt",
                "filename": "padma_puran_gitapress_hindi.txt",
                "section": "Complete"
            }
        ]
    },
    "varaha": {
        "name": "Varaha Purana",
        "files": [
            {
                "url": "https://dn790009.ca.archive.org/0/items/VarahaPurana/varaha_purana_djvu.txt",
                "filename": "varaha_purana_hindi.txt",
                "section": "Complete"
            }
        ]
    },
    "skanda": {
        "name": "Skanda Purana",
        "files": [
            {
                "url": "https://dn720002.ca.archive.org/0/items/Skand-puran/SH-Skand%20Puran%20Kashi%20Khand_djvu.txt",
                "filename": "skanda_kashi_khand.txt",
                "section": "Kashi Khand"
            },
            {
                "url": "https://dn720002.ca.archive.org/0/items/Skand-puran/SH-Skand%20Puran%20Maheshvar%20Khand_djvu.txt",
                "filename": "skanda_maheshvar_khand.txt",
                "section": "Maheshvar Khand"
            },
            {
                "url": "https://dn720002.ca.archive.org/0/items/Skand-puran/SH-Skand%20Puran%20Vaishnav%20Khand_djvu.txt",
                "filename": "skanda_vaishnav_khand.txt",
                "section": "Vaishnav Khand"
            },
            {
                "url": "https://dn720002.ca.archive.org/0/items/Skand-puran/SH-Skand%20Puran%20Brahma%20Khand_djvu.txt",
                "filename": "skanda_brahma_khand.txt",
                "section": "Brahma Khand"
            },
            {
                "url": "https://dn720002.ca.archive.org/0/items/Skand-puran/SH-Skand%20Puran%20Prabhas%20Khand_djvu.txt",
                "filename": "skanda_prabhas_khand.txt",
                "section": "Prabhas Khand"
            },
            {
                "url": "https://dn720002.ca.archive.org/0/items/Skand-puran/SH-Skand%20Puran%20Reva%20Avanti%20Khand_djvu.txt",
                "filename": "skanda_reva_avanti_khand.txt",
                "section": "Reva Avanti Khand"
            },
            {
                "url": "https://dn720002.ca.archive.org/0/items/Skand-puran/SH%20Skandh%20puran%20Nagar%20Khand_djvu.txt",
                "filename": "skanda_nagar_khand.txt",
                "section": "Nagar Khand"
            }
        ]
    }
}

DANDA_RE = re.compile(r'[।॥]')
CHAPTER_RE = re.compile(r'(?:अध्याय|Chapter|CHAPTER|Adhyaya)\s*[\d०-९]+', re.IGNORECASE)

def clean_ocr_text(text: str) -> str:
    """Basic clean up for raw OCR text."""
    # Remove weird characters and OCR artifacts
    text = re.sub(r'[^\w\s\u0900-\u097F।॥\-\.,;:!\?\(\)]', '', text)
    # Collapse multiple spaces and newlines
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    return text

def chunk_txt_file(txt_path: Path, text_id: str, purana_name: str, section_name: str) -> list[dict]:
    """Read a txt file, chunk it using verse-aware (danda) logic, and return list of dicts."""
    print(f"📖 Chunking: {purana_name} - {section_name} ({txt_path.name})")
    
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    content = clean_ocr_text(content)
    lines = content.splitlines()
    
    chunks = []
    current_chapter = 0
    verse_num = 0
    text_buffer = []
    line_buffer = []
    
    # We use danda splitting if they exist, otherwise line-based
    has_dandas = '।' in content or '॥' in content
    
    if has_dandas:
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Detect chapter
            if CHAPTER_RE.search(line):
                current_chapter += 1
                
            parts = DANDA_RE.split(line)
            for part in parts:
                part = part.strip()
                if len(part) < 15:
                    continue
                text_buffer.append(part)
                line_buffer.append(i + 1)
                
                if len(text_buffer) >= 3:
                    verse_num += 1
                    chunk_text = ' । '.join(text_buffer) + ' ॥'
                    chunk_id = f"{text_id}-{section_name.lower().replace(' ', '_')}-{current_chapter}-{verse_num}"
                    
                    chunks.append({
                        "id": chunk_id,
                        "purana": purana_name,
                        "category": "mahapurana",
                        "book_section": f"{section_name}, Chapter {current_chapter}" if current_chapter else section_name,
                        "chapter": current_chapter,
                        "verse_range": str(verse_num),
                        "text": chunk_text[:1200],
                        "language": "hindi", # Gitapress is a mix of Sanskrit verses & Hindi translations
                        "source_file": txt_path.name,
                        "source_page": line_buffer[0],
                        "word_count": len(chunk_text.split()),
                    })
                    text_buffer = text_buffer[-1:] # 1-verse overlap
                    line_buffer = line_buffer[-1:]
        
        # Flush remaining
        if len(text_buffer) >= 1:
            verse_num += 1
            chunk_text = ' । '.join(text_buffer)
            chunk_id = f"{text_id}-{section_name.lower().replace(' ', '_')}-{current_chapter}-{verse_num}"
            chunks.append({
                "id": chunk_id,
                "purana": purana_name,
                "category": "mahapurana",
                "book_section": f"{section_name}, Chapter {current_chapter}" if current_chapter else section_name,
                "chapter": current_chapter,
                "verse_range": str(verse_num),
                "text": chunk_text[:1200],
                "language": "hindi",
                "source_file": txt_path.name,
                "source_page": line_buffer[0] if line_buffer else 0,
                "word_count": len(chunk_text.split()),
            })
    else:
        # Line based fallback
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if CHAPTER_RE.search(line):
                current_chapter += 1
                
            text_buffer.append(line)
            line_buffer.append(i + 1)
            
            if len(text_buffer) >= 5:
                verse_num += 1
                chunk_text = '\n'.join(text_buffer)
                chunk_id = f"{text_id}-{section_name.lower().replace(' ', '_')}-{current_chapter}-{verse_num}"
                chunks.append({
                    "id": chunk_id,
                    "purana": purana_name,
                    "category": "mahapurana",
                    "book_section": f"{section_name}, Chapter {current_chapter}" if current_chapter else section_name,
                    "chapter": current_chapter,
                    "verse_range": str(verse_num),
                    "text": chunk_text[:1200],
                    "language": "hindi",
                    "source_file": txt_path.name,
                    "source_page": line_buffer[0],
                    "word_count": len(chunk_text.split()),
                })
                text_buffer = text_buffer[-2:] # overlap
                line_buffer = line_buffer[-2:]
                
        if len(text_buffer) >= 1:
            verse_num += 1
            chunk_text = '\n'.join(text_buffer)
            chunk_id = f"{text_id}-{section_name.lower().replace(' ', '_')}-{current_chapter}-{verse_num}"
            chunks.append({
                "id": chunk_id,
                "purana": purana_name,
                "category": "mahapurana",
                "book_section": f"{section_name}, Chapter {current_chapter}" if current_chapter else section_name,
                "chapter": current_chapter,
                "verse_range": str(verse_num),
                "text": chunk_text[:1200],
                "language": "hindi",
                "source_file": txt_path.name,
                "source_page": line_buffer[0] if line_buffer else 0,
                "word_count": len(chunk_text.split()),
            })

    print(f"  ✓ Extracted {len(chunks)} chunks")
    return chunks

def download_file(url: str, dest_path: Path):
    """Download file using urllib with custom user agent."""
    if dest_path.exists() and dest_path.stat().st_size > 10000:
        print(f"  ⏭ Skip (already exists): {dest_path.name}")
        return True
    
    print(f"  ↓ Downloading {url} ...")
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response, open(dest_path, "wb") as out_file:
            out_file.write(response.read())
        print(f"  ✓ Saved to {dest_path}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to download {url}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False

def main():
    print("🕉️  PuranGPT — Missing Puranas Downloader & Indexer")
    print("==================================================")
    
    # 1. Download and Chunk
    all_new_chunks = []
    
    for text_id, data in MISSING_TEXTS.items():
        print(f"\nProcessing {data['name']}...")
        raw_text_dir = Path("data/raw_texts/gretil") / text_id
        raw_text_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_file = CHUNKS_DIR / f"{text_id}.jsonl"
        
        # Check if already chunked
        if chunk_file.exists() and chunk_file.stat().st_size > 1000:
            print(f"⏭ Loading cached chunks for {data['name']}")
            with open(chunk_file, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        all_new_chunks.append(json.loads(line))
            continue
            
        text_id_chunks = []
        for file_info in data["files"]:
            dest_path = raw_text_dir / file_info["filename"]
            
            # Download text file
            success = download_file(file_info["url"], dest_path)
            if not success:
                print(f"✗ Skipping {file_info['filename']} due to download failure.")
                continue
                
            # Chunk the file
            chunks = chunk_txt_file(dest_path, text_id, data["name"], file_info["section"])
            text_id_chunks.extend(chunks)
            
        if text_id_chunks:
            # Save chunks to file
            with open(chunk_file, "w", encoding="utf-8") as f:
                for c in text_id_chunks:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
            all_new_chunks.extend(text_id_chunks)
            print(f"✓ Saved {len(text_id_chunks):,} chunks → {chunk_file.name}")
            
    print(f"\n==================================================")
    print(f"Total new chunks loaded/generated: {len(all_new_chunks):,}")
    
    if not all_new_chunks:
        print("No new chunks to index.")
        return
        
    # 2. Run local indexing to add them to ChromaDB and BM25
    print("\nRebuilding local indexes (ChromaDB + BM25) to include new Puranas...")
    indexer = EmbeddingIndexer(
        chunks_dir=CHUNKS_DIR,
        db_dir=DB_DIR,
        index_dir=INDEX_DIR,
        embed_model="intfloat/multilingual-e5-small", # Use the same model as configured in search.py
        batch_size=32
    )
    indexer.build_all()
    
    print("\n✓ New Puranas successfully indexed locally!")
    print("Next step: Run 'python scripts/migrate_chromadb_to_pinecone.py' to upload new vectors to Pinecone.")

if __name__ == "__main__":
    main()
