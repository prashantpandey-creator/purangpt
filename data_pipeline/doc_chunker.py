"""
Generic Document Chunker
=========================
Splits arbitrary documents (PDFs, DOCX, web pages) into semantic chunks
with section detection, paragraph-based splitting, and overlap — designed
to produce metadata compatible with the existing purana_verses table so
all Explorer endpoints work without changes.

Output: list of chunk dicts ready for embedding + upsert into pgvector.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("purangpt.doc_chunker")

# ── Constants ─────────────────────────────────────────────────────────────

TARGET_TOKENS = 600
MAX_TOKENS = 1000
OVERLAP_TOKENS = 80

# ── Section heading patterns (ordered by specificity) ─────────────────────

_HEADING_PATTERNS = [
    re.compile(r"^#{1,3}\s+.+", re.MULTILINE),                     # Markdown
    re.compile(r"^(?:Chapter|CHAPTER|Part|PART)\s+\d+", re.MULTILINE),  # Chapter N
    re.compile(r"^\d{1,3}\.?\s+[A-Z][A-Za-z\s]{4,80}$", re.MULTILINE), # 1. Introduction
    re.compile(r"^[A-Z][A-Z\s]{8,78}$", re.MULTILINE),              # ALL CAPS lines
]


def _estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def _detect_language(text: str) -> str:
    devanagari = sum(1 for c in text if "ऀ" <= c <= "ॿ")
    if devanagari > len(text) * 0.3:
        return "hindi" if any("अ" <= c <= "ह" for c in text) else "sanskrit"
    return "english"


@dataclass
class Section:
    title: str
    number: int
    paragraphs: list
    start_page: int = 1


def detect_sections(pages: Dict[str, Any]) -> List[Section]:
    """Split extracted pages into sections using heading heuristics."""
    full_text = ""
    page_offsets: list[tuple[int, int]] = []  # (char_offset, page_num)

    for page_key in sorted(pages.keys(), key=lambda k: int(k) if k.isdigit() else 0):
        page = pages[page_key]
        text = page.get("text", "") if isinstance(page, dict) else str(page)
        offset = len(full_text)
        page_offsets.append((offset, int(page_key) if page_key.isdigit() else 1))
        full_text += text + "\n\n"

    if not full_text.strip():
        return []

    heading_positions: list[tuple[int, str]] = []
    for pattern in _HEADING_PATTERNS:
        for m in pattern.finditer(full_text):
            line = m.group().strip()
            if 3 < len(line) < 120:
                heading_positions.append((m.start(), line))

    heading_positions.sort(key=lambda x: x[0])

    # Deduplicate overlapping headings (keep earliest)
    deduped: list[tuple[int, str]] = []
    for pos, title in heading_positions:
        if deduped and pos - deduped[-1][0] < 20:
            continue
        deduped.append((pos, title))

    def _page_for_offset(offset: int) -> int:
        result = 1
        for off, pg in page_offsets:
            if off <= offset:
                result = pg
        return result

    if not deduped:
        paras = _split_paragraphs(full_text)
        return [Section(title="Full Document", number=1, paragraphs=paras, start_page=1)]

    sections: list[Section] = []
    for i, (pos, title) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(full_text)
        body = full_text[pos + len(title):end].strip()
        paras = _split_paragraphs(body)
        if paras:
            sections.append(Section(
                title=_clean_heading(title),
                number=i + 1,
                paragraphs=paras,
                start_page=_page_for_offset(pos),
            ))

    # If there's content before the first heading, prepend it
    if deduped and deduped[0][0] > 100:
        preamble = full_text[:deduped[0][0]].strip()
        paras = _split_paragraphs(preamble)
        if paras:
            sections.insert(0, Section(
                title="Preamble",
                number=0,
                paragraphs=paras,
                start_page=1,
            ))
            for s in sections[1:]:
                s.number += 1

    # Re-number sections sequentially starting from 1
    for i, s in enumerate(sections):
        s.number = i + 1

    return sections


def _split_paragraphs(text: str) -> list[str]:
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip() and len(p.strip()) > 20]


def _clean_heading(title: str) -> str:
    title = re.sub(r"^#{1,3}\s+", "", title).strip()
    if len(title) > 80:
        title = title[:77] + "..."
    return title


def chunk_document(
    pages: Dict[str, Any],
    doc_id: str,
    filename: str,
    user_id: str,
    target_tokens: int = TARGET_TOKENS,
    max_tokens: int = MAX_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Main entry point. Takes extracted pages → returns chunk dicts
    ready for embedding + upsert into purana_verses.

    pages: {"1": {"text": "..."}, "2": {"text": "..."}, ...}
           or {"1": "...", "2": "..."} — both formats accepted.
    """
    sections = detect_sections(pages)
    if not sections:
        return []

    sample = ""
    for s in sections[:3]:
        sample += " ".join(s.paragraphs[:2]) + " "
    language = _detect_language(sample[:2000])

    chunks: list[dict] = []
    for section in sections:
        section_chunks = _chunk_section(
            section, doc_id, filename, user_id, language,
            target_tokens, max_tokens, overlap_tokens,
        )
        chunks.extend(section_chunks)

    return chunks


