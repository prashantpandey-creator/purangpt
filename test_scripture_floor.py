"""Smoke test for the scripture floor in indexer/search.py.

Regression guard for the bug where English/conceptual/multilingual queries embedded
near the English darshan transcripts and returned 100% Shailendra Sharma darshan,
never surfacing scripture — so the Guru could quote one book but not synthesize
across the texts ("answer from all angles").

Root cause fixed: the floor's firing condition counted scripture across the whole
fetch_k (= top_k*4) candidate pool, where deep-tail scripture that can never survive
MMR wrongly reported the floor as already met. It now measures the top_k output
window, retrieves every non-Guruji scripture category, and deterministically
guarantees the quota post-MMR.

Requires a live pgvector connection (VECTOR_DB_URL). Run directly:
    venv/bin/python test_scripture_floor.py     # local (localhost:5433)
or inside the backend container:
    docker exec -e PYTHONPATH=/app -w /app purangpt_backend python test_scripture_floor.py

Exit 0 = all assertions pass; non-zero = regression.
"""
import asyncio
import sys

from indexer.search import HybridSearcher
from backend.main import is_sharma_text

# (query, corpus_type, min_scripture, min_texts) — guruji control must stay darshan-only.
CASES = [
    ("the nature of dharma and duty", None, 4, 4),
    ("what happens to the soul after death", None, 4, 4),
    ("धर्म और कर्तव्य का स्वरूप", None, 4, 2),          # Hindi
    ("природа дхармы и долга", None, 4, 2),             # Russian
    ("Krishna Arjuna Kurukshetra battle", None, 4, 4),
    ("Gorakhnath nath yoga lineage", None, 4, 4),
    ("the nature of dharma and duty", "guruji", 0, 0),  # control: floor must NOT fire
]


async def main() -> int:
    s = await HybridSearcher().initialize()
    if not s.is_ready:
        print("SKIP: searcher not ready (no VECTOR_DB_URL)")
        return 0
    failures = 0
    for query, ct, min_scrip, min_texts in CASES:
        rows = await s.hybrid_search(query=query, top_k=8, corpus_type=ct)
        darshan = sum(1 for r in rows if is_sharma_text(r))
        scrip = len(rows) - darshan
        texts = {(r.purana or "?") for r in rows if not is_sharma_text(r)}
        if ct == "guruji":
            ok = scrip == 0  # floor must be skipped → no scripture injected
        else:
            ok = scrip >= min_scrip and len(texts) >= min_texts
        flag = "OK  " if ok else "FAIL"
        print(f"  [{flag}] {query[:38]:38s} ct={str(ct):7s} -> {darshan}D {scrip}S, {len(texts)} texts")
        if not ok:
            failures += 1
    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {len(CASES) - failures}/{len(CASES)} cases")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
