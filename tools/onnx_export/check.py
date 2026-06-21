"""onnx_export — Export multilingual-e5-small to quantized ONNX + embed all corpus chunks.

Two sub-commands (--mode):
  model   Export the SentenceTransformer model to ONNX INT8 (data/offline/model/)
  embed   Generate 384-dim embeddings for every row in corpus.db and store
          them in a new `embeddings` table with an ANN index via sqlite-vss
          (falls back to raw BLOB column if sqlite-vss unavailable, enabling
          cosine search via a pure-SQL dot-product scan for smaller corpora).

Input contract:
  run(mode, db_path, model_dir) -> envelope
Output contract (envelope.data on success):
  mode=model: { "model_dir": str, "onnx_size_mb": float, "dim": int }
  mode=embed: { "rows_embedded": int, "db_path": str, "backend": str }
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
from typing import Any, Dict, List

DB_DEFAULT    = os.path.join(os.path.dirname(__file__), "..", "..", "data", "offline", "corpus.db")
MODEL_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "offline", "model")
MODEL_ID      = "intfloat/multilingual-e5-small"
BATCH_SIZE    = 256
DIM           = 384


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ── model export ─────────────────────────────────────────────────────────────

def _export_model(model_dir: str) -> Dict[str, Any]:
    model_dir = os.path.abspath(model_dir)
    os.makedirs(model_dir, exist_ok=True)

    onnx_path = os.path.join(model_dir, "model_int8.onnx")
    if os.path.exists(onnx_path):
        size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        return _envelope(True, {"model_dir": model_dir, "onnx_size_mb": round(size_mb, 1), "dim": DIM},
                         {"skipped": True}, [])

    try:
        from optimum.onnxruntime import ORTModelForFeatureExtraction
        from optimum.onnxruntime.configuration import AutoQuantizationConfig
        from optimum.onnxruntime import ORTQuantizer
        from transformers import AutoTokenizer
    except ImportError as e:
        return _envelope(False, None, {}, [{"code": "missing_dep", "message": str(e)}])

    print(f"Exporting {MODEL_ID} → ONNX ...", file=sys.stderr)
    tmp_dir = os.path.join(model_dir, "_fp32")
    model = ORTModelForFeatureExtraction.from_pretrained(MODEL_ID, export=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model.save_pretrained(tmp_dir)
    tokenizer.save_pretrained(tmp_dir)

    print("Quantizing to INT8 ...", file=sys.stderr)
    qconfig = AutoQuantizationConfig.arm64(is_static=False, per_channel=False)
    quantizer = ORTQuantizer.from_pretrained(tmp_dir)
    quantizer.quantize(save_dir=model_dir, quantization_config=qconfig)

    # Rename to predictable filename
    candidates = [f for f in os.listdir(model_dir) if f.endswith(".onnx")]
    if candidates:
        src = os.path.join(model_dir, candidates[0])
        if src != onnx_path:
            os.rename(src, onnx_path)

    size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
    return _envelope(True, {"model_dir": model_dir, "onnx_size_mb": round(size_mb, 1), "dim": DIM},
                     {}, [])


# ── embed all chunks ──────────────────────────────────────────────────────────

def _pack_vec(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _embed_corpus(db_path: str, model_dir: str) -> Dict[str, Any]:
    import sqlite3

    db_path   = os.path.abspath(db_path)
    model_dir = os.path.abspath(model_dir)

    if not os.path.exists(db_path):
        return _envelope(False, None, {}, [{"code": "missing_db",
                                            "message": f"corpus.db not found: {db_path}"}])

    # Load the ONNX model for inference
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer
    except ImportError as e:
        return _envelope(False, None, {}, [{"code": "missing_dep", "message": str(e)}])

    onnx_path = os.path.join(model_dir, "model_int8.onnx")
    if not os.path.exists(onnx_path):
        # Fall back to full sentence-transformers if ONNX not exported yet
        try:
            from sentence_transformers import SentenceTransformer
            st_model = SentenceTransformer(MODEL_ID)
            use_onnx = False
        except ImportError as e:
            return _envelope(False, None, {}, [{"code": "missing_dep", "message": str(e)}])
    else:
        tokenizer = AutoTokenizer.from_pretrained(
            model_dir if os.path.exists(os.path.join(model_dir, "tokenizer_config.json"))
            else MODEL_ID
        )
        sess = ort.InferenceSession(onnx_path,
                                    providers=["CPUExecutionProvider"])
        use_onnx = True

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")

    # Check if sqlite-vss is available
    try:
        con.enable_load_extension(True)
        con.load_extension("vss0")
        has_vss = True
    except Exception:
        has_vss = False

    # Create embeddings table (skip rows already embedded)
    con.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            chunk_id TEXT PRIMARY KEY,
            vec      BLOB NOT NULL
        )
    """)
    con.commit()

    already = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    total   = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Embedding {total - already} chunks (already done: {already}) ...", file=sys.stderr)

    rows_done = 0
    cursor = con.execute(
        "SELECT id, text FROM chunks WHERE id NOT IN (SELECT chunk_id FROM embeddings)"
    )

    def embed_batch(texts: List[str]) -> List[List[float]]:
        if use_onnx:
            import numpy as np
            enc = tokenizer(texts, padding=True, truncation=True,
                            max_length=512, return_tensors="np")
            out = sess.run(None, dict(enc))
            # mean-pool over token dim
            hidden = out[0]                         # (B, seq, dim)
            mask   = enc["attention_mask"][..., None]
            vecs   = (hidden * mask).sum(1) / mask.sum(1)
            # L2 normalise
            norms  = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
            return (vecs / norms).tolist()
        else:
            import numpy as np
            vecs = st_model.encode(texts, normalize_embeddings=True,
                                   show_progress_bar=False)
            return vecs.tolist()

    batch_ids: List[str] = []
    batch_texts: List[str] = []
    t0 = time.time()

    for chunk_id, text in cursor:
        batch_ids.append(chunk_id)
        batch_texts.append(f"passage: {text}")  # e5-style prefix

        if len(batch_ids) >= BATCH_SIZE:
            vecs = embed_batch(batch_texts)
            con.executemany(
                "INSERT OR REPLACE INTO embeddings(chunk_id, vec) VALUES (?, ?)",
                [(cid, _pack_vec(v)) for cid, v in zip(batch_ids, vecs)]
            )
            con.commit()
            rows_done += len(batch_ids)
            batch_ids, batch_texts = [], []

            if rows_done % 10000 == 0:
                elapsed = time.time() - t0
                rate    = rows_done / elapsed
                eta     = (total - already - rows_done) / rate
                print(f"  {rows_done:,}/{total - already:,}  {rate:.0f} rows/s  ETA {eta/60:.1f}m",
                      file=sys.stderr)

    if batch_ids:
        vecs = embed_batch(batch_texts)
        con.executemany(
            "INSERT OR REPLACE INTO embeddings(chunk_id, vec) VALUES (?, ?)",
            [(cid, _pack_vec(v)) for cid, v in zip(batch_ids, vecs)]
        )
        con.commit()
        rows_done += len(batch_ids)

    final_count = con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    con.close()

    return _envelope(True, {
        "rows_embedded": rows_done,
        "total_rows":    final_count,
        "db_path":       db_path,
        "backend":       "onnx_int8" if use_onnx else "sentence_transformers",
    }, {"model_dir": model_dir}, [])


