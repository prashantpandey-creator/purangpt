"""awakener_chunk — chunk Guruji's biography (The Awakener) as Puranic corpus.

The principle (daddy, 2026-06-24): Guruji's story is the CONTINUATION of the
Puranas, not a separate biography. So it must become corpus — same chunk shape as
`all_chunks.jsonl`, with inline `awk_CH.PARA` markers so verify.py can ground the
citations the decoder emits, exactly as `mbh_`/`bhp_` do for the Puranas.

Marker scheme: prose has no canonical verse numbers, so we key markers to
chapter-index + paragraph-sequence-within-chapter (`awk_<chapter>.<para>`). The
marker maps to a REAL paragraph in the source — verify.py can confirm it exists —
without fabricating verse numbers that don't.

Input contract:  run(src_path="", out_path="", target_chars=1500, write=True) -> envelope
Output contract (envelope.data on success):
  { n_chunks, n_chapters, total_markers, out_path }
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List


_BASE = os.path.join(os.path.dirname(__file__), "..", "..")
_SRC = os.path.join(_BASE, "tools", "read_pass", "translations", "the_awakener_EN.md")
_OUT = os.path.join(_BASE, "data", "chunks", "awakener_chunks.jsonl")

_PURANA_LABEL = "The Awakener"
_CATEGORY = "biography"


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data,
            "metadata": metadata, "errors": errors}


def _marker_for(chapter_idx: int, para_seq: int) -> str:
    """awk_<chapter>.<para> — matches verify.py's _MARKER_RE."""
    return f"awk_{chapter_idx}.{para_seq}"


_PAGE_REF_RE = re.compile(r'—\s*\d+\s*$')


def _is_toc_para(p: str) -> bool:
    """A table-of-contents block: a paragraph where most lines end in a page
    reference (`Title — 148`). These are navigation cruft, not narrative — they
    would poison the decode with fake 'entities' pulled from chapter titles.
    """
    lines = [l for l in p.split("\n") if l.strip()]
    if not lines:
        return False
    pagey = sum(1 for l in lines if _PAGE_REF_RE.search(l.strip()))
    return pagey >= max(2, len(lines) * 0.5)


def chunk_prose(text: str, target_chars: int = 1500) -> List[Dict[str, Any]]:
    """Split prose into corpus-shaped chunks with inline awk_ markers.

    - Tracks the nearest preceding `##`/`###` heading as the chapter.
    - Skips `>` blockquotes, bare URLs, and the leading title/metadata.
    - Each paragraph gets an `awk_<ch>.<para>` marker prepended; paragraphs are
      packed into chunks up to ~target_chars (never splitting a paragraph).
    """
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]

    chapter_idx = 0
    chapter_label = "Front Matter"
    para_seq = 0  # paragraph sequence within the current chapter

    chunks: List[Dict[str, Any]] = []
    global_seq = 0

    buf: List[str] = []
    buf_chars = 0
    buf_chapter_idx = 0
    buf_chapter_label = chapter_label
    buf_first_marker = ""

    def flush():
        nonlocal buf, buf_chars, global_seq, buf_first_marker
        if not buf:
            return
        global_seq += 1
        chunk_text = "\n\n".join(buf)
        chunks.append({
            "id": f"awakener-{buf_chapter_idx:03d}-{global_seq}",
            "purana": _PURANA_LABEL,
            "category": _CATEGORY,
            "book_section": buf_chapter_label,
            "chapter": buf_chapter_idx,
            "verse_range": buf_first_marker.replace("awk_", "") if buf_first_marker else "",
            "text": chunk_text,
            "language": "english",
            "source_file": "the_awakener_EN.md",
            "source_page": 0,
            "word_count": len(chunk_text.split()),
        })
        buf = []
        buf_chars = 0
        buf_first_marker = ""

    for p in paras:
        # Heading? -> advance chapter, flush current buffer
        if p.startswith("#"):
            heading = p.lstrip("#").strip()
            # the H1 title is front matter, not a chapter
            if p.startswith("# ") and chapter_idx == 0:
                continue
            flush()
            chapter_idx += 1
            chapter_label = heading
            para_seq = 0
            continue

        # Skip blockquotes, bare URLs, very short noise lines
        if p.startswith(">") or p.startswith("http") or p.startswith("---"):
            continue
        if len(p) < 40:
            continue
        # Skip table-of-contents blocks (page-number listings)
        if _is_toc_para(p):
            continue

        para_seq += 1
        marker = _marker_for(chapter_idx, para_seq)
        marked_para = f"{marker} {p}"

        # starting a fresh buffer? capture chapter + first marker
        if not buf:
            buf_chapter_idx = chapter_idx
            buf_chapter_label = chapter_label
            buf_first_marker = marker

        buf.append(marked_para)
        buf_chars += len(marked_para)

        if buf_chars >= target_chars:
            flush()

    flush()
    return chunks


def run(src_path: str = "", out_path: str = "",
        target_chars: int = 1500, write: bool = True) -> Dict[str, Any]:
    src_path = src_path or os.path.abspath(_SRC)
    out_path = out_path or os.path.abspath(_OUT)
    metadata = {"src_path": src_path, "out_path": out_path,
                "target_chars": target_chars, "write": write}

    if not os.path.isfile(src_path):
        return _envelope(False, None, metadata,
                         [{"code": "missing_source",
                           "message": f"source not found: {src_path}"}])

    with open(src_path) as f:
        text = f.read()

    chunks = chunk_prose(text, target_chars=target_chars)
    if not chunks:
        return _envelope(False, None, metadata,
                         [{"code": "no_chunks",
                           "message": "no content chunks produced from source"}])

    if write:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

    chapters = {c["chapter"] for c in chunks}
    marker_re = re.compile(r'\bawk_\d+\.\d+\b')
    total_markers = sum(len(marker_re.findall(c["text"])) for c in chunks)

    data = {
        "n_chunks": len(chunks),
        "n_chapters": len(chapters),
        "total_markers": total_markers,
        "out_path": out_path if write else None,
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    write = "--dry-run" not in argv
    target = 1500
    if "--target" in argv:
        target = int(argv[argv.index("--target") + 1])

    env = run(target_chars=target, write=write)

    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"=== AWAKENER CHUNKED ===")
        print(f"Chunks: {d['n_chunks']:,}")
        print(f"Chapters: {d['n_chapters']}")
        print(f"Markers: {d['total_markers']:,}")
        if d.get("out_path"):
            print(f"Written to: {d['out_path']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
