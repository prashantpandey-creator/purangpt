"""embed — bge-m3 offline corpus embedding with checkpoint/resume.

Reads norm_rows.jsonl (output of check.py --step normalize).
Processes in batches of BATCH_SIZE rows. Each completed batch writes:
  {out_dir}/batch_{i:05d}/vectors.npy   float32 [N, 1024]
  {out_dir}/batch_{i:05d}/ids.json      list of N row IDs

Resume: re-running detects completed batch dirs and skips them.
After all batches: merges into {out_dir}/vectors.npy + {out_dir}/ids.json.

Usage:
  venv/bin/python -m tools.reembed.embed norm_rows.jsonl [--out embed_out] [--batch-size 5000]
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

MODEL_ID = "BAAI/bge-m3"
BATCH_SIZE = 5000


def _done_batches(out: Path) -> set[int]:
    done = set()
    for d in out.glob("batch_*"):
        if (d / "vectors.npy").exists() and (d / "ids.json").exists():
            try:
                done.add(int(d.name.split("_")[1]))
            except (IndexError, ValueError):
                pass
    return done


def run(norm_path: str, out_dir: str, batch_size: int = BATCH_SIZE,
        device: str | None = None) -> dict:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    norm_path = Path(norm_path)

    merged_vecs = out / "vectors.npy"
    merged_ids = out / "ids.json"
    if merged_vecs.exists() and merged_ids.exists():
        ids = json.load(open(merged_ids))
        vecs = np.load(merged_vecs)
        print(f"Merged output exists: {len(ids)} rows dim={vecs.shape[1]} — delete to re-run.", flush=True)
        return {"n": len(ids), "dim": int(vecs.shape[1]), "out_dir": str(out), "skipped": True}

    if device is None:
        try:
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        except Exception:
            device = "cpu"

    print(f"Loading {MODEL_ID} on {device}…", flush=True)
    model = SentenceTransformer(MODEL_ID, device=device, trust_remote_code=True)

    rows = []
    with open(norm_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    print(f"Loaded {len(rows)} rows from {norm_path}", flush=True)

    total_batches = (len(rows) + batch_size - 1) // batch_size
    done = _done_batches(out)
    t0 = time.time()

    for bi in range(total_batches):
        if bi in done:
            print(f"  batch {bi+1}/{total_batches}  SKIPPED (cached)", flush=True)
            continue
        batch_rows = rows[bi * batch_size:(bi + 1) * batch_size]
        texts = [r["embed_text"] for r in batch_rows]
        ids_batch = [r["id"] for r in batch_rows]
        bt = time.time()
        vecs = model.encode(texts, normalize_embeddings=True,
                            batch_size=64, show_progress_bar=False)
        bd = out / f"batch_{bi:05d}"
        bd.mkdir(exist_ok=True)
        np.save(bd / "vectors.npy", vecs.astype(np.float32))
        json.dump(ids_batch, open(bd / "ids.json", "w"))
        pct = (bi + 1) / total_batches * 100
        eta = (time.time() - t0) / (bi + 1 - len(done & set(range(bi + 1)))) * (total_batches - bi - 1)
        print(f"  batch {bi+1}/{total_batches}  n={len(batch_rows)}  {time.time()-bt:.0f}s  "
              f"{pct:.0f}%  eta~{eta/60:.0f}min", flush=True)

    print("Merging batches…", flush=True)
    all_ids: list[str] = []
    all_vecs: list = []
    for bi in range(total_batches):
        bd = out / f"batch_{bi:05d}"
        all_ids.extend(json.load(open(bd / "ids.json")))
        all_vecs.append(np.load(bd / "vectors.npy"))
    merged = np.concatenate(all_vecs, axis=0)
    np.save(merged_vecs, merged)
    json.dump(all_ids, open(merged_ids, "w"))
    total_sec = round(time.time() - t0, 1)
    print(f"Done: {len(all_ids)} rows  dim={merged.shape[1]}  {total_sec}s total", flush=True)
    return {"n": len(all_ids), "dim": int(merged.shape[1]), "out_dir": str(out),
            "total_sec": total_sec}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("norm_path")
    ap.add_argument("--out", default="embed_out")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--device", default=None)
    a = ap.parse_args()
    result = run(a.norm_path, a.out, a.batch_size, a.device)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
