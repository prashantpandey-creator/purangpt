"""awakener_chunk — tests-first (Rule 0, precondition A).

Chunks the Awakener (Guruji's biography, prose) into the SAME chunk shape as the
Puranic corpus, with inline `awk_CH.PARA` markers so verify.py can ground cites.
The principle: Guruji's story is a CONTINUATION of the Puranas, not a separate
biography — so it must become corpus, same schema, same graph.

Run: venv/bin/python -m tools.awakener_chunk.test_check   (from purangpt/ repo root)
"""
from __future__ import annotations

import re
import sys

from tools.awakener_chunk.check import (
    chunk_prose,
    _marker_for,
    _is_toc_para,
    run,
)

_AWK_RE = re.compile(r'\bawk_\d+\.\d+\b')

_SAMPLE = """# The Awakener — Biography

> metadata line to skip

Katya Mossin

## Early Years

In the summer of 1980 a boy was born in the foothills. The mountains watched over the family and the village prospered in the shadow of the great peaks that ringed the valley like silent sentinels keeping watch.

His grandfather told stories of the old gods every evening by the fire. The boy listened, and something in him remembered a time before this life, a vastness he could not yet name but which pulled at the edges of his ordinary days.

## The Search

Years later he left home to find a teacher. The road was long and the search tested every conviction he had carried from childhood into the uncertain country of his manhood.
"""


def test_chunk_prose_produces_chunks():
    chunks = chunk_prose(_SAMPLE, target_chars=200)
    assert len(chunks) >= 2, f"expected multiple chunks, got {len(chunks)}"
    for c in chunks:
        assert "id" in c
        assert "purana" in c
        assert "text" in c
        assert "chapter" in c


def test_chunks_carry_awk_markers():
    chunks = chunk_prose(_SAMPLE, target_chars=200)
    for c in chunks:
        markers = _AWK_RE.findall(c["text"])
        assert markers, f"chunk {c['id']} has no awk_ marker in text: {c['text'][:80]}"


def test_marker_matches_verify_regex():
    # verify.py's _MARKER_RE is r'\b[A-Za-z]{1,6}_\d+(?:[.\-]\d+)*\b'
    verify_re = re.compile(r'\b[A-Za-z]{1,6}_\d+(?:[.\-]\d+)*\b')
    m = _marker_for(2, 5)
    assert m == "awk_2.5", f"unexpected marker {m}"
    assert verify_re.search(m), "awk_ marker must match verify.py's _MARKER_RE"


def test_chapter_tracking_from_headings():
    chunks = chunk_prose(_SAMPLE, target_chars=200)
    labels = {c["book_section"] for c in chunks}
    assert any("Early Years" in lbl for lbl in labels), f"labels: {labels}"
    assert any("The Search" in lbl for lbl in labels), f"labels: {labels}"


def test_metadata_and_toc_skipped():
    chunks = chunk_prose(_SAMPLE, target_chars=200)
    full = " ".join(c["text"] for c in chunks)
    assert "metadata line to skip" not in full, "the > blockquote should be skipped"


def test_purana_label_is_awakener():
    chunks = chunk_prose(_SAMPLE, target_chars=200)
    assert all(c["purana"] == "The Awakener" for c in chunks)


def test_ids_unique_and_sequential():
    chunks = chunk_prose(_SAMPLE, target_chars=200)
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"


def test_envelope_shape():
    env = run(write=False)
    assert "success" in env
    assert "data" in env
    assert "metadata" in env
    assert "errors" in env
    if env["success"]:
        d = env["data"]
        assert "n_chunks" in d
        assert "n_chapters" in d
        assert "total_markers" in d


def test_run_handles_missing_source():
    env = run(src_path="/nonexistent/file.md", write=False)
    assert env["success"] is False
    assert env["errors"]
    assert env["errors"][0]["code"] == "missing_source"


def test_is_toc_para_detects_page_listing():
    toc = ("Under the Banyan Tree — 148\n"
           "Sea Creatures — 153\n"
           "The Sadhu on the Beach — 156\n"
           "Winning the Lottery — 161")
    assert _is_toc_para(toc) is True


def test_is_toc_para_passes_narrative():
    prose = ("In the summer of 1997, an unconscious man was found at the gates. "
             "The blazing heat had emptied the road, and there were no witnesses.")
    assert _is_toc_para(prose) is False


def test_toc_stripped_from_chunks():
    sample = """# The Awakener

## Contents

Early Years — 38
Family — 38
The Servant's Wife — 52
City. Books. Time. — 56

## Early Years

In the summer of 1980 a boy was born in the foothills where the mountains watched over the family and the village prospered in the shadow of the great peaks.
"""
    chunks = chunk_prose(sample, target_chars=200)
    full = " ".join(c["text"] for c in chunks)
    assert "Early Years — 38" not in full, "TOC page-listing leaked into chunks"
    assert "Servant's Wife — 52" not in full
    assert "summer of 1980" in full, "real narrative should survive"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
