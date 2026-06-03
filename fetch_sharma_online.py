"""
PuranGPT — Shailendra Sharma Online Fetcher
============================================
Fetches all freely published Shailendra Sharma content from official sources:

  1. shailendrasharma.org  — Yoga Darshan (full), Gita chapters 1-18 (PDFs), HYP PDF
  2. guruji.com.ua          — All English darshan transcripts (hundreds of Q&A sessions)
  3. shailendrasharmabooks.com — Blog articles (free yogic excerpts)

Run from purangpt/ directory:
    pip install aiohttp aiofiles pymupdf beautifulsoup4
    python fetch_sharma_online.py

After completion:
    python run.py --chunk
    python run.py --index
"""

from __future__ import annotations
import asyncio, json, re, hashlib, logging
from pathlib import Path
import aiohttp, aiofiles

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger("sharma_fetch")

BASE        = Path(__file__).parent
SHARMA_TXT  = BASE / "data/raw_texts/sharma"
SHARMA_PDF  = BASE / "data/sharma_books"
CHUNKS_DIR  = BASE / "data/chunks"
for d in [SHARMA_TXT, SHARMA_PDF, CHUNKS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PuranGPT research; scholarly use)",
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. Yoga Darshan — full commentary on Patanjali's Yoga Sutras
# ─────────────────────────────────────────────────────────────────────────────
YOGA_DARSHAN_URL = "https://www.shailendrasharma.org/yogadarshan"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Yogeshwari Gita — 18 chapter PDFs
# ─────────────────────────────────────────────────────────────────────────────
GITA_PDF_BASE = "https://www.shailendrasharma.org/wp-content/uploads/2011/05/gita-ch{}.pdf"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Hatha Yoga Pradipika PDF (English commentary)
# ─────────────────────────────────────────────────────────────────────────────
HYP_PDF_URL = "http://www.shailendrasharma.org/wp-content/uploads/2016/03/HYP_final.pdf"

# ─────────────────────────────────────────────────────────────────────────────
# 4. English darshans from guruji.com.ua
# ─────────────────────────────────────────────────────────────────────────────
DARSHANS_INDEX = "https://guruji.com.ua/darshans/english"

# ─────────────────────────────────────────────────────────────────────────────
# 5. shailendrasharmabooks.com blog (free excerpts)
# ─────────────────────────────────────────────────────────────────────────────
BLOG_INDEX = "https://shailendrasharmabooks.com/blog/"


def strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\s{3,}', '\n\n', text)
    return text.strip()


def make_chunks(text: str, book_key: str, purana_name: str, tradition: str,
                edition: str, chunk_size: int = 900) -> list[dict]:
    """Split text into RAG chunks at paragraph boundaries."""
    chunks = []
    paras  = [p.strip() for p in re.split(r'\n\n+', text) if len(p.strip()) > 50]
    buffer, chapter = "", "Introduction"
    for para in paras:
        if re.match(r'^(Sutra|Chapter|Adhyaya|Part|Section|Book)\s+[\dIVX]', para, re.I) and len(para) < 120:
            chapter = para[:80]
        buffer += para + "\n\n"
        if len(buffer) >= chunk_size:
            cid = hashlib.md5(f"{book_key}:{buffer[:50]}".encode()).hexdigest()[:10]
            chunks.append({
                "id":           f"sharma-{book_key}-{cid}",
                "purana":       purana_name,
                "author":       "Sri Sri Shailendra Sharma",
                "tradition":    tradition,
                "category":     "yogic-commentary",
                "book_section": chapter,
                "chapter":      chapter,
                "verse_range":  "",
                "text":         buffer.strip(),
                "language":     "English",
                "source_file":  book_key,
                "source_page":  len(chunks) + 1,
                "word_count":   len(buffer.split()),
                "edition":      edition,
                "bias":         "✅ Yogiraj Shailendra Sharma",
            })
            buffer = ""
    if buffer.strip():
        cid = hashlib.md5(f"{book_key}:{buffer[:50]}".encode()).hexdigest()[:10]
        chunks.append({
            "id":           f"sharma-{book_key}-{cid}",
            "purana":       purana_name,
            "author":       "Sri Sri Shailendra Sharma",
            "tradition":    tradition,
            "category":     "yogic-commentary",
            "book_section": chapter,
            "chapter":      chapter,
            "verse_range":  "",
            "text":         buffer.strip(),
            "language":     "English",
            "source_file":  book_key,
            "source_page":  len(chunks) + 1,
            "word_count":   len(buffer.split()),
            "edition":      edition,
            "bias":         "✅ Yogiraj Shailendra Sharma",
        })
    return chunks


