"""Tests for quantize_embeddings — run as:
    venv/bin/python -m tools.quantize_embeddings.test_check

Builds a tiny real SQLite corpus with float32 embeddings, quantizes it, and
asserts: envelope shape, int8 table exists with correct row count, blobs are
DIM int8 bytes + a scale float, dequantized vectors are close to the originals,
recall@10 vs the float32 ground truth clears a sane bar, and the int8 store is
~4x smaller. Also covers the missing-db and missing-table error paths.
"""
from __future__ import annotations

import os
import sqlite3
import struct
import tempfile

import numpy as np

from tools.quantize_embeddings.check import run, DIM


def _make_corpus(path: str, n: int = 200) -> None:
    """Write a real corpus.db with `embeddings` (float32, L2-normalized)."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE chunks (id TEXT PRIMARY KEY, text TEXT)")
    con.execute("CREATE TABLE embeddings (chunk_id TEXT PRIMARY KEY, vec BLOB NOT NULL)")
    rng = np.random.default_rng(42)
    for i in range(n):
        v = rng.standard_normal(DIM).astype(np.float32)
        v /= (np.linalg.norm(v) + 1e-9)
        cid = f"chunk-{i}"
        con.execute("INSERT INTO chunks VALUES (?,?)", (cid, f"text {i}"))
        con.execute("INSERT INTO embeddings VALUES (?,?)",
                    (cid, struct.pack(f"{DIM}f", *v)))
    con.commit()
    con.close()


def test_envelope_shape():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "corpus.db")
        _make_corpus(db, 50)
        env = run(db)
        assert set(env.keys()) == {"success", "data", "metadata", "errors"}, env
        assert env["success"] is True, env
        assert env["errors"] == []
        for k in ("rows_quantized", "int8_bytes", "float32_bytes", "ratio", "recall_at_10"):
            assert k in env["data"], (k, env["data"])
    print("ok: envelope_shape")


def test_int8_table_written():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "corpus.db")
        _make_corpus(db, 120)
        env = run(db)
        assert env["success"], env
        con = sqlite3.connect(db)
        n_src = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        n_dst = con.execute("SELECT COUNT(*) FROM embeddings_i8").fetchone()[0]
        assert n_src == n_dst == 120, (n_src, n_dst)
        cid, blob, scale = con.execute(
            "SELECT chunk_id, vec, scale FROM embeddings_i8 LIMIT 1").fetchone()
        assert len(blob) == DIM, len(blob)
        assert isinstance(scale, float) and scale > 0, scale
        con.close()
    print("ok: int8_table_written")


def test_dequant_close_and_recall():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "corpus.db")
        _make_corpus(db, 300)
        env = run(db)
        assert env["success"], env
        assert env["data"]["ratio"] < 0.35, env["data"]["ratio"]
        assert env["data"]["recall_at_10"] >= 0.80, env["data"]["recall_at_10"]

        con = sqlite3.connect(db)
        cid = con.execute("SELECT chunk_id FROM embeddings LIMIT 1").fetchone()[0]
        f32 = np.frombuffer(
            con.execute("SELECT vec FROM embeddings WHERE chunk_id=?", (cid,)).fetchone()[0],
            dtype=np.float32)
        q, scale = con.execute(
            "SELECT vec, scale FROM embeddings_i8 WHERE chunk_id=?", (cid,)).fetchone()
        deq = np.frombuffer(q, dtype=np.int8).astype(np.float32) * scale
        cos = float(np.dot(f32, deq) / (np.linalg.norm(f32) * np.linalg.norm(deq)))
        assert cos > 0.99, cos
        con.close()
    print("ok: dequant_close_and_recall")


def test_missing_db_error():
    env = run("/nonexistent/path/corpus.db")
    assert env["success"] is False, env
    assert env["data"] is None
    assert env["errors"][0]["code"] == "missing_db", env["errors"]
    print("ok: missing_db_error")


def test_missing_table_error():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "empty.db")
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE chunks (id TEXT)")
        con.commit(); con.close()
        env = run(db)
        assert env["success"] is False, env
        assert env["errors"][0]["code"] == "missing_embeddings", env["errors"]
    print("ok: missing_table_error")


if __name__ == "__main__":
    test_envelope_shape()
    test_int8_table_written()
    test_dequant_close_and_recall()
    test_missing_db_error()
    test_missing_table_error()
    print("\nALL TESTS PASSED")
