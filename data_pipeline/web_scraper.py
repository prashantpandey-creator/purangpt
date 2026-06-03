"""
PuranGPT — Web Article Scraper
===============================
Scrapes articles, blog posts, and internet text into the chunk format
expected by PuranGPT's build_index.py script.

Usage:
    python data_pipeline/web_scraper.py --url "https://example.com/article" --title "Example Article" --author "Author Name"
"""

import argparse
import json
import logging
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CHUNKS_DIR = Path("data/chunks")

def scrape_article(url: str, title: str, author: str = "Unknown"):
    """Scrape the main text from a web article."""
    try:
        logger.info(f"Scraping: {url}")
        headers = {"User-Agent": "PuranGPT Web Scraper (Academic)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Remove navs, headers, footers, scripts, styles
        for tag in soup(['nav', 'header', 'footer', 'script', 'style', 'aside', 'form', 'button']):
            tag.decompose()

        # Try to find main content
        main_content = soup.find('main') or soup.find('article')
        if not main_content:
            # Fallback to body
            main_content = soup.find('body')

        if not main_content:
            logger.error("Could not find any readable content.")
            return

        text = main_content.get_text(separator='\n', strip=True)
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        words = text.split()
        if len(words) < 50:
            logger.warning("Scraped content is too short, might be blocked or parsing failed.")
            return

        logger.info(f"Successfully scraped {len(words)} words.")
        chunk_text(text, url, title, author)

    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")

def chunk_text(text: str, url: str, title: str, author: str):
    """Chunk the text into overlapping segments of ~300 words."""
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    domain = urlparse(url).netloc.replace("www.", "")
    out_file = CHUNKS_DIR / f"web_scraped_{domain}.jsonl"

    words = text.split()
    chunk_size = 300
    overlap = 50
    
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        if len(chunk_words) < 50 and i != 0:
            continue  # skip tiny trailing chunks
            
        chunk_str = " ".join(chunk_words)
        chunk_id = f"web-{domain}-{uuid.uuid4().hex[:8]}"
        
        chunk = {
            "id": chunk_id,
            "purana": f"Web Article: {title}",
            "book_section": domain,
            "chapter": author,
            "verse_range": f"Part {len(chunks) + 1}",
            "text": chunk_str,
            "language": "english",
            "source_file": url,
            "source_page": 1,
            "word_count": len(chunk_words)
        }
        chunks.append(chunk)

    # Append to jsonl
    with open(out_file, "a", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    logger.info(f"Saved {len(chunks)} chunks to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape web articles into PuranGPT chunks.")
    parser.add_argument("--url", required=True, help="URL of the article to scrape")
    parser.add_argument("--title", required=True, help="Title of the article")
    parser.add_argument("--author", default="Unknown", help="Author of the article")
    args = parser.parse_args()

    scrape_article(args.url, args.title, args.author)
