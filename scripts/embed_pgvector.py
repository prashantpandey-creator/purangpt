"""
PuranGPT — pgvector embedding indexer (multi-worker)
Generates 384-dim e5-small embeddings for all purana_verses rows with NULL embedding.
Uses multiprocessing to fully saturate CPU cores.

Usage (inside backend container):
    python /app/scripts/embed_pgvector.py              # auto workers = nproc - 1
    python /app/scripts/embed_pgvector.py --workers 4
    python /app/scripts/embed_pgvector.py --dry-run
    python /app/scripts/embed_pgvector.py --limit 1000  # test
"""

import argparse
import asyncio
import logging
import multiprocessing
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(processName)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

EMBED_MODEL = "intfloat/multilingual-e5-small"
BATCH_SIZE = 64


def worker(worker_id: int, ids: list[str], db_url: str) -> tuple[int, int]:
    """Encode a partition of IDs and write embeddings to pgvector. Returns (done, errors)."""
    import asyncpg
    from sentence_transformers import SentenceTransformer

    log.info("Worker %d: %d rows to embed", worker_id, len(ids))
    model = SentenceTransformer(EMBED_MODEL)

    done = 0
    errors = 0

    async def _run():
        nonlocal done, errors

        async def make_pool():
            # Recycle idle connections so a server-side drop doesn't hand us a dead
            # one; small pool keeps total connections low under multi-worker load.
            return await asyncpg.create_pool(
                db_url, min_size=1, max_size=2,
                max_inactive_connection_lifetime=30,
                command_timeout=60,
            )

        pool = await make_pool()

        async def reset_pool():
            nonlocal pool
            try:
                await pool.close()
            except Exception:
                pass
            # brief backoff, then a fresh pool — recovers from transient drops
            await asyncio.sleep(2)
            pool = await make_pool()

        i = 0
        while i < len(ids):
            batch_ids = ids[i : i + BATCH_SIZE]

            # Whole batch is wrapped: a dropped connection during fetch OR update
            # must NOT escape the worker (that would kill the entire mp.starmap).
            # On a connection error we rebuild the pool and RETRY the same batch
            # once; any other error skips the batch (rows stay NULL → backfilled).
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT id, content FROM purana_verses WHERE id = ANY($1)",
                        batch_ids,
                    )

                if not rows:
                    i += BATCH_SIZE
                    continue

                texts = [f"passage: {r['content'][:800]}" for r in rows]
                rids = [r["id"] for r in rows]

                vecs = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False)
                updates = [
                    (f"[{','.join(map(str, v.tolist()))}]", rid)
                    for v, rid in zip(vecs, rids)
                ]

                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.executemany(
                            "UPDATE purana_verses SET embedding = $1::vector WHERE id = $2",
                            updates,
                        )

                done += len(rids)
                i += BATCH_SIZE
                if done % 512 == 0 or i >= len(ids):
                    log.info("Worker %d: %d / %d  (errors: %d)", worker_id, done, len(ids), errors)

            except (asyncpg.exceptions.ConnectionDoesNotExistError,
                    asyncpg.exceptions.InterfaceError,
                    ConnectionError, OSError) as e:
                # Transient connection drop — rebuild pool and retry this batch once.
                log.warning("Worker %d conn drop, rebuilding pool: %s", worker_id, e)
                await reset_pool()
                # do NOT advance i — retry the same batch
                continue
            except Exception as e:
                log.error("Worker %d batch error (skipping): %s", worker_id, e)
                errors += len(batch_ids)
                i += BATCH_SIZE
                continue

        await pool.close()
        return done, errors

    return asyncio.run(_run())


async def main(n_workers: int, dry_run: bool, limit_rows: int | None) -> None:
    import asyncpg

    db_url = os.environ.get("VECTOR_DB_URL")
    if not db_url:
        raise SystemExit("VECTOR_DB_URL not set")

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

    total = await pool.fetchval("SELECT COUNT(*) FROM purana_verses WHERE embedding IS NULL")
    total_all = await pool.fetchval("SELECT COUNT(*) FROM purana_verses")
    log.info("Total verses: %d  |  Missing embeddings: %d", total_all, total)

    if total == 0:
        log.info("All embeddings already present.")
        await pool.close()
        return

    if dry_run:
        log.info("--dry-run: would embed %d rows across %d workers. Exiting.", total, n_workers)
        await pool.close()
        return

    # Fetch all IDs that need embedding
    to_embed = limit_rows if limit_rows else total
    rows = await pool.fetch(
        "SELECT id FROM purana_verses WHERE embedding IS NULL ORDER BY id LIMIT $1",
        to_embed,
    )
    await pool.close()

    all_ids = [r["id"] for r in rows]
    log.info("Fetched %d IDs to embed across %d workers", len(all_ids), n_workers)

    # Partition IDs across workers
    chunk_size = (len(all_ids) + n_workers - 1) // n_workers
    partitions = [all_ids[i : i + chunk_size] for i in range(0, len(all_ids), chunk_size)]

    t0 = time.time()
    with multiprocessing.Pool(processes=n_workers) as mp_pool:
        results = mp_pool.starmap(
            worker,
            [(i, part, db_url) for i, part in enumerate(partitions)],
        )

    total_done = sum(r[0] for r in results)
    total_errors = sum(r[1] for r in results)
    elapsed = time.time() - t0
    rate = total_done / elapsed if elapsed > 0 else 0
    log.info(
        "Embedding complete. Done: %d  Errors: %d  Time: %.0fs  Rate: %.1f/s",
        total_done, total_errors, elapsed, rate,
    )

    # Refresh FTS for any NULL rows
    log.info("Refreshing FTS for NULL fts rows...")
    pool2 = await asyncpg.create_pool(db_url, min_size=1, max_size=2)
    null_fts = await pool2.fetchval("SELECT COUNT(*) FROM purana_verses WHERE fts IS NULL")
    if null_fts > 0:
        await pool2.execute(
            "UPDATE purana_verses SET fts = to_tsvector('simple', content) WHERE fts IS NULL"
        )
        log.info("Updated %d FTS rows.", null_fts)
    else:
        log.info("FTS already complete.")

    final_count = await pool2.fetchval("SELECT COUNT(*) FROM purana_verses WHERE embedding IS NOT NULL")
    log.info("Final embedded count: %d / %d", final_count, total_all)
    await pool2.close()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)

    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() - 1))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    log.info("Starting with %d workers", args.workers)
    asyncio.run(main(args.workers, args.dry_run, args.limit))
