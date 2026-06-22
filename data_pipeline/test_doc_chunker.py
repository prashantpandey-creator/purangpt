"""Tests for GenericDocChunker — run with: venv/bin/python -m data_pipeline.test_doc_chunker"""

from data_pipeline.doc_chunker import (
    chunk_document, detect_sections, _estimate_tokens, _detect_language,
)

DOC_ID = "test-doc-001"
FILENAME = "test.pdf"
USER_ID = "user-abc"


def _make_pages(texts: dict[int, str]) -> dict[str, dict]:
    return {str(k): {"text": v} for k, v in texts.items()}


# ── Section detection ─────────────────────────────────────────────────────

def test_markdown_headings():
    pages = _make_pages({
        1: "# Introduction\n\nThis is the intro paragraph with enough text to pass the filter.\n\n"
           "# Methods\n\nWe used several approaches to test this hypothesis thoroughly.\n\n"
           "# Results\n\nThe results show significant improvement across all metrics tested."
    })
    sections = detect_sections(pages)
    assert len(sections) == 3, f"Expected 3 sections, got {len(sections)}"
    assert sections[0].title == "Introduction"
    assert sections[1].title == "Methods"
    assert sections[2].title == "Results"


def test_numbered_headings():
    pages = _make_pages({
        1: "1. Background Information\n\nSome background text that explains the context well enough.\n\n"
           "2. Core Methodology\n\nThe methodology section with detailed explanation of the approach.\n\n"
           "3. Final Conclusions\n\nConclusions drawn from the data analysis and experiments."
    })
    sections = detect_sections(pages)
    assert len(sections) >= 2, f"Expected >=2 sections, got {len(sections)}"


def test_no_headings_fallback():
    pages = _make_pages({
        1: "Just a plain text document with no headings at all but enough text to matter.\n\n"
           "Another paragraph here that continues the discussion in detail.\n\n"
           "And yet another paragraph to ensure we have content to work with."
    })
    sections = detect_sections(pages)
    assert len(sections) == 1
    assert sections[0].title == "Full Document"


def test_empty_pages():
    pages = _make_pages({1: "", 2: "   "})
    sections = detect_sections(pages)
    assert len(sections) == 0


# ── Chunk generation ──────────────────────────────────────────────────────

def test_basic_chunking():
    pages = _make_pages({
        1: "# Chapter One\n\n" + "This is a test paragraph with some content. " * 20 + "\n\n"
           + "Second paragraph with different content here. " * 20 + "\n\n"
           + "Third paragraph to ensure multiple chunks. " * 20 + "\n\n"
           "# Chapter Two\n\n" + "Fourth paragraph in chapter two now. " * 20
    })
    chunks = chunk_document(pages, DOC_ID, FILENAME, USER_ID)
    assert len(chunks) > 0, "Should produce at least one chunk"

    for c in chunks:
        assert c["id"].startswith(DOC_ID), f"Chunk ID should start with doc_id: {c['id']}"
        assert c["text"], "Chunk text should not be empty"
        assert c["metadata"]["purana"] == DOC_ID
        assert c["metadata"]["workspace"] is True
        assert c["metadata"]["user_id"] == USER_ID
        assert c["metadata"]["doc_id"] == DOC_ID
        assert isinstance(c["metadata"]["chapter"], int)
        assert c["metadata"]["word_count"] > 0


def test_chunk_ids_deterministic():
    pages = _make_pages({
        1: "# Intro\n\nSome text here that forms the first paragraph of the document.\n\n"
           "More text to ensure the paragraph is long enough to be included."
    })
    chunks_a = chunk_document(pages, DOC_ID, FILENAME, USER_ID)
    chunks_b = chunk_document(pages, DOC_ID, FILENAME, USER_ID)
    assert [c["id"] for c in chunks_a] == [c["id"] for c in chunks_b]


def test_chunk_id_format():
    pages = _make_pages({
        1: "# Section\n\nA paragraph with enough content to be a real chunk of text."
    })
    chunks = chunk_document(pages, DOC_ID, FILENAME, USER_ID)
    assert len(chunks) > 0
    # Format: {doc_id}-s{section:04d}-p{chunk:04d}
    cid = chunks[0]["id"]
    assert "-s" in cid and "-p" in cid, f"Bad chunk ID format: {cid}"


def test_chunk_size_bounds():
    long_para = "Word " * 2000  # ~2000 words ≈ 2600 tokens
    pages = _make_pages({
        1: f"# Big Section\n\n{long_para}"
    })
    chunks = chunk_document(pages, DOC_ID, FILENAME, USER_ID, target_tokens=600, max_tokens=1000)
    assert len(chunks) > 1, "Long paragraph should be split into multiple chunks"
    for c in chunks:
        tok = _estimate_tokens(c["text"])
        assert tok <= 1100, f"Chunk too large: {tok} tokens"


def test_section_numbers_sequential():
    pages = _make_pages({
        1: "# Alpha\n\nContent for alpha section with enough words.\n\n"
           "# Beta\n\nContent for beta section with enough words.\n\n"
           "# Gamma\n\nContent for gamma section with enough words."
    })
    chunks = chunk_document(pages, DOC_ID, FILENAME, USER_ID)
    section_nums = sorted(set(c["metadata"]["chapter"] for c in chunks))
    assert section_nums == list(range(1, len(section_nums) + 1)), \
        f"Section numbers should be sequential starting from 1: {section_nums}"


# ── Language detection ────────────────────────────────────────────────────

def test_english_detection():
    assert _detect_language("This is a plain English sentence.") == "english"


def test_hindi_detection():
    assert _detect_language("यह एक हिंदी वाक्य है जो काफी लंबा है") in ("hindi", "sanskrit")


# ── Token estimation ──────────────────────────────────────────────────────

def test_token_estimate():
    text = "hello world foo bar"
    est = _estimate_tokens(text)
    assert 4 <= est <= 8, f"4 words should estimate ~5 tokens, got {est}"


# ── Multi-page documents ─────────────────────────────────────────────────

def test_multi_page():
    pages = _make_pages({
        1: "# Introduction\n\nFirst page content with a decent amount of text here.",
        2: "# Literature Review\n\nSecond page content that discusses prior work in detail.",
        3: "# Methodology\n\nThird page describes the methods used in this study.",
    })
    chunks = chunk_document(pages, DOC_ID, FILENAME, USER_ID)
    assert len(chunks) >= 3, "Should have at least one chunk per section"
    titles = [c["metadata"]["book_section"] for c in chunks]
    assert "Introduction" in titles
    assert "Literature Review" in titles
    assert "Methodology" in titles


# ── String page format ────────────────────────────────────────────────────

def test_string_page_format():
    pages = {"1": "# Test\n\nSome content in a simple string format without dict wrapper."}
    chunks = chunk_document(pages, DOC_ID, FILENAME, USER_ID)
    assert len(chunks) > 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    if passed < len(tests):
        exit(1)