def save_chunks(chunks: list[dict], filename: str) -> None:
    out = CHUNKS_DIR / filename
    with open(out, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    # append to all_chunks
    with open(CHUNKS_DIR / "all_chunks.jsonl", "a", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    log.info("  Saved %d chunks → %s", len(chunks), out.name)


async def fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")
        return await r.text(errors="replace")


async def fetch_bytes(session: aiohttp.ClientSession, url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 5000:
        log.info("  Skip (exists): %s", dest.name)
        return True
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                log.warning("  HTTP %d: %s", r.status, url)
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                async for chunk in r.content.iter_chunked(65536):
                    await f.write(chunk)
        log.info("  ✓ %s (%d KB)", dest.name, dest.stat().st_size // 1024)
        return True
    except Exception as e:
        log.warning("  ✗ %s — %s", url, e)
        return False


# ── Yoga Darshan ─────────────────────────────────────────────────────────────
async def fetch_yoga_darshan(session: aiohttp.ClientSession) -> None:
    log.info("\n=== Yoga Darshan ===")
    try:
        html = await fetch_text(session, YOGA_DARSHAN_URL)
        # Extract main content (after the nav)
        m = re.search(r'<h1[^>]*>.*?Yoga Darshan.*?</h1>(.*?)(?:©2011|shailendra\.ru)', html, re.DOTALL | re.I)
        content = m.group(1) if m else html
        text = f"Yoga Darshan: A Commentary on Patanjali's Yoga Sutras — Sri Sri Shailendra Sharma\nSource: shailendrasharma.org\n\n{strip_html(content)}"

        txt_path = SHARMA_TXT / "yoga_darshan.txt"
        txt_path.write_text(text, encoding="utf-8")
        log.info("  Saved %d chars to yoga_darshan.txt", len(text))

        chunks = make_chunks(text, "yoga_darshan",
                             "Yoga Darshan — Patanjali Yoga Sutra Commentary by Shailendra Sharma",
                             "darshana", "shailendrasharma.org (official)")
        save_chunks(chunks, "sharma_yoga_darshan.jsonl")
    except Exception as e:
        log.error("  Failed Yoga Darshan: %s", e)


# ── Gita chapters ─────────────────────────────────────────────────────────────
async def fetch_gita_chapters(session: aiohttp.ClientSession) -> None:
    log.info("\n=== Yogeshwari Gita Chapters (18 PDFs) ===")
    all_text = ""
    for i in range(1, 19):
        url  = GITA_PDF_BASE.format(i)
        dest = SHARMA_PDF / f"gita_chapter_{i:02d}.pdf"
        ok   = await fetch_bytes(session, url, dest)
        if ok:
            try:
                import fitz
                doc  = fitz.open(str(dest))
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                all_text += f"\n\n=== Chapter {i} ===\n{text}"
                log.info("  Extracted ch%d: %d chars", i, len(text))
            except Exception as e:
                log.warning("  Could not extract ch%d: %s", i, e)
        await asyncio.sleep(1)

    if all_text.strip():
        full = f"Yogeshwari Srimad Bhagavad Gita: A Yogic Commentary — Sri Sri Shailendra Sharma\nSource: shailendrasharma.org\n\n{all_text}"
        (SHARMA_TXT / "yogeshwari_gita_full.txt").write_text(full, encoding="utf-8")
        chunks = make_chunks(full, "yogeshwari_gita_full",
                             "Yogeshwari Srimad Bhagavad Gita — Shailendra Sharma (Full Commentary)",
                             "kriya-yoga", "shailendrasharma.org (official PDFs)")
        save_chunks(chunks, "sharma_yogeshwari_full.jsonl")
        log.info("  Total Gita: %d chunks", len(chunks))


# ── HYP PDF ───────────────────────────────────────────────────────────────────
async def fetch_hyp(session: aiohttp.ClientSession) -> None:
    log.info("\n=== Hatha Yoga Pradipika (PDF) ===")
    dest = SHARMA_PDF / "hatha_yoga_pradipika_sharma.pdf"
    ok   = await fetch_bytes(session, HYP_PDF_URL, dest)
    if ok:
        try:
            import fitz
            doc  = fitz.open(str(dest))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            full = f"Hatha Yoga Pradipika — Commentary by Sri Sri Shailendra Sharma\nSource: shailendrasharma.org\n\n{text}"
            (SHARMA_TXT / "hatha_yoga_pradipika_sharma.txt").write_text(full, encoding="utf-8")
            chunks = make_chunks(full, "hyp_sharma",
                                 "Hatha Yoga Pradipika — Shailendra Sharma Commentary",
                                 "nath", "shailendrasharma.org (official PDF)")
            save_chunks(chunks, "sharma_hyp.jsonl")
            log.info("  HYP: %d chunks", len(chunks))
        except Exception as e:
            log.error("  HYP extraction failed: %s", e)


# ── guruji.com.ua English Darshans ───────────────────────────────────────────
async def fetch_darshan_links(session: aiohttp.ClientSession, index_url: str) -> list[str]:
    """Get all darshan page URLs from the index."""
    try:
        html = await fetch_text(session, index_url)
        links = re.findall(r'href="(https://guruji\.com\.ua/darshan/[^"]+)"', html)
        links = list(dict.fromkeys(links))  # deduplicate
        log.info("  Found %d darshan links", len(links))
        return links
    except Exception as e:
        log.warning("  Could not fetch darshan index: %s", e)
        return []


async def fetch_one_darshan(session: aiohttp.ClientSession, url: str) -> str:
    try:
        html = await fetch_text(session, url)
        # Extract article body
        m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        if not m:
            m = re.search(r'<div class="entry-content[^"]*">(.*?)</div>', html, re.DOTALL)
        content = m.group(1) if m else html
        return strip_html(content)
    except Exception:
        return ""


async def fetch_all_darshans(session: aiohttp.ClientSession) -> None:
    log.info("\n=== guruji.com.ua English Darshans ===")
    links = await fetch_darshan_links(session, DARSHANS_INDEX)
    if not links:
        return

    all_chunks = []
    for i, url in enumerate(links):
        slug = url.rstrip("/").split("/")[-1]
        text = await fetch_one_darshan(session, url)
        if len(text) < 100:
            continue
        full = f"Darshan: {slug}\nSource: guruji.com.ua\nTradition: Kriya Yoga\n\n{text}"
        chunks = make_chunks(full, f"darshan_{slug}",
                             f"Shailendra Sharma Darshan — {slug}",
                             "kriya-yoga", "guruji.com.ua (official)")
        all_chunks.extend(chunks)
        if (i + 1) % 20 == 0:
            log.info("  Fetched %d/%d darshans (%d chunks so far)", i+1, len(links), len(all_chunks))
        await asyncio.sleep(0.8)

    if all_chunks:
        save_chunks(all_chunks, "sharma_darshans_online.jsonl")
        log.info("  Total darshan chunks: %d", len(all_chunks))


# ── shailendrasharmabooks.com blog ─────────────────────────────────────────────
async def fetch_blog(session: aiohttp.ClientSession) -> None:
    log.info("\n=== shailendrasharmabooks.com Blog ===")
    try:
        html = await fetch_text(session, BLOG_INDEX)
        links = re.findall(r'href="(https://shailendrasharmabooks\.com/[a-z0-9\-]+/)"', html)
        links = [l for l in dict.fromkeys(links) if "/product" not in l and "/category" not in l]
        log.info("  Found %d blog posts", len(links))

        all_chunks = []
        for url in links[:30]:  # first 30 posts
            try:
                html2 = await fetch_text(session, url)
                m = re.search(r'<article[^>]*>(.*?)</article>', html2, re.DOTALL)
                content = strip_html(m.group(1)) if m else ""
                if len(content) > 200:
                    slug = url.rstrip("/").split("/")[-1]
                    full = f"Blog: {slug}\nSource: shailendrasharmabooks.com\n\n{content}"
                    chunks = make_chunks(full, f"blog_{slug}",
                                        f"Shailendra Sharma Teaching — {slug}",
                                        "kriya-yoga", "shailendrasharmabooks.com (official)")
                    all_chunks.extend(chunks)
                await asyncio.sleep(0.5)
            except Exception:
                continue

        if all_chunks:
            save_chunks(all_chunks, "sharma_blog.jsonl")
            log.info("  Blog: %d chunks", len(all_chunks))
    except Exception as e:
        log.error("  Blog fetch failed: %s", e)


async def main():
    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        await fetch_yoga_darshan(session)
        await fetch_gita_chapters(session)
        await fetch_hyp(session)
        await fetch_all_darshans(session)
        await fetch_blog(session)

    log.info("\n✅ All done. Now rebuild the index:")
    log.info("   python run.py --index")


if __name__ == "__main__":
    asyncio.run(main())
