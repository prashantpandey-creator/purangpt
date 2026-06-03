import os
import requests
from bs4 import BeautifulSoup
import json
import uuid
from duckduckgo_search import DDGS
from pathlib import Path
import time
import re

CHUNKS_DIR = Path("data/chunks")
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = CHUNKS_DIR / "shailendra_sharma_darshans.jsonl"

def chunk_and_save(text: str, url: str, title: str):
    words = text.split()
    if len(words) < 50: return
    
    chunk_size = 300
    overlap = 50
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) < 50 and i != 0: continue
            
        chunk_str = " ".join(chunk_words)
        chunk_id = f"darshan-{uuid.uuid4().hex[:8]}"
        
        chunk = {
            "id": chunk_id,
            "purana": "Shailendra Sharma Darshans",
            "book_section": "Discourses",
            "chapter": title,
            "verse_range": f"Part {len(chunks) + 1}",
            "text": chunk_str,
            "language": "english",
            "source_file": url,
            "source_page": 1,
            "word_count": len(chunk_words)
        }
        chunks.append(chunk)

    with open(OUT_FILE, "a", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"Saved {len(chunks)} chunks from {title}")

def scrape_url(url: str):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else url
        
        for tag in soup(['nav', 'header', 'footer', 'script', 'style', 'aside']):
            tag.decompose()
            
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            text = re.sub(r'\n{3,}', '\n\n', text)
            chunk_and_save(text, url, title.strip())
            
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")

def main():
    print("Fetching index page...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get("https://gurujidarshan.com/darshans/english", headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        
        links = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.endswith('.html') and ('darshan' in href or 'novosti' in href):
                if not href.startswith('http'):
                    href = "https://gurujidarshan.com" + href
                links.add(href)
                
        print(f"Found {len(links)} unique Darshan URLs.")
        
        # Scrape all found links
        for idx, url in enumerate(list(links)):
            print(f"[{idx+1}/{len(links)}] Scraping {url}...")
            scrape_url(url)
            time.sleep(0.5)  # Be gentle
            
        print("Scraping complete.")
    except Exception as e:
        print(f"Failed to fetch index: {e}")

if __name__ == "__main__":
    main()
