"""Tests for sqlite_export.

Run: venv/bin/python -m tools.sqlite_export.test_check   (from purangpt/ repo root)

Uses a small in-memory fixture (5 rows) to verify envelope shape, DB schema,
FTS5 search, and the missing-input error path — without touching the 183MB
all_chunks.jsonl or writing to data/offline/.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

from tools.sqlite_export.check import run

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}
DATA_KEYS = {"output_path", "row_count", "fts_row_count", "db_size_mb", "texts"}

FIXTURE_ROWS = [
    {"id": "gita-1-1", "purana": "Bhagavad Gita", "category": "philosophy",
     "book_section": "Chapter 1", "chapter": 1, "verse_range": "1",
     "language": "sanskrit", "source_file": "gita.txt", "source_page": 1,
     "word_count": 10, "text": "dhritarashtra uvaca dharma ksetre kuru ksetre"},
    {"id": "gita-1-2", "purana": "Bhagavad Gita", "category": "philosophy",
     "book_section": "Chapter 1", "chapter": 1, "verse_range": "2",
     "language": "sanskrit", "source_file": "gita.txt", "source_page": 2,
     "word_count": 8, "text": "sanjaya uvaca drishtva tu pandava anikam"},
    {"id": "agni-1-1", "purana": "Agni Purana", "category": "mixed",
     "book_section": "Chapter 1", "chapter": 1, "verse_range": "1",
     "language": "sanskrit", "source_file": "agni.txt", "source_page": 1,
     "word_count": 12, "text": "agni puranam atha agni puranam anukramanika"},
    {"id": "rama-1-1", "purana": "Ramayana", "category": "itihasa",
     "book_section": "Bala Kanda", "chapter": 1, "verse_range": "1",
     "language": "sanskrit", "source_file": "rama.txt", "source_page": 1,
     "word_count": 9, "text": "tapah svadhyaya niratam tapasvim vag vidham"},
    {"id": "rama-1-2", "purana": "Ramayana", "category": "itihasa",
     "book_section": "Bala Kanda", "chapter": 1, "verse_range": "2",
     "language": "english", "source_file": "rama_en.txt", "source_page": 1,
     "word_count": 11, "text": "who is that virtuous one among men always truthful"},
]


def _write_fixture(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in FIXTURE_ROWS:
            f.write(json.dumps(row) + "\n")


def test_envelope_shape():
    with tempfile.TemporaryDirectory() as tmp:
        chunks = os.path.join(tmp, "chunks.jsonl")
        output = os.path.join(tmp, "corpus.db")
        _write_fixture(chunks)
        env = run(chunks, output)
        assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
        assert env["success"] is True, env
        assert env["errors"] == []
        assert set(env["data"].keys()) == DATA_KEYS, env["data"].keys()
    print("ok: envelope_shape")


def test_row_counts():
    with tempfile.TemporaryDirectory() as tmp:
        chunks = os.path.join(tmp, "chunks.jsonl")
        output = os.path.join(tmp, "corpus.db")
        _write_fixture(chunks)
        env = run(chunks, output)
        assert env["data"]["row_count"] == 5, env["data"]
        assert env["data"]["fts_row_count"] == 5, env["data"]
    print("ok: row_counts")


def test_db_schema_and_content():
    with tempfile.TemporaryDirectory() as tmp:
        chunks = os.path.join(tmp, "chunks.jsonl")
        output = os.path.join(tmp, "corpus.db")
        _write_fixture(chunks)
        run(chunks, output)
        con = sqlite3.connect(output)
        row = con.execute(
            "SELECT id, purana, text FROM chunks WHERE id = 'gita-1-1'"
        ).fetchone()
        assert row is not None, "gita-1-1 not found"
        assert row[1] == "Bhagavad Gita", row
        assert "dharma" in row[2], row
        con.close()
    print("ok: db_schema_and_content")


def test_fts5_search():
    with tempfile.TemporaryDirectory() as tmp:
        chunks = os.path.join(tmp, "chunks.jsonl")
        output = os.path.join(tmp, "corpus.db")
        _write_fixture(chunks)
        run(chunks, output)
        con = sqlite3.connect(output)
        # FTS search for "dharma" — should match gita-1-1
        hits = con.execute(
            """SELECT c.id FROM chunks c
               JOIN chunks_fts f ON c.rowid = f.rowid
               WHERE chunks_fts MATCH 'dharma'"""
        ).fetchall()
        ids = [h[0] for h in hits]
        assert "gita-1-1" in ids, f"expected gita-1-1 in FTS results, got: {ids}"
        # "virtuous" should match rama-1-2 (English)
        hits2 = con.execute(
            """SELECT c.id FROM chunks c
               JOIN chunks_fts f ON c.rowid = f.rowid
               WHERE chunks_fts MATCH 'virtuous'"""
        ).fetchall()
        ids2 = [h[0] for h in hits2]
        assert "rama-1-2" in ids2, f"expected rama-1-2, got: {ids2}"
        con.close()
    print("ok: fts5_search")


def test_texts_list():
    with tempfile.TemporaryDirectory() as tmp:
        chunks = os.path.join(tmp, "chunks.jsonl")
        output = os.path.join(tmp, "corpus.db")
        _write_fixture(chunks)
        env = run(chunks, output)
        texts = env["data"]["texts"]
        assert "Bhagavad Gita" in texts, texts
        assert "Agni Purana" in texts, texts
        assert "Ramayana" in texts, texts
    print("ok: texts_list")


def test_missing_input_error():
    with tempfile.TemporaryDirectory() as tmp:
        env = run("/nonexistent/path/chunks.jsonl", os.path.join(tmp, "out.db"))
        assert env["success"] is False, env
        assert env["data"] is None
        assert env["errors"][0]["code"] == "missing_input", env["errors"]
    print("ok: missing_input_error")


if __name__ == "__main__":
    test_envelope_shape()
    test_row_counts()
    test_db_schema_and_content()
    test_fts5_search()
    test_texts_list()
    test_missing_input_error()
    print("\nALL TESTS PASSED")
