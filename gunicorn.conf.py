"""
Gunicorn configuration for PuranGPT backend.

Key design decision: this is an I/O-bound async app — nearly all request time is
spent awaiting the upstream LLM API stream. One asyncio event loop handles high
concurrency on its own, so we do NOT scale workers with cores. 2 workers gives
redundancy (one serves while the other restarts on deploy) at ~1/3 the memory of
the old 6-worker setup.

The embedding model (~1.2GB) is loaded ONCE here in the master via on_starting,
then shared with every worker copy-on-write through preload fork. Previously it
loaded per-worker inside the FastAPI lifespan (post-fork), costing 6× the RAM and
causing OOM under any concurrent batch work.
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("WEB_CONCURRENCY", "4"))
timeout = 180
graceful_timeout = 30
worker_tmp_dir = "/dev/shm"

# preload_app forks workers from a fully-imported master, enabling copy-on-write
# sharing of anything loaded in on_starting (the embedding model).
preload_app = True

# Recycle workers periodically to bound any slow memory growth (jitter avoids
# both workers recycling at once).
max_requests = 2000
max_requests_jitter = 200


def on_starting(server):
    """Runs once in the master before workers fork. Load the heavy embedding
    model here so all workers inherit it copy-on-write instead of each loading
    its own copy."""
    try:
        from indexer.search import HybridSearcher
        HybridSearcher.preload_model()
        server.log.info("Embedding model preloaded in master — shared across workers.")
    except Exception as e:
        # Non-fatal: workers will lazily load the model in lifespan if this fails.
        server.log.warning("Master model preload failed (%s); workers will load lazily.", e)
