"""
PuranGPT — Puranic Text Downloader
====================================
Downloads the 18 Mahapuranas and other Hindu sacred texts (Ramayana,
Mahabharata, Bhagavad Gita, Upanishads, Yoga texts) from vedpuran.net
with fallbacks to GRETIL and sacred-texts.com.

Features
--------
* Async downloading with aiohttp (concurrent but rate-limited)
* Exponential backoff with jitter on 429 / 5xx errors (via tenacity)
* Per-server rate limiting (respectful to public servers)
* Rich progress bars
* Resume support — skips already-downloaded files
* CLI entry point with argparse

Usage
-----
    python downloader.py                    # download everything
    python downloader.py --texts bhagavata agni vishnu
    python downloader.py --category mahapuranas
    python downloader.py --list             # show all available texts
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import aiofiles
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TaskID,
)
from rich.logging import RichHandler
from rich.table import Table
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("purangpt.downloader")
console = Console()

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TextSource:
    """Represents one downloadable sacred text with primary + fallback URLs."""

    name: str                        # Human-readable name, e.g. "Bhagavata Purana"
    key: str                         # Short key used in filenames, e.g. "bhagavata"
    category: str                    # Category: mahapuranas / epics / upanishads / yoga
    primary_urls: List[str]          # Try these in order (vedpuran.net first)
    fallback_urls: List[str]         # GRETIL / sacred-texts.com / archive.org
    language: str = "hindi"          # Primary language of the source
    volumes: int = 1                 # Multi-volume texts (Skanda Purana = 7 vols)
    notes: str = ""                  # Any useful notes about the text

    def all_urls(self) -> List[str]:
        """Return primary + fallback URLs in priority order."""
        return self.primary_urls + self.fallback_urls


@dataclass
class DownloadResult:
    """Outcome of a single download attempt."""

    key: str
    volume: int
    success: bool
    file_path: Optional[Path] = None
    url_used: Optional[str] = None
    error: Optional[str] = None
    skipped: bool = False           # True if file already existed


# ---------------------------------------------------------------------------
# Master catalog of all texts
# ---------------------------------------------------------------------------

def _build_catalog() -> Dict[str, TextSource]:
    """
    Build the complete catalog of texts to download.

    URL notes
    ---------
    vedpuran.net follows the pattern:
        https://www.vedpuran.net/download/<name>-puran.pdf
    For multi-volume texts, volumes are suffixed with -1, -2, etc.
    sacred-texts.com hosts plain-text/HTML versions.
    GRETIL (Göttingen Register of Electronic Texts in Indian Languages)
    hosts scholarly transliterated Sanskrit.
    archive.org hosts scanned PDFs.
    """

    # ---- 18 Mahapuranas ------------------------------------------------
    mahapuranas: List[TextSource] = [
        TextSource(
            name="Agni Purana",
            key="agni",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/agni-puran.pdf",
                "https://www.vedpuran.net/agni-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/AgniPuranaInHindi/Agni-Purana-Hindi.pdf",
                "https://archive.org/download/agni-purana_202101/agni_purana.pdf",
            ],
            language="hindi",
            notes="Contains 383 chapters on cosmology, astronomy, medicine, weaponry, poetics",
        ),
        TextSource(
            name="Bhagavata Purana",
            key="bhagavata",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/bhagwat-puran.pdf",
                "https://www.vedpuran.net/shrimad-bhagwat-mahapuran/",
            ],
            fallback_urls=[
                "https://archive.org/download/BhagavataPuranaHindi/bhagavata_purana_hindi.pdf",
                "https://sacred-texts.com/hin/sbh01/index.htm",
                "https://archive.org/download/srimad-bhagavatam-cantos-1-12/Srimad_Bhagavatam_Hindi.pdf",
            ],
            language="hindi",
            notes="12 Skandhas; most celebrated of all Puranas — Vaishnava",
        ),
        TextSource(
            name="Bhavishya Purana",
            key="bhavishya",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/bhavishya-puran.pdf",
                "https://www.vedpuran.net/bhavishya-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/BhavishyaPuranaHindi/Bhavishya-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Prophecy-focused Purana; 4 Parvas",
        ),
        TextSource(
            name="Brahma Purana",
            key="brahma",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/brahma-puran.pdf",
                "https://www.vedpuran.net/brahma-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/BrahmaPuranaHindi/Brahma-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Adi Purana; 246 chapters on creation, geography, Odisha",
        ),
        TextSource(
            name="Brahmanda Purana",
            key="brahmanda",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/brahmand-puran.pdf",
                "https://www.vedpuran.net/brahmand-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/BrahmandaPuranaHindi/Brahmanda-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Contains Lalita Sahasranama and Adhyatma Ramayana",
        ),
        TextSource(
            name="Brahma Vaivarta Purana",
            key="brahma_vaivarta",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/brahma-vaivarta-puran.pdf",
                "https://www.vedpuran.net/brahma-vaivarta-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/BrahmaVaivartaPuranaHindi/Brahma-Vaivarta-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="4 Kandas; focuses on Krishna and Radha",
        ),
        TextSource(
            name="Garuda Purana",
            key="garuda",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/garuda-puran.pdf",
                "https://www.vedpuran.net/garuda-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/GarudaPuranaHindi/Garuda-Purana-Hindi.pdf",
                "https://sacred-texts.com/hin/gpu/index.htm",
            ],
            language="hindi",
            notes="Discusses death rites, the afterlife, Vishnu worship",
        ),
        TextSource(
            name="Kurma Purana",
            key="kurma",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/kurma-puran.pdf",
                "https://www.vedpuran.net/kurma-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/KurmaPuranaHindi/Kurma-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Kurma avatar; Ishvara Gita; 2 Samhitas",
        ),
        TextSource(
            name="Linga Purana",
            key="linga",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/ling-puran.pdf",
                "https://www.vedpuran.net/ling-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/LingaPuranaHindi/Linga-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Shaiva text; origin of Linga worship; 163 chapters",
        ),
        TextSource(
            name="Markandeya Purana",
            key="markandeya",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/markandey-puran.pdf",
                "https://www.vedpuran.net/markandey-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/MarkandeyaPuranaHindi/Markandeya-Purana-Hindi.pdf",
                "https://sacred-texts.com/hin/m8/index.htm",
            ],
            language="hindi",
            notes="Contains Devi Mahatmya (Durga Saptashati); 137 chapters",
        ),
        TextSource(
            name="Matsya Purana",
            key="matsya",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/matsya-puran.pdf",
                "https://www.vedpuran.net/matsya-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/MatyaPuranaHindi/Matsya-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Matsya avatar; 291 chapters on cosmogony",
        ),
        TextSource(
            name="Narada Purana",
            key="narada",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/narad-puran.pdf",
                "https://www.vedpuran.net/narad-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/NaradaPuranaHindi/Narada-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Also called Naradiya; 2 parts; discusses bhakti and music",
        ),
        TextSource(
            name="Padma Purana",
            key="padma",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/padma-puran.pdf",
                "https://www.vedpuran.net/padma-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/PadmaPuranaHindi/Padma-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="5 Khandas; Vaishnava; contains Rama stories",
        ),
        TextSource(
            name="Shiva Purana",
            key="shiva",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/shiv-puran.pdf",
                "https://www.vedpuran.net/shiv-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/ShivaPuranaHindi/Shiva-Purana-Hindi.pdf",
                "https://archive.org/download/shiva-purana-hindi-all-7-samhitas/Shiva-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="7 Samhitas; major Shaiva text; Shiva's cosmology",
        ),
        TextSource(
            name="Skanda Purana",
            key="skanda",
            category="mahapuranas",
            primary_urls=[
                # Skanda is massive (7 Khanda volumes); vedpuran.net has vol 1
                "https://www.vedpuran.net/download/skand-puran.pdf",
                "https://www.vedpuran.net/skanda-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/SkandaPuranaHindi1/Skanda-Purana-Hindi-Vol-1.pdf",
                "https://archive.org/download/SkandaPuranaHindi2/Skanda-Purana-Hindi-Vol-2.pdf",
                "https://archive.org/download/SkandaPuranaHindi3/Skanda-Purana-Hindi-Vol-3.pdf",
                "https://archive.org/download/SkandaPuranaHindi4/Skanda-Purana-Hindi-Vol-4.pdf",
            ],
            language="hindi",
            volumes=4,
            notes="Largest Purana; 81,000 shlokas; 7 Khandas",
        ),
        TextSource(
            name="Vamana Purana",
            key="vamana",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/vaman-puran.pdf",
                "https://www.vedpuran.net/vaman-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/VamanaPuranaHindi/Vamana-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Vamana avatar; 95 chapters",
        ),
        TextSource(
            name="Varaha Purana",
            key="varaha",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/varah-puran.pdf",
                "https://www.vedpuran.net/varah-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/VarahaPuranaHindi/Varaha-Purana-Hindi.pdf",
            ],
            language="hindi",
            notes="Varaha avatar; 217 chapters",
        ),
        TextSource(
            name="Vishnu Purana",
            key="vishnu",
            category="mahapuranas",
            primary_urls=[
                "https://www.vedpuran.net/download/vishnu-puran.pdf",
                "https://www.vedpuran.net/vishnu-puran/",
            ],
            fallback_urls=[
                "https://archive.org/download/VishnuPuranaHindi/Vishnu-Purana-Hindi.pdf",
                "https://sacred-texts.com/hin/vp/index.htm",
            ],
            language="hindi",
            notes="6 Amsas; Vaishnava; foundational Purana by Parashara",
        ),
    ]

    # ---- Epics ---------------------------------------------------------
    epics: List[TextSource] = [
        TextSource(
            name="Ramayana (Valmiki)",
            key="ramayana",
            category="epics",
            primary_urls=[
                "https://www.vedpuran.net/download/valmiki-ramayan.pdf",
                "https://www.vedpuran.net/valmiki-ramayan/",
            ],
            fallback_urls=[
                "https://archive.org/download/ValmikiRamayanaInHindi/Valmiki-Ramayana-Hindi-Full.pdf",
                "https://sacred-texts.com/hin/rama/index.htm",
            ],
            language="hindi",
            volumes=2,
            notes="7 Kandas; ~24,000 shlokas",
        ),
        TextSource(
            name="Mahabharata",
            key="mahabharata",
            category="epics",
            primary_urls=[
                "https://www.vedpuran.net/download/mahabharat.pdf",
                "https://www.vedpuran.net/mahabharat/",
            ],
            fallback_urls=[
                "https://archive.org/download/MahabharataAllVolumesHindi/Mahabharata-Hindi.pdf",
                "https://sacred-texts.com/hin/maha/index.htm",
            ],
            language="hindi",
            volumes=3,
            notes="18 Parvas + Harivamsa; ~100,000 shlokas",
        ),
        TextSource(
            name="Bhagavad Gita",
            key="bhagavad_gita",
            category="epics",
            primary_urls=[
                "https://www.vedpuran.net/download/bhagwat-geeta.pdf",
                "https://www.vedpuran.net/bhagwat-geeta/",
            ],
            fallback_urls=[
                "https://archive.org/download/BhagavadGitaHindi/Bhagavad-Gita-Hindi.pdf",
                "https://sacred-texts.com/hin/gita/index.htm",
            ],
            language="hindi",
            notes="18 chapters; 700 shlokas; from Mahabharata Bhishmaparva",
        ),
    ]

    # ---- Major Upanishads (108) -----------------------------------------
    upanishads: List[TextSource] = [
        TextSource(
            name="108 Upanishads",
            key="upanishads_108",
            category="upanishads",
            primary_urls=[
                "https://www.vedpuran.net/download/108-upanishad.pdf",
            ],
            fallback_urls=[
                "https://archive.org/download/108UpanishadsinSanskritHindi/108-Upanishads-Hindi.pdf",
                "https://sacred-texts.com/hin/upan/index.htm",
            ],
            language="hindi",
            notes="All 108 Upanishads; Isha, Kena, Katha, Prashna, Mundaka, Mandukya, Aitareya, Taittiriya, Chandogya, Brihadaranyaka, etc.",
        ),
        TextSource(
            name="Isha Upanishad",
            key="isha_upanishad",
            category="upanishads",
            primary_urls=[
                "https://www.vedpuran.net/download/isha-upanishad.pdf",
            ],
            fallback_urls=[
                "https://sacred-texts.com/hin/upan/up01.htm",
            ],
            language="sanskrit",
            notes="18 verses; from Shukla Yajurveda",
        ),
        TextSource(
            name="Kena Upanishad",
            key="kena_upanishad",
            category="upanishads",
            primary_urls=[
                "https://www.vedpuran.net/download/kena-upanishad.pdf",
            ],
            fallback_urls=[
                "https://sacred-texts.com/hin/upan/up02.htm",
            ],
            language="sanskrit",
            notes="Samaveda; 4 sections on Brahman",
        ),
        TextSource(
            name="Katha Upanishad",
            key="katha_upanishad",
            category="upanishads",
            primary_urls=[
                "https://www.vedpuran.net/download/katha-upanishad.pdf",
            ],
            fallback_urls=[
                "https://sacred-texts.com/hin/upan/up03.htm",
            ],
            language="sanskrit",
            notes="Yama teaches Nachiketa; 2 Adhyayas",
        ),
        TextSource(
            name="Chandogya Upanishad",
            key="chandogya_upanishad",
            category="upanishads",
            primary_urls=[
                "https://www.vedpuran.net/download/chandogya-upanishad.pdf",
            ],
            fallback_urls=[
                "https://sacred-texts.com/hin/upan/up07.htm",
            ],
            language="sanskrit",
            notes="Samaveda; 8 Prapathakas; Tat tvam asi",
        ),
        TextSource(
            name="Brihadaranyaka Upanishad",
            key="brihadaranyaka_upanishad",
            category="upanishads",
            primary_urls=[
                "https://www.vedpuran.net/download/brihadaranyaka-upanishad.pdf",
            ],
            fallback_urls=[
                "https://sacred-texts.com/hin/upan/up08.htm",
            ],
            language="sanskrit",
            notes="Largest Upanishad; Yajnavalkya's teachings",
        ),
        TextSource(
            name="Mandukya Upanishad",
            key="mandukya_upanishad",
            category="upanishads",
            primary_urls=[
                "https://www.vedpuran.net/download/mandukya-upanishad.pdf",
            ],
            fallback_urls=[
                "https://sacred-texts.com/hin/upan/up06.htm",
            ],
            language="sanskrit",
            notes="12 verses; Atharvaveda; Om and 4 states of consciousness",
        ),
    ]

    # ---- Yoga Texts ----------------------------------------------------
    yoga_texts: List[TextSource] = [
        TextSource(
            name="Yoga Sutras of Patanjali",
            key="yoga_sutras",
            category="yoga",
            primary_urls=[
                "https://www.vedpuran.net/download/patanjali-yoga-sutra.pdf",
            ],
            fallback_urls=[
                "https://archive.org/download/YogaSutrasOfPatanjali/Yoga-Sutras-Patanjali-Hindi.pdf",
                "https://sacred-texts.com/hin/yogasutr.htm",
            ],
            language="sanskrit",
            notes="196 sutras in 4 Padas; foundation of Raja Yoga",
        ),
        TextSource(
            name="Hatha Yoga Pradipika",
            key="hatha_yoga_pradipika",
            category="yoga",
            primary_urls=[
                "https://www.vedpuran.net/download/hatha-yoga-pradipika.pdf",
            ],
            fallback_urls=[
                "https://archive.org/download/HathaYogaPradipika/Hatha-Yoga-Pradipika-Hindi.pdf",
                "https://sacred-texts.com/hin/hyp/index.htm",
            ],
            language="hindi",
            notes="4 chapters; asanas, pranayama, mudras, samadhi",
        ),
        TextSource(
            name="Yoga Vasistha",
            key="yoga_vasistha",
            category="yoga",
            primary_urls=[
                "https://www.vedpuran.net/download/yoga-vasistha.pdf",
            ],
            fallback_urls=[
                "https://archive.org/download/YogaVasisthaHindi/Yoga-Vasistha-Hindi.pdf",
            ],
            language="hindi",
            volumes=2,
            notes="Laghu Yoga Vasistha; 6 Prakaranas; Advaita Vedanta",
        ),
    ]

    # ---- Combine all into dict keyed by short key ----------------------
    catalog: Dict[str, TextSource] = {}
    for ts in mahapuranas + epics + upanishads + yoga_texts:
        catalog[ts.key] = ts
    return catalog


CATALOG: Dict[str, TextSource] = _build_catalog()

# ---------------------------------------------------------------------------
# Per-domain rate limits (max concurrent requests)
# ---------------------------------------------------------------------------
DOMAIN_SEMAPHORES: Dict[str, asyncio.Semaphore] = {
    "www.vedpuran.net": asyncio.Semaphore(2),   # Be very gentle
    "archive.org":      asyncio.Semaphore(3),
    "sacred-texts.com": asyncio.Semaphore(2),
    "default":          asyncio.Semaphore(2),
}

# Minimum seconds to wait between requests to the same domain
DOMAIN_MIN_DELAY: Dict[str, float] = {
    "www.vedpuran.net": 3.0,
    "archive.org": 1.0,
    "sacred-texts.com": 2.0,
    "default": 2.0,
}

_last_request_time: Dict[str, float] = {}


def _get_semaphore(url: str) -> asyncio.Semaphore:
    """Return the rate-limit semaphore for the given URL's domain."""
    domain = urlparse(url).netloc
    return DOMAIN_SEMAPHORES.get(domain, DOMAIN_SEMAPHORES["default"])


