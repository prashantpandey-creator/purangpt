"""
PuranGPT — Shloka-Aware Puranic Text Chunker
=============================================
Splits extracted Puranic text into semantically meaningful chunks aligned
with verse (shloka) boundaries, attaches rich metadata, and saves the
results as JSONL files ready for indexing.

Design Decisions
----------------
* **Shloka boundaries** are detected via Devanagari danda (।) and
  double-danda (॥) punctuation, which reliably marks verse endings in
  Sanskrit and Hindi texts.  Latin-script fallbacks handle transliterated
  or English-translated texts.
* **Chapter markers** are detected by a multilingual regex covering common
  patterns in Hindi, Sanskrit, and English editions (अध्याय, Chapter,
  Adhyaya, Sarga, Kanda, Parva, Skandha, etc.).
* **Metadata extraction** uses regex patterns to parse inline structural
  markers that many published editions include (e.g. "॥ भागवतपुराणे
  द्वितीयस्कन्धे प्रथमोऽध्यायः ॥").
* **Chunk size** is 2-3 verses with 1-verse overlap to preserve context
  across chunk boundaries.  A maximum of 800 tokens is enforced (roughly
  600 characters for Devanagari text).
* Each chunk carries a stable **deterministic ID** based on purana/chapter/
  verse range so identical texts always produce identical IDs.

Output
------
``data/chunks/{purana_key}.jsonl`` — one JSON object per line
``data/chunks/all_chunks.jsonl``   — master file with all chunks

Usage
-----
    chunker = PuranicChunker()
    chunks = chunker.process_extracted_json(path, purana_name="Bhagavata Purana")
    chunker.process_all(Path("data/extracted"), Path("data/chunks"))
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("purangpt.chunker")
console = Console()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum chunk size in characters (≈ 800 tokens for Devanagari)
MAX_CHUNK_CHARS: int = 2400   # ~800 tokens × 3 chars per Devanagari character avg

# Verses per chunk (target window and overlap)
VERSES_PER_CHUNK: int = 3
VERSE_OVERLAP: int = 1

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Verse-ending punctuation (Sanskrit / Hindi)
RE_DANDA = re.compile(r"[।॥]+")

# Double danda specifically (marks complete verse)
RE_DOUBLE_DANDA = re.compile(r"॥")

# Chapter start markers (multilingual)
RE_CHAPTER = re.compile(
    r"""
    (?:
        अध्याय\s*[\u0900-\u097F\d]+    # Hindi: अध्याय १ or अध्याय 1
      | Adhyaya\s+\d+                   # Transliterated
      | Chapter\s+\d+                   # English
      | Sarga\s+\d+                     # Ramayana chapter
      | Kanda\s+\d+                     # Ramayana/Mahabharata section
      | Parva\s+\d+                     # Mahabharata parva
      | Skandha\s+\d+                   # Bhagavata skandha
      | Samhita\s+\d+                   # Shiva Purana samhita
      | Khanda\s+\d+                    # Skanda/other khandas
      | स्कन्ध\s*[\u0900-\u097F\d]+   # Sanskrit skandha
      | काण्ड\s*[\u0900-\u097F\d]+     # Kanda
      | पर्व\s*[\u0900-\u097F\d]+      # Parva
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Verse number patterns embedded in text
RE_VERSE_NUM = re.compile(
    r"""
    (?:
        ॥\s*(\d+)\s*॥                  # ॥ 42 ॥ — most common Sanskrit
      | \|\s*(\d+)\s*\|                 # | 42 | (ASCII variant)
      | (\d+)\.                         # 42. (decimal numbering)
      | \((\d+)\)                       # (42)
    )
    """,
    re.VERBOSE,
)

# Purana self-reference patterns (common in colophons)
RE_PURANA_REF = re.compile(
    r"""
    (?:
        (अग्नि|भागवत|भविष्य|ब्रह्म|ब्रह्माण्ड|ब्रह्मवैवर्त|
         गरुड|कूर्म|लिंग|मार्कण्डेय|मत्स्य|नारद|पद्म|
         शिव|स्कन्द|वामन|वराह|विष्णु)पुराण
      | (Agni|Bhagavata|Bhavishya|Brahma|Brahmanda|BrahmaVaivarta|
         Garuda|Kurma|Linga|Markandeya|Matsya|Narada|Padma|
         Shiva|Skanda|Vamana|Varaha|Vishnu)\s*Purana
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Shloka number range pattern: "1-3", "1 to 3", "1–3"
RE_RANGE = re.compile(r"(\d+)\s*[-–to]+\s*(\d+)")

# ---------------------------------------------------------------------------
# Purana metadata tables
# ---------------------------------------------------------------------------

# Canonical name mapping (key → display name)
PURANA_NAMES: Dict[str, str] = {
    "agni":           "Agni Purana",
    "bhagavata":      "Bhagavata Purana",
    "bhavishya":      "Bhavishya Purana",
    "brahma":         "Brahma Purana",
    "brahmanda":      "Brahmanda Purana",
    "brahma_vaivarta":"Brahma Vaivarta Purana",
    "garuda":         "Garuda Purana",
    "kurma":          "Kurma Purana",
    "linga":          "Linga Purana",
    "markandeya":     "Markandeya Purana",
    "matsya":         "Matsya Purana",
    "narada":         "Narada Purana",
    "padma":          "Padma Purana",
    "shiva":          "Shiva Purana",
    "skanda":         "Skanda Purana",
    "vamana":         "Vamana Purana",
    "varaha":         "Varaha Purana",
    "vishnu":         "Vishnu Purana",
    "ramayana":       "Ramayana",
    "mahabharata":    "Mahabharata",
    "bhagavad_gita":  "Bhagavad Gita",
    "upanishads_108": "108 Upanishads",
    "yoga_sutras":    "Yoga Sutras of Patanjali",
    "hatha_yoga_pradipika": "Hatha Yoga Pradipika",
    "yoga_vasistha":  "Yoga Vasistha",
}

# Section terminology per text (for structured book_section)
SECTION_TERMS: Dict[str, str] = {
    "bhagavata":    "Skandha",
    "shiva":        "Samhita",
    "skanda":       "Khanda",
    "padma":        "Khanda",
    "brahma":       "Adhyaya",
    "ramayana":     "Kanda",
    "mahabharata":  "Parva",
    "yoga_sutras":  "Pada",
    "default":      "Chapter",
}

# Language detection heuristics (Devanagari Unicode range U+0900–U+097F)
RE_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def _detect_language(text: str) -> str:
    """
    Detect whether text is primarily Devanagari (hindi/sanskrit) or English.

    Heuristic: if > 30% of non-whitespace characters are Devanagari → hindi.
    Finer distinction between Sanskrit and Hindi requires NLP tooling; we
    default to 'hindi' for all Devanagari texts.
    """
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return "unknown"
    devanagari_count = sum(1 for c in non_ws if RE_DEVANAGARI.match(c))
    ratio = devanagari_count / len(non_ws)
    if ratio > 0.30:
        return "hindi"          # Hindi or Sanskrit — both use Devanagari
    return "english"


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------

@dataclass
class PuranicChunk:
    """
    A single semantically-bounded chunk of Puranic text.

    Field Notes
    -----------
    id : str
        Deterministic, human-readable ID:
        ``{purana_key}-{chapter:04d}-{verse_start:04d}``
    book_section : str
        High-level section name (Skandha, Kanda, Parva, Khanda, Samhita).
    verse_range : str
        Verse numbers included, e.g. "1-3".  May be empty for prose texts.
    """
    id: str
    purana: str                 # Display name, e.g. "Bhagavata Purana"
    purana_key: str             # Short key, e.g. "bhagavata"
    book_section: str           # e.g. "Skandha 10" / "Kanda 2" / "Chapter 5"
    chapter: int                # Chapter number (0 if unknown)
    verse_range: str            # "1-3"
    text: str
    language: str               # 'hindi' | 'sanskrit' | 'english' | 'unknown'
    source_file: str
    source_page: int            # Starting page number in the source PDF
    word_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.word_count = len(self.text.split())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["word_count"] = self.word_count
        return d


# ---------------------------------------------------------------------------
# PuranicChunker — core class
# ---------------------------------------------------------------------------

class PuranicChunker:
    """
    Splits extracted Puranic text into shloka-aligned chunks with metadata.

    Parameters
    ----------
    verses_per_chunk : int
        Target number of verses per chunk (default 3).
    verse_overlap : int
        Number of verses to overlap between adjacent chunks (default 1).
    max_chars : int
        Hard maximum characters per chunk (default 2400).
    """

    def __init__(
        self,
        verses_per_chunk: int = VERSES_PER_CHUNK,
        verse_overlap: int = VERSE_OVERLAP,
        max_chars: int = MAX_CHUNK_CHARS,
    ) -> None:
        self.verses_per_chunk = verses_per_chunk
        self.verse_overlap = verse_overlap
        self.max_chars = max_chars

    # ------------------------------------------------------------------
    # Verse splitting
    # ------------------------------------------------------------------

    def _split_into_verses(self, text: str) -> List[str]:
        """
        Split a page/block of text into individual verses.

        Strategy:
        1. Split on double danda (॥) — strongest verse boundary signal.
        2. Also split on single danda (।) lines that end a hemistich.
        3. Fall back to line-by-line splitting for prose/English texts.

        Returns a list of non-empty verse strings.
        """
        # Normalise multiple consecutive dandas
        text = re.sub(r"[।॥]{2,}", "॥", text)
        # Split on double danda
        parts = RE_DOUBLE_DANDA.split(text)

        # If very few splits → likely prose or English → use paragraph splits
        if len(parts) < 3:
            # Try splitting on blank lines or single danda
            parts = re.split(r"\n{2,}|।\s*\n", text)

        verses = [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]
        return verses

    # ------------------------------------------------------------------
    # Chapter detection
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_chapter_number(text: str) -> int:
        """
        Extract the chapter number from text near a chapter heading.

        Looks for Devanagari numerals (converted to Arabic) or Arabic digits
        immediately following chapter keywords.
        """
        # Map Devanagari digit characters to ASCII
        deva_to_ascii = str.maketrans("०१२३४५६७८९", "0123456789")
        text_norm = text.translate(deva_to_ascii)

        # Look for digits following chapter markers
        for pattern in [
            r"(?:अध्याय|Adhyaya|Chapter|Sarga|Kanda|Parva|Skandha|Samhita|Khanda)\s*(\d+)",
            r"(\d+)\s*(?:अध्याय|Adhyaya)",
        ]:
            m = re.search(pattern, text_norm, re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, IndexError):
                    pass
        return 0

    @staticmethod
    def _extract_section_name(purana_key: str, chapter: int) -> str:
        """Build a human-readable section name for a chunk."""
        term = SECTION_TERMS.get(purana_key, SECTION_TERMS["default"])
        if chapter > 0:
            return f"{term} {chapter}"
        return term

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_verse_nums(text: str) -> List[int]:
        """Extract all verse numbers found in a text block."""
        nums: List[int] = []
        for m in RE_VERSE_NUM.finditer(text):
            for g in m.groups():
                if g is not None:
                    try:
                        nums.append(int(g))
                    except ValueError:
                        pass
        return sorted(set(nums))

    @staticmethod
    def _make_chunk_id(
        purana_key: str,
        chapter: int,
        verse_start: int,
        chunk_index: int,
    ) -> str:
        """
        Generate a deterministic, human-readable chunk ID.

        Format: ``{key}-ch{chapter:04d}-v{verse:04d}``
        If verse number is unknown (0), use a hash of chapter + index.
        """
        if verse_start > 0:
            return f"{purana_key}-ch{chapter:04d}-v{verse_start:04d}"
        # Fallback: use chunk index within chapter
        return f"{purana_key}-ch{chapter:04d}-i{chunk_index:04d}"

    # ------------------------------------------------------------------
    # Core chunking
    # ------------------------------------------------------------------

    def _chunk_verses(
        self,
        verses: List[str],
        purana_key: str,
        purana_name: str,
        chapter: int,
        section_name: str,
        source_file: str,
        source_page: int,
        language: str,
    ) -> List[PuranicChunk]:
        """
        Group individual verses into chunks with overlap.

        Parameters
        ----------
        verses : list[str]
            Ordered list of verse strings for one chapter.
        """
        chunks: List[PuranicChunk] = []
        n = len(verses)
        step = max(1, self.verses_per_chunk - self.verse_overlap)
        chunk_index = 0

        i = 0
        while i < n:
            window = verses[i : i + self.verses_per_chunk]
            chunk_text = "\n".join(window)

            # Enforce maximum character limit — split large windows
            if len(chunk_text) > self.max_chars:
                # Use only first N verses that fit
                trimmed: List[str] = []
                total = 0
                for v in window:
                    if total + len(v) + 1 > self.max_chars:
                        break
                    trimmed.append(v)
                    total += len(v) + 1
                window = trimmed if trimmed else [window[0][:self.max_chars]]
                chunk_text = "\n".join(window)

            # Extract verse numbers from this window
            verse_nums = self._extract_verse_nums(chunk_text)
            if verse_nums:
                v_start, v_end = verse_nums[0], verse_nums[-1]
                verse_range = f"{v_start}-{v_end}" if v_start != v_end else str(v_start)
                first_verse_num = v_start
            else:
                verse_range = ""
                first_verse_num = 0

            chunk_id = self._make_chunk_id(purana_key, chapter, first_verse_num, chunk_index)

            chunk = PuranicChunk(
                id=chunk_id,
                purana=purana_name,
                purana_key=purana_key,
                book_section=section_name,
                chapter=chapter,
                verse_range=verse_range,
                text=chunk_text.strip(),
                language=language,
                source_file=source_file,
                source_page=source_page,
            )
            chunks.append(chunk)
            chunk_index += 1
            i += step

        return chunks

    # ------------------------------------------------------------------
    # Page-level processing
    # ------------------------------------------------------------------

    def _process_page(
        self,
        page_num: int,
        page_text: str,
        purana_key: str,
        purana_name: str,
        current_chapter: int,
    ) -> Tuple[List[PuranicChunk], int]:
        """
        Process a single page's text and return chunks + updated chapter number.

        Handles chapter boundary detection mid-page.
        """
        if not page_text.strip():
            return [], current_chapter

        # Detect language for this page
        language = _detect_language(page_text)

        # Look for chapter marker on this page
        ch_match = RE_CHAPTER.search(page_text)
        if ch_match:
            new_ch = self._extract_chapter_number(page_text)
            if new_ch > 0:
                current_chapter = new_ch
                logger.debug("Chapter boundary: %d (page %d)", current_chapter, page_num)

        section_name = self._extract_section_name(purana_key, current_chapter)
        verses = self._split_into_verses(page_text)

        if not verses:
            return [], current_chapter

        chunks = self._chunk_verses(
            verses=verses,
            purana_key=purana_key,
            purana_name=purana_name,
            chapter=current_chapter,
            section_name=section_name,
            source_file="",  # Will be filled by caller
            source_page=page_num,
            language=language,
        )
        return chunks, current_chapter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_extracted_json(
        self,
        json_path: Path,
        purana_name: Optional[str] = None,
        purana_key: Optional[str] = None,
    ) -> List[PuranicChunk]:
        """
        Process a single extraction JSON file and return all chunks.

        Parameters
        ----------
        json_path : Path
            Path to a JSON file produced by TextExtractor.
        purana_name : str | None
            Display name. If None, inferred from the filename.
        purana_key : str | None
            Short key. If None, inferred from the filename.

        Returns
        -------
        list[PuranicChunk]
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        source_file: str = data.get("source_file", json_path.stem)
        pages: Dict[str, Any] = data.get("pages", {})

        # Infer purana name / key from filename if not provided
        if purana_key is None:
            # e.g. "bhagavata.json" → "bhagavata"
            # strip any _vol1, _vol2 suffixes
            stem = re.sub(r"_vol\d+$", "", json_path.stem.lower().replace("-", "_"))
            purana_key = stem
        if purana_name is None:
            purana_name = PURANA_NAMES.get(purana_key, purana_key.replace("_", " ").title())

        logger.info("Chunking '%s' (%d pages)…", purana_name, len(pages))

        all_chunks: List[PuranicChunk] = []
        current_chapter: int = 1

        # Process pages in order
        for page_key in sorted(pages.keys(), key=lambda k: int(k)):
            page_data = pages[page_key]
            page_text: str = page_data.get("text", "")
            page_num: int = int(page_key)

            page_chunks, current_chapter = self._process_page(
                page_num=page_num,
                page_text=page_text,
                purana_key=purana_key,
                purana_name=purana_name,
                current_chapter=current_chapter,
            )
            # Fill in source_file (not available inside _process_page)
            for chunk in page_chunks:
                chunk.source_file = source_file
            all_chunks.extend(page_chunks)

        # De-duplicate chunks with identical IDs (can occur at chapter boundaries)
        seen_ids: set[str] = set()
        deduped: List[PuranicChunk] = []
        for chunk in all_chunks:
            if chunk.id not in seen_ids:
                seen_ids.add(chunk.id)
                deduped.append(chunk)

        logger.info(
            "  → %d chunks generated (%d deduplicated)",
            len(deduped), len(all_chunks) - len(deduped),
        )
        return deduped

    def save_chunks_jsonl(self, chunks: List[PuranicChunk], output_path: Path) -> None:
        """Write chunks to a JSONL file (one JSON object per line)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                line = json.dumps(chunk.to_dict(), ensure_ascii=False)
                f.write(line + "\n")
        logger.debug("Saved %d chunks to %s", len(chunks), output_path)

    def process_all(
        self,
        extracted_dir: Path,
        chunks_dir: Path,
        overwrite: bool = False,
    ) -> Dict[str, int]:
        """
        Process all extracted JSON files and write per-purana JSONL chunks.

        Also writes a master ``all_chunks.jsonl`` combining everything.

        Parameters
        ----------
        extracted_dir : Path
            Root directory of extraction JSON files.
        chunks_dir : Path
            Root directory where JSONL chunk files will be saved.
        overwrite : bool
            Re-process already-chunked files.

        Returns
        -------
        dict[str, int]
            Mapping from purana key to chunk count.
        """
        from pathlib import Path
        extracted_dir_path = Path(extracted_dir)
        json_files = sorted(extracted_dir_path.rglob("*.json"))
        if not json_files:
            logger.warning("No extracted JSON files found under %s", extracted_dir)
            return {}

        logger.info("Found %d JSON file(s) to chunk", len(json_files))
        chunks_dir.mkdir(parents=True, exist_ok=True)
        master_path = chunks_dir / "all_chunks.jsonl"
        stats: Dict[str, int] = {}
        all_chunks: List[PuranicChunk] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("Chunking extracted texts…", total=len(json_files))

            for jf in json_files:
                # Infer purana key from file path (parent dir or stem)
                stem = re.sub(r"_vol\d+$", "", jf.stem.lower().replace("-", "_"))
                out_path = chunks_dir / f"{stem}.jsonl"

                progress.update(task, description=f"Chunking [cyan]{jf.name}[/cyan]")

                if out_path.exists() and not overwrite:
                    logger.debug("Skipping (already chunked): %s", jf.name)
                    # Load existing chunk count for stats
                    count = sum(1 for _ in open(out_path, encoding="utf-8"))
                    stats[stem] = count
                    progress.advance(task)
                    continue

                try:
                    chunks = self.process_extracted_json(jf)
                    self.save_chunks_jsonl(chunks, out_path)
                    stats[stem] = len(chunks)
                    all_chunks.extend(chunks)
                except Exception as exc:
                    logger.error("Failed to chunk '%s': %s", jf.name, exc, exc_info=True)
                    stats[stem] = 0
                finally:
                    progress.advance(task)

        # Write master file
        if all_chunks:
            logger.info("Writing master chunk file (%d chunks total)…", len(all_chunks))
            self.save_chunks_jsonl(all_chunks, master_path)
        elif master_path.exists():
            logger.info("Master file already exists (skipping re-write)")

        # Summary
        total = sum(stats.values())
        console.print(
            f"\n[green]Chunking complete.[/green] "
            f"[bold]{total}[/bold] chunks from [bold]{len(stats)}[/bold] texts."
        )
        for key, count in sorted(stats.items(), key=lambda x: -x[1]):
            console.print(f"  [cyan]{key:<30}[/cyan] {count:>6,} chunks")

        return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI wrapper for batch chunking."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="purangpt-chunker",
        description="Chunk extracted Puranic text JSON files into verse-aligned JSONL",
    )
    parser.add_argument(
        "--extracted-dir", default="data/extracted",
        help="Directory containing extraction JSON files (default: data/extracted)",
    )
    parser.add_argument(
        "--chunks-dir", default="data/chunks",
        help="Output directory for JSONL chunk files (default: data/chunks)",
    )
    parser.add_argument(
        "--verses-per-chunk", type=int, default=VERSES_PER_CHUNK,
        help=f"Verses per chunk (default: {VERSES_PER_CHUNK})",
    )
    parser.add_argument(
        "--verse-overlap", type=int, default=VERSE_OVERLAP,
        help=f"Verse overlap between chunks (default: {VERSE_OVERLAP})",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Re-chunk already-processed files",
    )
    args = parser.parse_args()

    chunker = PuranicChunker(
        verses_per_chunk=args.verses_per_chunk,
        verse_overlap=args.verse_overlap,
    )
    chunker.process_all(
        extracted_dir=Path(args.extracted_dir),
        chunks_dir=Path(args.chunks_dir),
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
