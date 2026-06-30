"""import_vectors — push bge-m3 embeddings into the prod pgvector DB.

Reads {embed_out}/vectors.npy + {embed_out}/ids.json.
Steps:
  1. ALTER TABLE purana_verses ADD COLUMN IF NOT EXISTS embedding_bge vector(1024)
  2. Bulk UPDATE in batches of 1000 rows via psycopg2 execute_batch
  3. CREATE INDEX CONCURRENTLY ON purana_verses USING hnsw(embedding_bge vector_cosine_ops)

Requires SSH tunnel to be running on localhost:5433:
  ssh -i ~/.ssh/purangpt_hetzner -L 5433:localhost:5433 root@204.168.176.229 -N &

Usage:
  venv/bin/python -m tools.reembed.import_vectors embed_out/ [--dry-run] [--db-url ...]
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

DEFAULT_DB = "postgresql://postgres:postgres@localhost:5433/purangpt"
BATCH = 1000


def run(embed_dir: str, db_url: str = DEFAULT_DB, dry_run: bool = False) -> dict:
    import numpy as np
    import psycopg2
    import psycopg2.extras

    embed_dir = Path(embed_dir)
    ids_path = embed_dir / "ids.json"
    vecs_path = embed_dir / "vectors.npy"

    if not ids_path.exists() or not vecs_path.exists():
        return {"success": False, "error": f"Missing {ids_path} or {vecs_path}"}

    ids: list[str] = json.load(open(ids_path))
    vecs = np.load(vecs_path)
    if len(ids) != len(vecs):
        return {"success": False, "error": f"id/vec count mismatch: {len(ids)} vs {len(vecs)}"}

    dim = int(vecs.shape[1])
    print(f"Loaded {len(ids)} vectors  dim={dim}", flush=True)

    if dry_run:
        print("DRY RUN — no DB writes.", flush=True)
        return {"success": True, "n": len(ids), "dim": dim, "dry_run": True}

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute(f"ALTER TABLE purana_verses ADD COLUMN IF NOT EXISTS embedding_bge vector({dim})")
    conn.commit()
    print(f"Column embedding_bge vector({dim}) ensured.", flush=True)

    updated = 0
    t0 = time.time()
    for i in range(0, len(ids), BATCH):
        batch_ids = ids[i:i + BATCH]
        batch_vecs = vecs[i:i + BATCH]
        data = [(vec.tolist(), bid) for bid, vec in zip(batch_ids, batch_vecs)]
        psycopg2.extras.execute_batch(
            cur,
            "UPDATE purana_verses SET embedding_bge = %s::vector WHERE id = %s",
            data,
            page_size=BATCH,
        )
        conn.commit()
        updated += len(batch_ids)
        pct = updated / len(ids) * 100
        elapsed = time.time() - t0
        eta = elapsed / updated * (len(ids) - updated) if updated else 0
        print(f"  {updated}/{len(ids)} ({pct:.0f}%)  {elapsed:.0f}s  eta~{eta/60:.0f}min", flush=True)

    print("Creating HNSW index (concurrent — may take 5-15 min)…", flush=True)
    conn.autocommit = True
    cur.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pv_embedding_bge "
        "ON purana_verses USING hnsw(embedding_bge vector_cosine_ops) "
        "WITH (m=16, ef_construction=64)"
    )
    conn.close()
    total_sec = round(time.time() - t0, 1)
    print(f"Done. {updated} rows updated  HNSW built  {total_sec}s total", flush=True)
    return {"success": True, "n": updated, "dim": dim, "total_sec": total_sec}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("embed_dir")
    ap.add_argument("--db-url", default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    result = run(a.embed_dir, a.db_url, a.dry_run)
    print(json.dumps(result, default=str))
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
