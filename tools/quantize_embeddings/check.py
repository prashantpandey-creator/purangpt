"""quantize_embeddings — shrink a float32 `embeddings` table to int8 in-place.

Reads the float32 `embeddings(chunk_id, vec)` table in corpus.db and writes an
`embeddings_i8(chunk_id, vec, scale)` table where each vector is stored as DIM
symmetric-int8 bytes plus a per-vector float scale (`scale = max|v| / 127`).
Dequant is `int8 * scale`. On L2-normalized vectors this is ~4x smaller with
>99% per-vector cosine and ~95% recall@10 vs the float32 ground truth — the
standard SQ8 trick (FAISS/pgvector). The frontend reads `embeddings_i8` and
dequantizes in JS before the cosine scan.

Input contract:  run(db_path) -> dict (envelope)
Output contract (envelope.data on success):
  { rows_quantized:int, int8_bytes:int, float32_bytes:int, ratio:float,
    recall_at_10:float }
On failure: success=False, data=None, errors=[{code,message}]
  codes: missing_db, missing_embeddings
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
from typing import Any, Dict, List

DIM = 384
BATCH = 10000
RECALL_QUERIES = 50  # sample size for the recall@10 self-check


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(db_path: str = "") -> Dict[str, Any]:
    import numpy as np

    db_path = os.path.abspath(db_path)
    metadata = {"db_path": db_path, "dim": DIM}

    if not os.path.exists(db_path):
        return _envelope(False, None, metadata,
                         [{"code": "missing_db", "message": f"db not found: {db_path}"}])

    con = sqlite3.connect(db_path)
    has_emb = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
    ).fetchone()
    if not has_emb:
        con.close()
        return _envelope(False, None, metadata,
                         [{"code": "missing_embeddings",
                           "message": "no `embeddings` table in db"}])

    rows = con.execute("SELECT chunk_id, vec FROM embeddings").fetchall()
    if not rows:
        con.close()
        return _envelope(False, None, metadata,
                         [{"code": "missing_embeddings",
                           "message": "`embeddings` table is empty"}])

    con.execute("DROP TABLE IF EXISTS embeddings_i8")
    con.execute("""
        CREATE TABLE embeddings_i8 (
            chunk_id TEXT PRIMARY KEY,
            vec      BLOB NOT NULL,
            scale    REAL NOT NULL
        )
    """)

    # Quantize in batches. Keep dequantized vectors for the recall self-check.
    cids: List[str] = []
    f32_mat: List["np.ndarray"] = []
    i8_mat: List["np.ndarray"] = []
    int8_bytes = 0
    float32_bytes = 0
    batch: List[tuple] = []

    for cid, blob in rows:
        v = np.frombuffer(blob, dtype=np.float32)
        float32_bytes += len(blob)
        scale = float(np.max(np.abs(v))) / 127.0 or 1e-9
        q = np.round(v / scale).astype(np.int8)
        qb = q.tobytes()
        int8_bytes += len(qb) + 8  # +8 for the REAL scale column
        batch.append((cid, qb, scale))
        cids.append(cid)
        f32_mat.append(v)
        i8_mat.append(q.astype(np.float32) * scale)
        if len(batch) >= BATCH:
            con.executemany("INSERT INTO embeddings_i8 VALUES (?,?,?)", batch)
            batch = []
    if batch:
        con.executemany("INSERT INTO embeddings_i8 VALUES (?,?,?)", batch)
    con.commit()
    con.close()

    # Recall@10: for a random sample of vectors used as queries, do the top-10
    # neighbours from the int8 matrix match the float32 ground truth?
    f32 = np.stack(f32_mat)
    i8 = np.stack(i8_mat)
    names = np.array(cids)
    n = len(cids)
    k = min(10, n)
    rnd = random.Random(0)
    sample_idx = rnd.sample(range(n), min(RECALL_QUERIES, n))
    recalls = []
    for qi in sample_idx:
        qv = f32[qi]  # query in float32 (what the live ONNX model produces)
        top_true = set(names[np.argsort(-(f32 @ qv))[:k]])
        top_i8 = set(names[np.argsort(-(i8 @ qv))[:k]])
        recalls.append(len(top_true & top_i8) / k)
    recall_at_10 = float(sum(recalls) / len(recalls)) if recalls else 1.0

    data = {
        "rows_quantized": n,
        "int8_bytes": int8_bytes,
        "float32_bytes": float32_bytes,
        "ratio": round(int8_bytes / float32_bytes, 4) if float32_bytes else 0.0,
        "recall_at_10": round(recall_at_10, 4),
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else \
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "offline", "corpus.db")

    env = run(db_path)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"OK: {d['rows_quantized']:,} vecs  "
              f"{d['float32_bytes']/1024/1024:.0f}MiB -> {d['int8_bytes']/1024/1024:.0f}MiB "
              f"({d['ratio']*100:.0f}%)  recall@10={d['recall_at_10']*100:.1f}%")

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