async def _respect_rate_limit(url: str) -> None:
    """Sleep if necessary to respect per-domain minimum delay."""
    domain = urlparse(url).netloc
    min_delay = DOMAIN_MIN_DELAY.get(domain, DOMAIN_MIN_DELAY["default"])
    last = _last_request_time.get(domain, 0.0)
    elapsed = time.monotonic() - last
    if elapsed < min_delay:
        jitter = random.uniform(0, 0.5)  # Up to 0.5 s random jitter
        await asyncio.sleep(min_delay - elapsed + jitter)
    _last_request_time[domain] = time.monotonic()


# ---------------------------------------------------------------------------
# Core download logic
# ---------------------------------------------------------------------------

async def _download_url(
    session: aiohttp.ClientSession,
    url: str,
    dest: Path,
    progress: Progress,
    task_id: TaskID,
) -> bool:
    """
    Download a single URL to dest with streaming.

    Returns True on success, False on failure (caller tries next URL).
    """
    sem = _get_semaphore(url)
    async with sem:
        await _respect_rate_limit(url)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status == 404:
                    logger.debug("404 Not Found: %s", url)
                    return False
                resp.raise_for_status()

                total = int(resp.headers.get("Content-Length", 0))
                if total:
                    progress.update(task_id, total=total)

                dest.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(dest, "wb") as f:
                    downloaded = 0
                    async for chunk in resp.content.iter_chunked(65_536):  # 64 KB chunks
                        await f.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task_id, advance=len(chunk))
                return True

        except (aiohttp.ClientResponseError, aiohttp.ClientConnectorError) as exc:
            logger.debug("HTTP error for %s: %s", url, exc)
            return False
        except asyncio.TimeoutError:
            logger.debug("Timeout for %s", url)
            return False