# ── public entry point ────────────────────────────────────────────────────────

def run(mode: str = "model",
        db_path: str = DB_DEFAULT,
        model_dir: str = MODEL_DEFAULT) -> Dict[str, Any]:
    if mode == "model":
        return _export_model(model_dir)
    elif mode == "embed":
        return _embed_corpus(db_path, model_dir)
    else:
        return _envelope(False, None, {"mode": mode},
                         [{"code": "bad_mode", "message": f"unknown mode '{mode}'; use 'model' or 'embed'"}])


def main(argv: List[str]) -> int:
    as_json   = "--json" in argv
    mode      = argv[argv.index("--mode") + 1] if "--mode" in argv else "model"
    db_path   = argv[argv.index("--db") + 1]   if "--db"   in argv else DB_DEFAULT
    model_dir = argv[argv.index("--model-dir") + 1] if "--model-dir" in argv else MODEL_DEFAULT

    env = run(mode, db_path, model_dir)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}", file=sys.stderr)
            return 2
        d = env["data"]
        if mode == "model":
            print(f"OK: model exported → {d['model_dir']}  ({d['onnx_size_mb']} MB, {d['dim']}-dim)")
        else:
            print(f"OK: {d['rows_embedded']:,} rows embedded → {d['db_path']}  backend={d['backend']}")

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
