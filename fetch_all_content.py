"""
PuranGPT — Comprehensive Content Fetcher
==========================================
Downloads and indexes ALL missing content:

1. vedpuran.net   — Hindi PDFs of all 18 Mahapuranas, Vedas, Upanishads (text extraction)
2. guruji.com.ua  — All 188+ English Darshan transcripts of Shailendra Sharma (2016–2025)
3. gurujidarshan.com — 476+ additional darshan pages (comprehensive mirror)
4. anahada.com    — Philosophical articles by/about Shailendra Sharma
5. wildyogi.info  — Interviews and darshan excerpts
6. shailendrasharma.org — Yoga Darshan full commentary + 18 Gita chapter PDFs + HYP PDF

Run from purangpt/ directory:
    pip install aiohttp aiofiles pymupdf beautifulsoup4 langdetect
    python fetch_all_content.py

After completion:
    python index_sharma_texts.py    ← re-index Sharma chunks
    docker compose restart backend  ← reload BM25 on server

Author: PuranGPT automated fetcher
"""
from __future__ import annotations
import asyncio, json, re, hashlib, logging, pickle, sys, time
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fetcher")

BASE        = Path(__file__).parent
SHARMA_TXT  = BASE / "data/raw_texts/sharma"
VEDPURAN_TXT= BASE / "data/raw_texts/vedpuran"
SHARMA_PDF  = BASE / "data/sharma_books"
CHUNKS_DIR  = BASE / "data/chunks"
INDEX_DIR   = BASE / "data/indexes"

