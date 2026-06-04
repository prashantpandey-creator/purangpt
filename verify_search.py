#!/usr/bin/env python3
"""
verify_search.py — Post-reindex coherence check for PuranGPT.

Run AFTER `python run.py --index` on a machine with the full venv
(chromadb + sentence-transformers + rank_bm25 installed):

    python verify_search.py

It checks four things:
  1. No placeholder/mock chunks remain in the BM25 chunk_map or in ChromaDB.
  2. The chunk_map has no duplicate ids (double-counting fix held).
  3. Sharma book commentary is actually embedded in the vector store.
  4. Representative queries surface Sharma commentary, AND a control Purana
     query is unaffected by the weighting (no Sharma bleed-in).

Exit code is non-zero if any hard check fails, so it can gate a deploy.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

INDEX_DIR = Path(os.getenv("INDEX_DIR", "data/indexes"))
DB_DIR    = Path(os.getenv("DB_DIR", "data/chroma_db"))

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "\033[92m✓\033[0m" if ok else "\033[91m✗\033[0m"
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(label)


# ── 1 & 2: chunk_map integrity (no model needed) ────────────────────────────
print("\n[1] BM25 chunk_map integrity")
chunk_map = json.loads((INDEX_DIR / "chunk_map.json").read_text(encoding="utf-8"))
ids = [c.get("id", "") for c in chunk_map]
mock = [i for i in ids if "mock" in i.lower()]
dupes = len(ids) - len(set(ids))
check("no mock chunks in chunk_map", not mock, f"{len(mock)} found")
check("no duplicate ids in chunk_map", dupes == 0, f"{dupes} duplicates")
print(f"      chunk_map size: {len(ids):,} (expected ~115,694)")

# ── 3: ChromaDB contents ────────────────────────────────────────────────────
print("\n[3] ChromaDB vector store")
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(path=str(DB_DIR),
                                   settings=Settings(anonymized_telemetry=False))
col = client.get_collection("purana_verses")
sharma_cats = {"yogic-commentary", "yogic-discourse"}
limit = 10000
offset = 0
chroma_ids = set()
sharma_book_count = 0

while True:
    batch = col.get(limit=limit, offset=offset, include=["metadatas"])
    if not batch["ids"]:
        break
    chroma_ids.update(batch["ids"])
    for m in batch["metadatas"]:
        if m and (m.get("category") or "").lower() in sharma_cats:
            sharma_book_count += 1
    offset += limit

chroma_mock = [i for i in chroma_ids if "mock" in i.lower()]
check("no mock vectors in ChromaDB", not chroma_mock, f"{len(chroma_mock)} found")
print(f"      vector count: {col.count():,}")

check("Sharma book commentary embedded", sharma_book_count >= 80,
      f"{sharma_book_count} commentary chunks in vector store")

# ── 4: live retrieval behaviour ─────────────────────────────────────────────
print("\n[4] Retrieval behaviour")
from indexer.search import HybridSearcher

searcher = HybridSearcher(db_dir=DB_DIR, index_dir=INDEX_DIR).initialize()


def top_sources(query, **kw):
    res = searcher.hybrid_search(query, top_k=8, **kw)
    return res


def has_sharma_commentary(results) -> bool:
    return any((r.chunk.get("category") or "").lower() in sharma_cats
               for r in results)


for q in ["how does one become immortal through yoga",
          "what is ojas and amrita",
          "khechari mudra and the nectar at the palate",
          "Time as Shiva, Mahakala consciousness"]:
    res = top_sources(q)
    found = has_sharma_commentary(res)
    check(f"Sharma commentary surfaces for: {q!r}", found,
          f"top purana = {res[0].purana if res else 'none'}")

# Control: a pure Purana narrative query should NOT be hijacked by Sharma weighting.
control = "how many sons did king dasharatha have in the ramayana"
res_on  = top_sources(control, sharma_weighting=True)
res_off = top_sources(control, sharma_weighting=False)
control_clean = not has_sharma_commentary(res_on)
check("control Purana query free of Sharma bleed-in", control_clean,
      f"top = {res_on[0].purana if res_on else 'none'}")
# Weighting should only re-rank, never invent results for unrelated queries.
ids_on  = {r.id for r in res_on}
ids_off = {r.id for r in res_off}
check("weighting only re-ranks (same candidate set on control)",
      ids_on == ids_off,
      f"{len(ids_on ^ ids_off)} differing ids")

# ── Verdict ─────────────────────────────────────────────────────────────────
print()
if failures:
    print(f"\033[91mFAILED {len(failures)} check(s):\033[0m " + "; ".join(failures))
    sys.exit(1)
print("\033[92mAll coherence checks passed.\033[0m")