# Retry wrapper: up to 5 attempts, exponential backoff with jitter (1–30 s)
async def _download_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    dest: Path,
    progress: Progress,
    task_id: TaskID,
) -> bool:
    """Retry _download_url up to 5 times with exponential backoff."""
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        success = await _download_url(session, url, dest, progress, task_id)
        if success:
            return True
        if attempt < max_attempts:
            wait = min(2 ** attempt + random.uniform(0, 1), 30)
            logger.debug("Attempt %d failed for %s; retrying in %.1fs", attempt, url, wait)
            await asyncio.sleep(wait)
    return False


# ---------------------------------------------------------------------------
# PuranDownloader — main class
# ---------------------------------------------------------------------------

class PuranDownloader:
    """
    Async downloader for Hindu sacred texts.

    Parameters
    ----------
    output_dir : Path
        Root directory where downloaded files are saved.
        Structure: output_dir/{key}/filename.pdf (or _vol1.pdf, _vol2.pdf)
    max_concurrent : int
        Global limit on simultaneous downloads across all domains.
    user_agent : str
        HTTP User-Agent header sent with every request.
    """

    DEFAULT_USER_AGENT = (
        "PuranGPT-Downloader/1.0 "
        "(Academic/non-commercial use; Hindu sacred texts; "
        "contact: purangpt@example.com)"
    )

    def __init__(
        self,
        output_dir: Path = Path("data/raw_pdfs"),
        max_concurrent: int = 4,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent
        self.user_agent = user_agent
        self._global_sem = asyncio.Semaphore(max_concurrent)
        self._state_file = output_dir / ".download_state.json"
        self._downloaded_files: Dict[str, List[str]] = {}  # key -> [file_paths]
        self._load_state()

    # ------------------------------------------------------------------
    # State persistence (resume support)
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Load previously downloaded file registry from JSON state file."""
        if self._state_file.exists():
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    self._downloaded_files = json.load(f)
                logger.debug("Loaded download state: %d entries", len(self._downloaded_files))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not load state file: %s", e)
                self._downloaded_files = {}

    def _save_state(self) -> None:
        """Persist download state to disk."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_file, "w", encoding="utf-8") as f:
            json.dump(self._downloaded_files, f, indent=2)

    def _is_downloaded(self, key: str, volume: int) -> Optional[Path]:
        """
        Check if a text (+ volume) is already downloaded.

        Returns the existing Path if found, None otherwise.
        """
        files = self._downloaded_files.get(key, [])
        vol_suffix = f"_vol{volume}" if volume > 0 else ""
        for fp in files:
            p = Path(fp)
            if vol_suffix in p.stem and p.exists():
                return p
        return None

    # ------------------------------------------------------------------
    # Destination path computation
    # ------------------------------------------------------------------

    def _dest_path(self, source: TextSource, volume: int = 0) -> Path:
        """
        Compute the destination path for a download.

        Volume == 0 means single-volume text.
        """
        folder = self.output_dir / source.key
        folder.mkdir(parents=True, exist_ok=True)
        suffix = f"_vol{volume}" if volume > 0 else ""
        filename = f"{source.key}{suffix}.pdf"
        return folder / filename

    # ------------------------------------------------------------------
    # Single-text download
    # ------------------------------------------------------------------

    async def _download_source(
        self,
        session: aiohttp.ClientSession,
        source: TextSource,
        volume: int,
        urls: List[str],
        progress: Progress,
    ) -> DownloadResult:
        """
        Try each URL in order until one succeeds.

        Parameters
        ----------
        volume : int
            0 for single-volume, 1+ for multi-volume texts.
        urls : list[str]
            Ordered list of URLs to attempt.
        """
        # Check if already downloaded
        existing = self._is_downloaded(source.key, volume)
        if existing and existing.exists():
            return DownloadResult(
                key=source.key, volume=volume,
                success=True, file_path=existing, skipped=True,
            )

        dest = self._dest_path(source, volume)
        vol_label = f" Vol {volume}" if volume > 0 else ""
        task_label = f"[cyan]{source.name}{vol_label}[/cyan]"

        task_id = progress.add_task(task_label, total=None, start=False)
        progress.start_task(task_id)

        async with self._global_sem:
            for url in urls:
                logger.debug("Trying URL: %s → %s", url, dest)
                success = await _download_with_retry(session, url, dest, progress, task_id)
                if success:
                    # Record in state
                    self._downloaded_files.setdefault(source.key, [])
                    self._downloaded_files[source.key].append(str(dest))
                    self._save_state()
                    progress.update(task_id, description=f"[green]✓ {source.name}{vol_label}[/green]")
                    progress.stop_task(task_id)
                    return DownloadResult(
                        key=source.key, volume=volume,
                        success=True, file_path=dest, url_used=url,
                    )

            # All URLs failed
            progress.update(task_id, description=f"[red]✗ {source.name}{vol_label}[/red]")
            progress.stop_task(task_id)
            if dest.exists():
                dest.unlink()  # Remove partial download
            return DownloadResult(
                key=source.key, volume=volume, success=False,
                error=f"All {len(urls)} URLs failed",
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def download_texts(
        self,
        keys: Optional[List[str]] = None,
        category: Optional[str] = None,
    ) -> List[DownloadResult]:
        """
        Download one or more texts.

        Parameters
        ----------
        keys : list[str] | None
            Specific text keys to download. If None, all texts are downloaded
            (subject to `category` filter).
        category : str | None
            If provided, only download texts of this category:
            'mahapuranas', 'epics', 'upanishads', 'yoga'.

        Returns
        -------
        list[DownloadResult]
            One result per volume per text.
        """
        # Build list of (source, volume, urls) tuples to download
        tasks: List[Tuple[TextSource, int, List[str]]] = []

        sources: List[TextSource] = []
        if keys:
            for k in keys:
                if k in CATALOG:
                    sources.append(CATALOG[k])
                else:
                    logger.warning("Unknown text key: '%s' — skipping", k)
        elif category:
            sources = [s for s in CATALOG.values() if s.category == category]
        else:
            sources = list(CATALOG.values())

        for source in sources:
            if source.volumes == 1:
                tasks.append((source, 0, source.all_urls()))
            else:
                # Multi-volume: try volume-specific URLs for fallbacks
                for vol in range(1, source.volumes + 1):
                    # For multi-volume, some fallback URLs are indexed by position
                    vol_urls = list(source.primary_urls)
                    # Add volume-specific fallback URLs if available
                    for url in source.fallback_urls:
                        # Many archive.org multi-vol PDFs have -Vol-N or _vol_N in URL
                        vol_url = url  # Fallback: use as-is (server may 404, we'll skip)
                        vol_urls.append(vol_url)
                    tasks.append((source, vol, vol_urls))

        if not tasks:
            logger.warning("No texts to download.")
            return []

        # HTTP session with browser-like headers
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/pdf,application/octet-stream,*/*",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8,sa;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        }
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False)

        results: List[DownloadResult] = []

        console.rule("[bold cyan]PuranGPT Text Downloader[/bold cyan]")
        console.print(f"Downloading [bold]{len(tasks)}[/bold] text(s) to [cyan]{self.output_dir}[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            refresh_per_second=4,
        ) as progress:
            async with aiohttp.ClientSession(
                headers=headers, connector=connector
            ) as session:
                # Batch concurrently but respect semaphores
                coros = [
                    self._download_source(session, source, vol, urls, progress)
                    for source, vol, urls in tasks
                ]
                results = await asyncio.gather(*coros, return_exceptions=False)

        # Summary report
        succeeded = [r for r in results if r.success and not r.skipped]
        skipped   = [r for r in results if r.skipped]
        failed    = [r for r in results if not r.success]

        table = Table(title="Download Summary", show_lines=True)
        table.add_column("Text", style="cyan")
        table.add_column("Volume", justify="center")
        table.add_column("Status", justify="center")
        table.add_column("Path / Error")

        for r in results:
            if r.skipped:
                status = "[yellow]SKIPPED[/yellow]"
                info = str(r.file_path)
            elif r.success:
                status = "[green]OK[/green]"
                info = str(r.file_path)
            else:
                status = "[red]FAILED[/red]"
                info = r.error or "Unknown error"

            vol_str = str(r.volume) if r.volume > 0 else "—"
            table.add_row(r.key, vol_str, status, info)

        console.print(table)
        console.print(
            f"\n[green]{len(succeeded)} downloaded[/green] | "
            f"[yellow]{len(skipped)} skipped[/yellow] | "
            f"[red]{len(failed)} failed[/red]"
        )

        return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _list_catalog() -> None:
    """Print a Rich table of all available texts."""
    table = Table(title="PuranGPT — Available Sacred Texts", show_lines=True)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Category")
    table.add_column("Vols", justify="center")
    table.add_column("Language")
    table.add_column("Notes")

    for key, source in CATALOG.items():
        table.add_row(
            key,
            source.name,
            source.category,
            str(source.volumes),
            source.language,
            source.notes[:60] + ("…" if len(source.notes) > 60 else ""),
        )
    console.print(table)


def main() -> None:
    """CLI entry point for the downloader."""
    parser = argparse.ArgumentParser(
        prog="purangpt-downloader",
        description="Download Hindu sacred texts (Puranas, Epics, Upanishads, Yoga texts)",
    )
    parser.add_argument(
        "--texts", nargs="+", metavar="KEY",
        help="Specific text keys to download (see --list for available keys)",
    )
    parser.add_argument(
        "--category",
        choices=["mahapuranas", "epics", "upanishads", "yoga"],
        help="Download all texts of a specific category",
    )
    parser.add_argument(
        "--output-dir", default="data/raw_pdfs", metavar="DIR",
        help="Output directory for downloaded PDFs (default: data/raw_pdfs)",
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=3, metavar="N",
        help="Maximum simultaneous downloads (default: 3)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available texts and exit",
    )
    args = parser.parse_args()

    if args.list:
        _list_catalog()
        return

    downloader = PuranDownloader(
        output_dir=Path(args.output_dir),
        max_concurrent=args.max_concurrent,
    )

    asyncio.run(
        downloader.download_texts(
            keys=args.texts,
            category=args.category,
        )
    )


if __name__ == "__main__":
    main()