def _chunk_section(
    section: Section,
    doc_id: str,
    filename: str,
    user_id: str,
    language: str,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[dict]:
    """Split a section's paragraphs into overlapping chunks."""
    if not section.paragraphs:
        return []

    chunks: list[dict] = []
    current_paras: list[str] = []
    current_tokens = 0
    para_idx = 0
    chunk_num = 0

    while para_idx < len(section.paragraphs):
        para = section.paragraphs[para_idx]
        ptok = _estimate_tokens(para)

        # Single paragraph exceeds max — force-split it
        if ptok > max_tokens and not current_paras:
            words = para.split()
            target_words = int(target_tokens / 1.3)
            for i in range(0, len(words), target_words):
                sub = " ".join(words[i:i + target_words])
                chunk_num += 1
                chunks.append(_make_chunk(
                    text=sub, doc_id=doc_id, filename=filename, user_id=user_id,
                    language=language, section=section, chunk_num=chunk_num,
                    para_start=para_idx + 1, para_end=para_idx + 1,
                ))
            para_idx += 1
            continue

        if current_tokens + ptok > max_tokens and current_paras:
            chunk_num += 1
            chunks.append(_make_chunk(
                text="\n\n".join(current_paras),
                doc_id=doc_id, filename=filename, user_id=user_id,
                language=language, section=section, chunk_num=chunk_num,
                para_start=para_idx - len(current_paras) + 1,
                para_end=para_idx,
            ))

            # Overlap: keep last paragraph(s) worth ~overlap_tokens
            overlap_paras: list[str] = []
            overlap_tok = 0
            for p in reversed(current_paras):
                pt = _estimate_tokens(p)
                if overlap_tok + pt > overlap_tokens:
                    break
                overlap_paras.insert(0, p)
                overlap_tok += pt

            current_paras = overlap_paras
            current_tokens = overlap_tok
            continue

        current_paras.append(para)
        current_tokens += ptok
        para_idx += 1

    # Flush remaining
    if current_paras:
        chunk_num += 1
        chunks.append(_make_chunk(
            text="\n\n".join(current_paras),
            doc_id=doc_id, filename=filename, user_id=user_id,
            language=language, section=section, chunk_num=chunk_num,
            para_start=len(section.paragraphs) - len(current_paras) + 1,
            para_end=len(section.paragraphs),
        ))

    return chunks


def _make_chunk(
    text: str,
    doc_id: str,
    filename: str,
    user_id: str,
    language: str,
    section: Section,
    chunk_num: int,
    para_start: int,
    para_end: int,
) -> dict:
    chunk_id = f"{doc_id}-s{section.number:04d}-p{chunk_num:04d}"
    verse_range = f"{para_start}" if para_start == para_end else f"{para_start}-{para_end}"

    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "purana": doc_id,
            "chapter": section.number,
            "book_section": section.title,
            "verse_range": verse_range,
            "language": language,
            "source_file": filename,
            "source_page": section.start_page,
            "word_count": len(text.split()),
            "doc_id": doc_id,
            "user_id": user_id,
            "workspace": True,
        },
    }
