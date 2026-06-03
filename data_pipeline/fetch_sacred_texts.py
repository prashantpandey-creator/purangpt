import requests
import json
import uuid
from pathlib import Path

CHUNKS_DIR = Path("data/chunks")
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# Some raw URLs for English translations of these texts
TEXTS = [
    {
        "url": "https://raw.githubusercontent.com/tensorsense/Yoga-Sutras/master/yoga_sutras.txt",
        "title": "Yoga Sutras of Patanjali",
        "domain": "neutral-darshana"
    },
    {
        "url": "https://raw.githubusercontent.com/sanskrit-lexicon/CORPUS/master/HathaYogaPradipika/HathaYogaPradipika.txt",
        "title": "Hatha Yoga Pradipika",
        "domain": "nath-sampradaya"
    },
    {
        "url": "https://raw.githubusercontent.com/sanskrit-lexicon/CORPUS/master/ShivaSamhita/ShivaSamhita.txt",
        "title": "Shiva Samhita",
        "domain": "nath-sampradaya"
    }
]

def chunk_text(text: str, title: str, domain: str):
    words = text.split()
    if len(words) < 50: return
    
    out_file = CHUNKS_DIR / f"{title.replace(' ', '_').lower()}.jsonl"
    chunk_size = 300
    overlap = 50
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) < 50 and i != 0: continue
            
        chunk_str = " ".join(chunk_words)
        chunk = {
            "id": f"{domain}-{uuid.uuid4().hex[:8]}",
            "purana": title,
            "book_section": domain,
            "chapter": "Full Text",
            "verse_range": f"Part {len(chunks) + 1}",
            "text": chunk_str,
            "language": "english",
            "source_file": title,
            "source_page": 1,
            "word_count": len(chunk_words)
        }
        chunks.append(chunk)

    with open(out_file, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"Saved {len(chunks)} chunks for {title}")

for t in TEXTS:
    print(f"Downloading {t['title']}...")
    try:
        res = requests.get(t["url"], timeout=10)
        if res.status_code == 200:
            chunk_text(res.text, t["title"], t["domain"])
        else:
            print(f"Failed: HTTP {res.status_code}")
    except Exception as e:
        print(f"Error fetching {t['title']}: {e}")
