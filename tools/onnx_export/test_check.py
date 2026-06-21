"""Tests for onnx_export.

Run: venv/bin/python -m tools.onnx_export.test_check   (from purangpt/ repo root)

Uses tiny in-memory fixtures — no model download, no corpus.db required.
Tests: envelope shape, bad-mode error, missing-db error, and the embed
path against a real tiny corpus.db built on the fly with 3 rows.
"""
from __future__ import annotations

import json
import os
import sqlite3
import struct
import tempfile

from tools.onnx_export.check import run, _pack_vec

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}


def _make_tiny_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY, purana TEXT, category TEXT, book_section TEXT,
            chapter INTEGER, verse_range TEXT, language TEXT,
            source_file TEXT, source_page INTEGER, word_count INTEGER, text TEXT
        )
    """)
    con.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        ("g-1", "Gita", "phil", "Ch1", 1, "1", "en", "gita.txt", 1, 5, "dharma kuru kshetra"),
        ("g-2", "Gita", "phil", "Ch1", 1, "2", "en", "gita.txt", 2, 4, "sanjaya uvaca drishtva"),
        ("r-1", "Rama", "iti",  "BK",  1, "1", "sa", "rama.txt", 1, 6, "tapah svadhyaya niratam"),
    ])
    con.commit()
    con.close()


def test_envelope_shape():
    env = run("bad_mode")
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    print("ok: envelope_shape")


def test_bad_mode_error():
    env = run("bad_mode")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "bad_mode"
    print("ok: bad_mode_error")


def test_missing_db_error():
    env = run("embed", db_path="/nonexistent/corpus.db")
    assert env["success"] is False
    assert env["errors"][0]["code"] == "missing_db"
    print("ok: missing_db_error")


def test_embed_tiny_corpus():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "corpus.db")
        _make_tiny_db(db)
        env = run("embed", db_path=db, model_dir=os.path.join(tmp, "model"))
        assert env["success"] is True, env
        d = env["data"]
        assert d["rows_embedded"] == 3, d
        assert d["total_rows"] == 3, d
        assert "backend" in d

        # Verify embeddings table exists and blobs are 384-dim floats
        con = sqlite3.connect(db)
        rows = con.execute("SELECT chunk_id, vec FROM embeddings").fetchall()
        assert len(rows) == 3, f"expected 3 embedding rows, got {len(rows)}"
        for cid, blob in rows:
            floats = struct.unpack(f"{len(blob)//4}f", blob)
            assert len(floats) == 384, f"{cid}: expected 384-dim, got {len(floats)}"
        con.close()
    print("ok: embed_tiny_corpus")


def test_pack_vec():
    v = [0.1, 0.2, 0.3]
    blob = _pack_vec(v)
    assert len(blob) == 12  # 3 * 4 bytes
    unpacked = struct.unpack("3f", blob)
    assert abs(unpacked[0] - 0.1) < 1e-5
    print("ok: pack_vec")


if __name__ == "__main__":
    test_envelope_shape()
    test_bad_mode_error()
    test_missing_db_error()
    test_pack_vec()
    test_embed_tiny_corpus()
    print("\nALL TESTS PASSED")