for d in [SHARMA_TXT, VEDPURAN_TXT, SHARMA_PDF, CHUNKS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def strip_html(html: str) -> str:
    """Clean HTML to plain text."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'&[a-z]+;', '', text)
    text = re.sub(r'\s{3,}', '\n\n', text)
    return text.strip()


def make_chunks(
    text: str,
    book_key: str,
    purana_name: str,
    tradition: str,
    edition: str,
    language: str = "English",
    category: str = "yogic-commentary",
    chunk_size: int = 900,
    overlap: int = 100,
) -> list[dict]:
    """Split text into overlapping RAG chunks."""
    chunks = []
    paras = [p.strip() for p in re.split(r'\n\n+', text) if len(p.strip()) > 60]
    buffer, chapter = "", "Introduction"
    for para in paras:
        if re.match(r'^(Sutra|Chapter|Adhyaya|Part|Section|Shloka|Verse)\s+[\dIVX]', para, re.I) \
                and len(para) < 120:
            chapter = para[:80]
        buffer += para + "\n\n"
        if len(buffer) >= chunk_size:
            cid = hashlib.md5(f"{book_key}:{buffer[:50]}".encode()).hexdigest()[:10]
            chunks.append({
                "id":           f"sharma-{book_key}-{cid}",
                "purana":       purana_name,
                "author":       "Sri Sri Shailendra Sharma",
                "tradition":    tradition,
                "category":     category,
                "book_section": chapter,
                "chapter":      chapter,
                "verse_range":  "",
                "text":         buffer.strip(),
                "language":     language,
                "source_file":  book_key,
                "source_page":  len(chunks) + 1,
                "word_count":   len(buffer.split()),
                "edition":      edition,
                "bias":         "✅ Yogiraj Shailendra Sharma",
            })
            buffer = buffer[chunk_size - overlap:]
    if buffer.strip() and len(buffer.strip()) > 100:
        cid = hashlib.md5(f"{book_key}:{buffer[:50]}".encode()).hexdigest()[:10]
        chunks.append({
            "id":           f"sharma-{book_key}-{cid}",
            "purana":       purana_name,
            "author":       "Sri Sri Shailendra Sharma",
            "tradition":    tradition,
            "category":     category,
            "book_section": chapter,
            "chapter":      chapter,
            "verse_range":  "",
            "text":         buffer.strip(),
            "language":     language,
            "source_file":  book_key,
            "source_page":  len(chunks) + 1,
            "word_count":   len(buffer.split()),
            "edition":      edition,
            "bias":         "✅ Yogiraj Shailendra Sharma",
        })
    return chunks


def save_chunks(chunks: list[dict], filename: str, mode: str = "w") -> None:
    out = CHUNKS_DIR / filename
    with open(out, mode, encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    log.info("  ✓ Saved %d chunks → %s", len(chunks), out.name)


async def fetch_text(session, url: str, timeout: int = 30) -> str:
    import aiohttp
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status} for {url}")
        return await r.text(errors="replace")


async def fetch_bytes(session, url: str, dest: Path, timeout: int = 120) -> bool:
    import aiohttp, aiofiles
    if dest.exists() and dest.stat().st_size > 10_000:
        log.info("  Skip (exists): %s", dest.name)
        return True
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
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


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        log.warning("  PDF extract failed %s: %s", pdf_path.name, e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# PART 1 — vedpuran.net: Hindi Puranas (PDF download + text extraction)
# ─────────────────────────────────────────────────────────────────────────────
VEDPURAN_PDFS = {
    # Mahapuranas (18)
    "agni_puran":           ("https://vedpuran.net/wp-content/uploads/2011/10/agni-puran.pdf",             "Agni Purana (Hindi — Vedpuran.net)",             "mixed"),
    "bhagwat_puran":        ("https://vedpuran.net/wp-content/uploads/2011/10/bhagwat-puran.pdf",          "Bhagavata Purana (Hindi — Vedpuran.net)",         "vaishnava"),
    "bavishya_puran":       ("https://vedpuran.net/wp-content/uploads/2011/10/bavishya-puran.pdf",         "Bhavishya Purana (Hindi — Vedpuran.net)",         "mixed"),
    "brahma_puran":         ("https://vedpuran.net/wp-content/uploads/2011/10/bramha.pdf",                 "Brahma Purana (Hindi — Vedpuran.net)",            "mixed"),
    "brahmanda_puran":      ("https://vedpuran.net/wp-content/uploads/2011/10/brahamand.pdf",              "Brahmanda Purana (Hindi — Vedpuran.net)",         "mixed"),
    "brahmanda_puran_2":    ("https://vedpuran.net/wp-content/uploads/2011/10/brahamandp.pdf",             "Brahmanda Purana Pt2 (Hindi — Vedpuran.net)",     "mixed"),
    "brahma_vaivarta_puran":("https://vedpuran.net/wp-content/uploads/2011/10/vaivtpuran.pdf",             "Brahma Vaivarta Purana (Hindi — Vedpuran.net)",   "vaishnava"),
    "garuda_puran":         ("https://vedpuran.net/wp-content/uploads/2011/10/garuda1.pdf",                "Garuda Purana (Hindi — Vedpuran.net)",            "vaishnava"),
    "kurma_puran":          ("https://vedpuran.net/wp-content/uploads/2011/10/kurma.pdf",                  "Kurma Purana (Hindi — Vedpuran.net)",             "shaiva-vaishnava"),
    "linga_puran":          ("https://vedpuran.net/wp-content/uploads/2011/10/ling.pdf",                   "Linga Purana (Hindi — Vedpuran.net)",             "shaiva"),
    "markandeya_puran":     ("https://vedpuran.net/wp-content/uploads/2011/10/markende-puran.pdf",         "Markandeya Purana (Hindi — Vedpuran.net)",        "shakta"),
    "matsya_puran_1":       ("https://vedpuran.net/wp-content/uploads/2011/10/matsya-puran-1.pdf",         "Matsya Purana Pt1 (Hindi — Vedpuran.net)",        "mixed"),
    "matsya_puran_2":       ("https://vedpuran.net/wp-content/uploads/2011/10/matsya-puran-2.pdf",         "Matsya Purana Pt2 (Hindi — Vedpuran.net)",        "mixed"),
    "narada_puran":         ("https://vedpuran.net/wp-content/uploads/2011/10/nard-puran.pdf",             "Narada Purana (Hindi — Vedpuran.net)",            "vaishnava"),
    "padma_puran":          ("https://vedpuran.net/wp-content/uploads/2011/10/padam-puran.pdf",            "Padma Purana (Hindi — Vedpuran.net)",             "vaishnava"),
    "shiva_puran":          ("https://vedpuran.net/wp-content/uploads/2011/10/shiv-puran.pdf",             "Shiva Purana (Hindi — Vedpuran.net)",             "shaiva"),
    "skanda_puran":         ("https://vedpuran.net/wp-content/uploads/2011/10/sakand-puran.pdf",           "Skanda Purana (Hindi — Vedpuran.net)",            "shaiva"),
    "vamana_puran":         ("https://vedpuran.net/wp-content/uploads/2011/10/vamanpuran.pdf",             "Vamana Purana (Hindi — Vedpuran.net)",            "vaishnava"),
    # Upapuranas
    "narsimha_puran":       ("https://vedpuran.net/wp-content/uploads/2011/10/narsihma-puran.pdf",         "Narasimha Purana (Hindi — Vedpuran.net)",         "vaishnava"),
    # Vedas
    "rigveda_hindi":        ("https://vedpuran.net/wp-content/uploads/2011/10/rigved.pdf",                 "Rigveda (Hindi — Vedpuran.net)",                  "vedic"),
    "samaveda_hindi":       ("https://vedpuran.net/wp-content/uploads/2011/10/samved.pdf",                 "Samaveda (Hindi — Vedpuran.net)",                 "vedic"),
    "atharvaveda_1":        ("https://vedpuran.net/wp-content/uploads/2011/10/arthved-part-1.pdf",         "Atharvaveda Pt1 (Hindi — Vedpuran.net)",          "vedic"),
    "atharvaveda_2":        ("https://vedpuran.net/wp-content/uploads/2011/10/atharva-2.pdf",              "Atharvaveda Pt2 (Hindi — Vedpuran.net)",          "vedic"),
}

async def fetch_vedpuran_pdfs(session) -> int:
    """Download all vedpuran.net PDFs and extract Hindi text."""
    log.info("\n=== VEDPURAN.NET — Hindi PDFs (%d texts) ===", len(VEDPURAN_PDFS))
    total_chunks = 0

    for key, (url, display_name, tradition) in VEDPURAN_PDFS.items():
        dest = SHARMA_PDF / f"vedpuran_{key}.pdf"
        txt_dest = VEDPURAN_TXT / f"{key}.txt"

        # Skip if already extracted
        if txt_dest.exists() and txt_dest.stat().st_size > 5000:
            log.info("  Skip (exists): %s", txt_dest.name)
            # Still count for progress
            try:
                chunks = _load_existing_chunks(key)
                total_chunks += len(chunks)
            except Exception:
                pass
            continue

        ok = await fetch_bytes(session, url, dest, timeout=180)
        if not ok:
            await asyncio.sleep(2)
            continue

        # Extract text from PDF
        raw_text = extract_pdf_text(dest)
        if len(raw_text) < 500:
            log.warning("  Skipping %s — too little text (%d chars)", key, len(raw_text))
            continue

        # Save raw text
        full_text = f"{display_name}\nSource: vedpuran.net (Hindi)\nTradition: {tradition}\n\n{raw_text}"
        txt_dest.write_text(full_text, encoding="utf-8", errors="replace")
        log.info("  Extracted: %s (%d chars)", key, len(full_text))

        # Chunk and save
        chunks = make_chunks(
            full_text, f"vedpuran_{key}", display_name, tradition,
            "vedpuran.net (Hindi PDF)", language="Hindi",
            category="purana-hindi"
        )
        if chunks:
            save_chunks(chunks, f"vedpuran_{key}.jsonl")
            total_chunks += len(chunks)

        await asyncio.sleep(2)  # polite delay

    log.info("  Total vedpuran chunks: %d", total_chunks)
    return total_chunks


def _load_existing_chunks(key: str) -> list[dict]:
    f = CHUNKS_DIR / f"vedpuran_{key}.jsonl"
    if not f.exists():
        return []
    chunks = []
    with open(f) as fh:
        for line in fh:
            chunks.append(json.loads(line))
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# PART 2 — guruji.com.ua: All English Darshan transcripts
# ─────────────────────────────────────────────────────────────────────────────

async def get_all_darshan_urls(session) -> list[tuple[str, str]]:
    """Get all darshan URLs from both guruji.com.ua and gurujidarshan.com."""
    all_urls = set()

    # guruji.com.ua index
    try:
        html = await fetch_text(session, "https://guruji.com.ua/darshans/english")
        links = re.findall(r'href="(https://guruji\.com\.ua/darshan/[^"]+)"', html)
        for l in links:
            all_urls.add(("guruji.com.ua", l))
        log.info("  guruji.com.ua: found %d darshan links", len(links))
    except Exception as e:
        log.warning("  guruji.com.ua index failed: %s", e)

    # gurujidarshan.com index (more comprehensive)
    try:
        html = await fetch_text(session, "https://gurujidarshan.com/darshans")
        links = re.findall(r'href="(https?://gurujidarshan\.com/darshan/[^"#?]+)"', html)
        for l in set(links):
            all_urls.add(("gurujidarshan.com", l))
        log.info("  gurujidarshan.com: found %d darshan links", len(links))

        # also check for pagination
        page_links = re.findall(r'href="(https?://gurujidarshan\.com/darshans\?[^"]+)"', html)
        for pl in page_links[:20]:
            try:
                html2 = await fetch_text(session, pl)
                more = re.findall(r'href="(https?://gurujidarshan\.com/darshan/[^"#?]+)"', html2)
                for l in set(more):
                    all_urls.add(("gurujidarshan.com", l))
                await asyncio.sleep(1)
            except Exception:
                pass
    except Exception as e:
        log.warning("  gurujidarshan.com index failed: %s", e)

    result = sorted(all_urls, key=lambda x: x[1])
    log.info("  Total unique darshan URLs: %d", len(result))
    return result


async def fetch_one_darshan(session, url: str) -> str:
    """Extract clean text content from a darshan page."""
    try:
        html = await fetch_text(session, url)
        # Try article tag first
        m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        if not m:
            # Try entry-content div
            m = re.search(r'<div[^>]+class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>\s*(?:<div|<footer|<aside)', html, re.DOTALL)
        if not m:
            # Try main content area
            m = re.search(r'<div[^>]+class="[^"]*post-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        content = m.group(1) if m else html
        text = strip_html(content)
        # Filter out nav/footer noise (too short = nav, too repetitive = boilerplate)
        if len(text) < 200:
            return ""
        return text
    except Exception as e:
        log.warning("  Failed %s: %s", url, e)
        return ""


async def fetch_all_darshans(session) -> int:
    """Fetch all Shailendra Sharma darshan transcripts."""
    log.info("\n=== SHAILENDRA SHARMA DARSHANS ===")

    # Check what we already have
    existing_file = CHUNKS_DIR / "sharma_darshans_all.jsonl"
    existing_ids = set()
    if existing_file.exists():
        with open(existing_file) as f:
            for line in f:
                try:
                    c = json.loads(line)
                    existing_ids.add(c.get("source_file", ""))
                except Exception:
                    pass
        log.info("  Already have %d darshan sources cached", len(existing_ids))

    url_pairs = await get_all_darshan_urls(session)

    all_chunks = []
    fetched = 0
    skipped = 0

    for source, url in url_pairs:
        slug = url.rstrip("/").split("/")[-1].replace(".html", "")
        cache_key = f"darshan_{source}_{slug}"

        if cache_key in existing_ids:
            skipped += 1
            continue

        text = await fetch_one_darshan(session, url)
        if len(text) < 150:
            await asyncio.sleep(0.5)
            continue

        # Build full labeled text
        full = (
            f"Shailendra Sharma Darshan: {slug}\n"
            f"Source: {source}\n"
            f"URL: {url}\n"
            f"Tradition: Kriya Yoga / Nath\n\n"
            f"{text}"
        )

        # Save raw text
        raw_path = SHARMA_TXT / f"darshan_{slug}.txt"
        raw_path.write_text(full, encoding="utf-8", errors="replace")

        chunks = make_chunks(
            full,
            cache_key,
            f"Shailendra Sharma Darshan — {slug}",
            "kriya-yoga",
            f"{source} (official darshan)",
            language="English",
            category="yogic-discourse",
        )
        all_chunks.extend(chunks)
        fetched += 1

        if fetched % 25 == 0:
            log.info("  Progress: %d fetched, %d skipped, %d chunks", fetched, skipped, len(all_chunks))
            # Flush to disk periodically
            if all_chunks:
                save_chunks(all_chunks, "sharma_darshans_all.jsonl", mode="a")
                all_chunks = []

        await asyncio.sleep(0.8)  # polite crawl rate

    # Final flush
    if all_chunks:
        save_chunks(all_chunks, "sharma_darshans_all.jsonl", mode="a")

    log.info("  Darshans complete: %d new, %d already cached", fetched, skipped)
    return fetched


# ─────────────────────────────────────────────────────────────────────────────
# PART 3 — anahada.com: Philosophical articles
# ─────────────────────────────────────────────────────────────────────────────
ANAHADA_ARTICLES = [
    "https://anahada.com/advaita-nirakara-and-nirguna/",
    "https://anahada.com/yoga-and-your-soul/",
    "https://anahada.com/life-after-life/",
    "https://anahada.com/pseudo-spirituality/",
    "https://anahada.com/genius-and-the-story-of-a-hen/",
    "https://anahada.com/prithvi-namaskar/",
    "https://anahada.com/castes-of-ages/",
]

async def fetch_anahada(session) -> int:
    """Fetch Shailendra Sharma articles from anahada.com."""
    log.info("\n=== ANAHADA.COM — Articles ===")
    all_chunks = []

    # First discover all links
    try:
        html = await fetch_text(session, "https://anahada.com")
        extra = re.findall(r'href="(https://anahada\.com/[a-z0-9\-]+/?)"', html)
        extra = [l for l in extra if l not in ANAHADA_ARTICLES and len(l) > 25]
        all_urls = list(dict.fromkeys(ANAHADA_ARTICLES + extra[:30]))
    except Exception:
        all_urls = ANAHADA_ARTICLES

    log.info("  Fetching %d anahada.com articles", len(all_urls))

    for url in all_urls:
        try:
            html = await fetch_text(session, url)
            m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
            if not m:
                m = re.search(r'<div[^>]+class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            content = strip_html(m.group(1)) if m else strip_html(html)
            if len(content) < 300:
                continue

            slug = url.rstrip("/").split("/")[-1]
            full = (
                f"Shailendra Sharma — {slug.replace('-', ' ').title()}\n"
                f"Source: anahada.com\nURL: {url}\n\n{content}"
            )
            chunks = make_chunks(
                full, f"anahada_{slug}",
                f"Shailendra Sharma Article — {slug.replace('-',' ').title()}",
                "kriya-yoga", "anahada.com"
            )
            all_chunks.extend(chunks)
            log.info("  ✓ %s (%d chunks)", slug, len(chunks))
            await asyncio.sleep(1)
        except Exception as e:
            log.warning("  ✗ %s: %s", url, e)

    if all_chunks:
        save_chunks(all_chunks, "sharma_anahada.jsonl")
    return len(all_chunks)


# ─────────────────────────────────────────────────────────────────────────────
# PART 4 — wildyogi.info: Darshan excerpts and interviews
# ─────────────────────────────────────────────────────────────────────────────
async def fetch_wildyogi(session) -> int:
    """Fetch Shailendra Sharma content from wildyogi.info."""
    log.info("\n=== WILDYOGI.INFO — Darshan Excerpts ===")
    all_chunks = []

    try:
        # Search for Sharma content
        html = await fetch_text(session, "https://wildyogi.info/?s=shailendra+sharma")
        links = re.findall(r'href="(https://wildyogi\.info/[a-z0-9\-/]+/?)"', html)
        links = [l for l in dict.fromkeys(links) if len(l) > 25 and "?" not in l]
        log.info("  Found %d wildyogi links", len(links))

        for url in links[:40]:
            try:
                html2 = await fetch_text(session, url)
                m = re.search(r'<article[^>]*>(.*?)</article>', html2, re.DOTALL)
                content = strip_html(m.group(1)) if m else ""
                if len(content) < 300:
                    continue
                slug = url.rstrip("/").split("/")[-1]
                full = f"Shailendra Sharma — WildYogi: {slug}\nSource: wildyogi.info\n\n{content}"
                chunks = make_chunks(
                    full, f"wildyogi_{slug}",
                    f"Shailendra Sharma Teaching — {slug.replace('-',' ').title()}",
                    "kriya-yoga", "wildyogi.info"
                )
                all_chunks.extend(chunks)
                await asyncio.sleep(1)
            except Exception:
                continue
    except Exception as e:
        log.warning("  wildyogi.info failed: %s", e)

    if all_chunks:
        save_chunks(all_chunks, "sharma_wildyogi.jsonl")
    return len(all_chunks)


# ─────────────────────────────────────────────────────────────────────────────
# PART 5 — shailendrasharma.org: Yoga Darshan + 18 Gita PDFs + HYP
# ─────────────────────────────────────────────────────────────────────────────
async def fetch_shailendrasharmaorg(session) -> int:
    """Fetch official content from shailendrasharma.org."""
    log.info("\n=== SHAILENDRASHARMA.ORG — Official Texts ===")
    total = 0

    # 1. Yoga Darshan
    yoga_txt = SHARMA_TXT / "yoga_darshan.txt"
    if not yoga_txt.exists() or yoga_txt.stat().st_size < 2000:
        try:
            html = await fetch_text(session, "https://www.shailendrasharma.org/yogadarshan")
            m = re.search(r'<h1[^>]*>.*?Yoga Darshan.*?</h1>(.*?)(?:©2011|shailendra\.ru|</body)', html, re.DOTALL | re.I)
            content = strip_html(m.group(1) if m else html)
            full = f"Yoga Darshan: Commentary on Patanjali's Yoga Sutras\nAuthor: Sri Sri Shailendra Sharma\nSource: shailendrasharma.org\n\n{content}"
            yoga_txt.write_text(full, encoding="utf-8")
            chunks = make_chunks(full, "yoga_darshan",
                                 "Yoga Darshan — Patanjali Commentary by Shailendra Sharma",
                                 "darshana", "shailendrasharma.org (official)")
            if chunks:
                save_chunks(chunks, "sharma_yoga_darshan.jsonl")
                total += len(chunks)
            log.info("  Yoga Darshan: %d chunks", len(chunks))
        except Exception as e:
            log.warning("  Yoga Darshan failed: %s", e)

    # 2. Hatha Yoga Pradipika PDF
    hyp_dest = SHARMA_PDF / "hatha_yoga_pradipika_sharma.pdf"
    hyp_txt = SHARMA_TXT / "hatha_yoga_pradipika_sharma.txt"
    if not hyp_txt.exists() or hyp_txt.stat().st_size < 2000:
        ok = await fetch_bytes(session, "http://www.shailendrasharma.org/wp-content/uploads/2016/03/HYP_final.pdf", hyp_dest)
        if ok:
            raw = extract_pdf_text(hyp_dest)
            if raw:
                full = f"Hatha Yoga Pradipika — Commentary by Sri Sri Shailendra Sharma\nSource: shailendrasharma.org\n\n{raw}"
                hyp_txt.write_text(full, encoding="utf-8")
                chunks = make_chunks(full, "hyp_sharma",
                                     "Hatha Yoga Pradipika — Shailendra Sharma Commentary",
                                     "nath", "shailendrasharma.org (official PDF)")
                if chunks:
                    save_chunks(chunks, "sharma_hyp.jsonl")
                    total += len(chunks)
                log.info("  HYP: %d chunks", len(chunks))

    # 3. 18 Bhagavad Gita chapter PDFs
    gita_txt = SHARMA_TXT / "yogeshwari_gita_full.txt"
    if not gita_txt.exists() or gita_txt.stat().st_size < 5000:
        all_gita_text = ""
        for i in range(1, 19):
            dest = SHARMA_PDF / f"gita_chapter_{i:02d}.pdf"
            url = f"https://www.shailendrasharma.org/wp-content/uploads/2011/05/gita-ch{i}.pdf"
            ok = await fetch_bytes(session, url, dest)
            if ok:
                text = extract_pdf_text(dest)
                if text:
                    all_gita_text += f"\n\n=== Chapter {i} ===\n{text}"
            await asyncio.sleep(1.5)

        if all_gita_text.strip():
            full = f"Yogeshwari Srimad Bhagavad Gita: A Yogic Commentary\nAuthor: Sri Sri Shailendra Sharma\nSource: shailendrasharma.org\n\n{all_gita_text}"
            gita_txt.write_text(full, encoding="utf-8")
            chunks = make_chunks(full, "yogeshwari_gita_full",
                                 "Yogeshwari Srimad Bhagavad Gita — Shailendra Sharma (Full)",
                                 "kriya-yoga", "shailendrasharma.org (official PDFs)")
            if chunks:
                save_chunks(chunks, "sharma_yogeshwari_full.jsonl")
                total += len(chunks)
            log.info("  Yogeshwari Gita: %d chunks", len(chunks))

    return total


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    import aiohttp
    log.info("=" * 60)
    log.info("PuranGPT Comprehensive Content Fetcher")
    log.info("=" * 60)

    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:

        # Part 1: vedpuran.net Hindi PDFs
        vp_total = await fetch_vedpuran_pdfs(session)

        # Part 2: Shailendra Sharma darshans (guruji.com.ua + gurujidarshan.com)
        darshan_total = await fetch_all_darshans(session)

        # Part 3: anahada.com articles
        anahada_total = await fetch_anahada(session)

        # Part 4: wildyogi.info excerpts
        wild_total = await fetch_wildyogi(session)

        # Part 5: shailendrasharma.org official texts
        org_total = await fetch_shailendrasharmaorg(session)

    log.info("\n" + "=" * 60)
    log.info("✅ FETCH COMPLETE")
    log.info("=" * 60)
    log.info("  vedpuran.net PDFs:       %d chunks", vp_total)
    log.info("  Sharma Darshans:         %d new sessions", darshan_total)
    log.info("  Anahada articles:        %d chunks", anahada_total)
    log.info("  WildYogi excerpts:       %d chunks", wild_total)
    log.info("  Shailendrasharma.org:    %d chunks", org_total)
    log.info("")
    log.info("Next steps:")
    log.info("  1. python index_sharma_texts.py   ← add new chunks to ChromaDB + BM25")
    log.info("  2. scp -r data/chunks/ server:data/  ← sync to server")
    log.info("  3. docker compose restart backend  ← reload BM25 index")


if __name__ == "__main__":
    asyncio.run(main())
