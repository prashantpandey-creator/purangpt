"""
PuranGPT — Fetch Missing Texts
================================
Downloads the 5 missing Puranas + empty GRETIL texts.
Run this from the purangpt/ directory:

    python fetch_missing_texts.py

What this downloads:
  - Bhavishya Purana     → GRETIL Sanskrit (if available) + Hindi PDF
  - Brahma Vaivarta Purana → Hindi PDF from archive.org
  - Padma Purana         → GRETIL Sanskrit + Hindi PDF
  - Skanda Purana        → GRETIL Sanskrit (Skandhas 1-31)
  - Varaha Purana        → Hindi PDF from archive.org

Also fills empty GRETIL dirs:
  - Yoga Sutras, Samkhya Karika, Brahma Sutras, Mahabharata,
    Hatha Yoga Pradipika, Shiva Samhita, Linga Purana Part 2,
    Brihadaranyaka, Chandogya, Katha Upanishad, Gorakshashataka
"""

from __future__ import annotations
import asyncio
import aiohttp
import aiofiles
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
log = logging.getLogger("fetch_missing")

BASE     = Path(__file__).parent
GRETIL   = BASE / "data/raw_texts/gretil"
RAW_PDFS = BASE / "data/raw_pdfs"

# ── GRETIL plain-text URLs ─────────────────────────────────────────────────
# All from https://gretil.sub.uni-goettingen.de/gretil/corpustei/
GRETIL_BASE = "https://gretil.sub.uni-goettingen.de/gretil/corpustei/"

GRETIL_TEXTS = {
    # Missing Puranas
    "bhavishya":      "sa_bhaviSyapurANa.txt",
    "padma":          "sa_padmapurANa.txt",
    "skanda_1_31":    "sa_skandapurANa01-31.txt",
    "varaha":         "sa_vArAhapurANa.txt",
    "brahma_vaivarta":"sa_brahmavaivartapurANa.txt",
    # Empty dirs that should have content
    "yoga_sutras":    "sa_yogasUtra.txt",
    "samkhya_karika": "sa_sAMkhyakArikA.txt",
    "brahmasutras":   "sa_brahmasUtra.txt",
    "mahabharata":    "sa_mahAbhArata.txt",
    "hatha_yoga_pradipika": "sa_haTayogapradIpikA.txt",
    "shiva_samhita":  "sa_zivasa.txt",
    "linga_2":        "sa_liNgapurANa2.txt",
    "brihadaranyaka": "sa_bRhadAraNyakopaniSad.txt",
    "chandogya":      "sa_chAndogyopaniSad.txt",
    "katha":          "sa_kaThakaupaniSad.txt",
    "goraksha_shataka":"sa_gorakshapaddhati.txt",
    "arthashastra":   "sa_arthasAstra.txt",
    "nyayasutras":    "sa_nyAyasUtra.txt",
    "vaisheshika":    "sa_vaiSeSikasUtra.txt",
    "mimamsa_sutras": "sa_mImAMsAsUtra.txt",
    "vakyapadiya":    "sa_vAkyapadIya.txt",
    "harivamsha":     "sa_harivaMza.txt",
}

# ── Hindi PDF fallbacks (archive.org) ─────────────────────────────────────
HINDI_PDFS = {
    "bhavishya": [
        "https://archive.org/download/BhavishyaPuranaHindi/Bhavishya-Purana-Hindi.pdf",
        "https://archive.org/download/bhavishya-purana_hindi/bhavishya_purana.pdf",
    ],
    "brahma_vaivarta": [
        "https://archive.org/download/BrahmaVaivartaPuranaHindi/Brahma-Vaivarta-Purana-Hindi.pdf",
        "https://www.vedpuran.net/download/brahma-vaivarta-puran.pdf",
    ],
    "padma": [
        "https://archive.org/download/PadmaPuranaHindi/Padma-Purana-Hindi.pdf",
        "https://www.vedpuran.net/download/padma-puran.pdf",
    ],
    "varaha": [
        "https://archive.org/download/VarahaPuranaHindi/Varaha-Purana-Hindi.pdf",
        "https://www.vedpuran.net/download/varah-puran.pdf",
    ],
    "skanda": [
        "https://www.vedpuran.net/download/skand-puran-1.pdf",
        "https://archive.org/download/SkandaPurana/SkandaPurana.pdf",
    ],
}


async def download_file(session: aiohttp.ClientSession, url: str, dest: Path) -> bool:
    """Download a single file. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 10_000:
        log.info("  Skip (exists): %s", dest.name)
        return True
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as r:
            if r.status != 200:
                log.warning("  HTTP %d: %s", r.status, url)
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                async for chunk in r.content.iter_chunked(65536):
                    await f.write(chunk)
            size_kb = dest.stat().st_size // 1024
            log.info("  ✓ %s (%d KB)", dest.name, size_kb)
            return True
    except Exception as e:
        log.warning("  ✗ %s — %s", url, e)
        if dest.exists():
            dest.unlink()
        return False


async def fetch_gretil(session: aiohttp.ClientSession):
    """Download GRETIL Sanskrit plain-text files."""
    log.info("\n=== GRETIL Sanskrit texts ===")
    for key, filename in GRETIL_TEXTS.items():
        dest = GRETIL / key / filename
        if dest.exists() and dest.stat().st_size > 1000:
            log.info("  Skip (exists): %s/%s", key, filename)
            continue
        url = GRETIL_BASE + filename
        log.info("Fetching %s …", key)
        ok = await download_file(session, url, dest)
        if not ok:
            # Try alternative filename patterns
            alt_names = [
                filename.replace("sa_", "").replace(".txt", "_u.txt"),
                filename.replace("purANa", "purana"),
            ]
            for alt in alt_names:
                alt_url = GRETIL_BASE + alt
                ok = await download_file(session, alt_url, GRETIL / key / alt)
                if ok:
                    break
        await asyncio.sleep(1.5)   # Be respectful to GRETIL


async def fetch_hindi_pdfs(session: aiohttp.ClientSession):
    """Download Hindi PDF fallbacks for texts GRETIL doesn't have."""
    log.info("\n=== Hindi PDFs (vedpuran.net / archive.org) ===")
    for key, urls in HINDI_PDFS.items():
        dest_dir = RAW_PDFS / key
        dest = dest_dir / f"{key}.pdf"
        if dest.exists() and dest.stat().st_size > 100_000:
            log.info("  Skip (exists): %s", key)
            continue
        log.info("Fetching Hindi PDF: %s …", key)
        for url in urls:
            ok = await download_file(session, url, dest)
            if ok:
                break
            await asyncio.sleep(2)
        await asyncio.sleep(2)


async def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PuranGPT research bot; scholarly use)",
        "Accept": "*/*",
    }
    connector = aiohttp.TCPConnector(limit=3, ssl=False)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        await fetch_gretil(session)
        await fetch_hindi_pdfs(session)

    log.info("\n✓ Done. Now run:")
    log.info("  python run.py --chunk   # re-chunk all texts")
    log.info("  python run.py --index   # rebuild vector index")


if __name__ == "__main__":
    asyncio.run(main())
