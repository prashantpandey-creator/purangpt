"""
PuranGPT — Hybrid Search Engine
Combines semantic (dense vector) search via Postgres with
FTS keyword search, fused natively in Postgres via RRF.

This gives us the best of both worlds:
- Semantic: "stories of devotion" finds passages about bhakti even without the exact word
- BM25: "Narada" finds exact name matches that embeddings might rank lower
"""

from __future__ import annotations
import json
import logging
import math
import os
import hashlib
import asyncpg
from typing import Any, Optional

try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None
except ImportError:
    redis_client = None

logger = logging.getLogger(__name__)

CACHE_TTL = 86400 * 7  # Cache search results for 7 days


# ── Data Structures ────────────────────────────────────────────────────────

class SearchResult:
    """A single search result with full metadata."""

    def __init__(self, chunk: dict[str, Any], score: float, rank: int = 0):
        self.chunk     = chunk
        self.score     = score
        self.rank      = rank
        # Convenience accessors
        self.id        = chunk.get("id", "")
        self.purana    = chunk.get("purana", "Unknown")
        self.chapter   = chunk.get("chapter")
        self.verse_range = chunk.get("verse_range", "")
        self.text      = chunk.get("text", "")
        self.language  = chunk.get("language", "hindi")
        self.reference = self._build_reference()

    def _build_reference(self) -> str:
        """Build a human-readable reference string."""
        parts = [self.purana]
        if section := self.chunk.get("book_section"):
            parts.append(section)
        if self.chapter:
            parts.append(f"Ch. {self.chapter}")
        if self.verse_range:
            parts.append(f"Verse {self.verse_range}")
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":          self.id,
            "purana":      self.purana,
            "reference":   self.reference,
            "chapter":     self.chapter,
            "verse_range": self.verse_range,
            "text":        self.text,
            "language":    self.language,
            "score":       round(self.score, 4),
        }

    def __repr__(self) -> str:
        return f"SearchResult({self.reference!r}, score={self.score:.3f})"


# ── HybridSearcher ─────────────────────────────────────────────────────────

class HybridSearcher:
    """
    Hybrid retrieval engine utilizing Postgres pgvector and Full Text Search (FTS).
    """
    # Process-wide shared embedding model. Loaded ONCE in the gunicorn master
    # (pre-fork) so every worker inherits the same ~1.2GB weights copy-on-write
    # instead of each loading its own copy. See gunicorn.conf.py on_starting hook.
    _shared_model = None

    def __init__(self) -> None:
        self._embed_model = None
        self._initialized = False
        self._db_url = os.environ.get("VECTOR_DB_URL", "postgresql://postgres:postgres@localhost:5432/purangpt")
        self._pool = None

    @classmethod
    def preload_model(cls):
        """Load the embedding model into the class once. Safe to call in the
        master process before gunicorn forks workers."""
        if cls._shared_model is None:
            from sentence_transformers import SentenceTransformer
            import logging
            logger = logging.getLogger("purangpt.search")
            cls._shared_model = SentenceTransformer("intfloat/multilingual-e5-small")
            logger.info("Embedding model preloaded ✓ (shared across workers)")
        return cls._shared_model

    async def initialize(self) -> "HybridSearcher":
        """Per-worker init: create this event loop's asyncpg pool and bind the
        shared embedding model. The pool CANNOT be shared across forked workers
        (it's bound to a specific event loop), so each worker makes its own —
        but the model is the shared class-level instance, not a fresh load."""
        logger.info("Initializing HybridSearcher via Postgres…")

        # asyncpg pool is per-worker (event-loop-bound) — keep it small since we
        # now run only 2 workers: 2 workers × 5 = 10 connections max to pgvector.
        self._pool = await asyncpg.create_pool(self._db_url, min_size=1, max_size=5)

        # Reuse the master-preloaded model if present; otherwise load on demand
        # (e.g. dev / `run.py` path that doesn't go through the gunicorn hook).
        self._embed_model = self._shared_model or self.preload_model()

        self._initialized = True
        logger.info("HybridSearcher initialized ✓")
        return self

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._pool is not None

    # ── Hybrid Search (RRF Fusion) ─────────────────────────────────────

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        semantic_weight: float = 0.5,
        mmr_lambda: float = 0.7,
        sharma_weighting: bool = True,
        embed_phrase: str | None = None,
        fts_phrase: str | None = None,
    ) -> list[SearchResult]:
        """
        Executes the hybrid_search RPC on Postgres, which performs pgvector distance
        and FTS websearch natively, fusing them with RRF.

        Args:
            query:        Original user query (used for FTS if fts_phrase not given).
            embed_phrase: Enriched phrase for embedding, e.g. from SanskritQueryProcessor.
                          Falls back to "query: {query}" if None.
            fts_phrase:   Multi-term OR phrase for Postgres FTS, e.g. "maheśvara | shiva | rudra".
                          Falls back to raw query if None.
        """
        if not self.is_ready:
            return []

        # 1. Build cache key
        cache_params = json.dumps({
            "query": query,
            "top_k": top_k,
            "filters": filters or {},
            "sharma_weighting": sharma_weighting,
            "embed_phrase": embed_phrase,
            "fts_phrase": fts_phrase,
        }, sort_keys=True)
        cache_hash = hashlib.sha256(cache_params.encode()).hexdigest()
        cache_key = f"hybrid_search:{cache_hash}"

        # 2. Check Redis cache
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    logger.debug("Cache hit for hybrid_search: %r", query)
                    # Reconstruct SearchResult objects (which take the chunk and score)
                    return [SearchResult(chunk=r, score=r["score"], rank=r.get("rank", i)) for i, r in enumerate(data)]
            except Exception as e:
                logger.warning("Redis cache read failed for hybrid_search %r: %s", query, e)

        try:
            # 3. Generate query embedding — use enriched phrase if provided
            import asyncio
            loop = asyncio.get_running_loop()
            phrase_to_embed = embed_phrase if embed_phrase else f"query: {query}"
            query_emb = await loop.run_in_executor(None, self._embed_model.encode, phrase_to_embed)
            if hasattr(query_emb, "tolist"):
                query_emb = query_emb.tolist()
            emb_str = "[" + ",".join(map(str, query_emb)) + "]"

            # 2. Build filter JSON
            pg_filter = {}
            if filters:
                for k, v in filters.items():
                    if isinstance(v, dict) and "$eq" in v:
                        pg_filter[k] = v["$eq"]
                    else:
                        pg_filter[k] = v

            filter_json = json.dumps(pg_filter)

            # 3. Execute Postgres hybrid_search function
            # Use fts_phrase for FTS if given (OR-joined synonyms), else raw query.
            fts_query = fts_phrase if fts_phrase else query
            fetch_k = top_k * 4
            async with self._pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT id, content, metadata, similarity
                    FROM hybrid_search($1, $2::vector, $3, $4::jsonb)
                ''', fts_query, emb_str, fetch_k, filter_json)

            if not rows:
                return []

            # Create SearchResult objects
            results = []
            for rank, row in enumerate(rows):
                meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                score = float(row['similarity'])
                chunk = {**meta, "id": row['id'], "text": row['content']}
                results.append(SearchResult(chunk=chunk, score=score, rank=rank))
                
            # Apply source weighting
            COMMENTARY_CATEGORIES = {"yogic-commentary", "yogic-discourse"}
            if sharma_weighting:
                for res in results:
                    cat = (res.chunk.get("category") or "").lower()
                    if cat in COMMENTARY_CATEGORIES:
                        res.score *= 1.6
                    elif res.id.startswith("darshan-") or res.purana == "Shailendra Sharma Darshans":
                        res.score *= 0.6
                        
            # Sort by updated scores
            results.sort(key=lambda x: x.score, reverse=True)

            # Apply MMR
            final_results = []
            selected_sources = []
            candidates = results.copy()

            while len(final_results) < top_k and candidates:
                if not final_results:
                    best = candidates.pop(0)
                    final_results.append(SearchResult(chunk=best.chunk, score=best.score, rank=0))
                    selected_sources.append(best.purana)
                    continue

                best_mmr = -math.inf
                best_idx = 0
                source_counts = {}
                for src in selected_sources:
                    source_counts[src] = source_counts.get(src, 0) + 1

                max_rrf = candidates[0].score if candidates else 1.0
                
                for i, cand in enumerate(candidates):
                    overlap = source_counts.get(cand.purana, 0)
                    diversity_penalty = overlap * 0.15 * max_rrf
                    mmr_score = mmr_lambda * cand.score - (1.0 - mmr_lambda) * diversity_penalty
                    if mmr_score > best_mmr:
                        best_mmr = mmr_score
                        best_idx = i

                chosen = candidates.pop(best_idx)
                final_results.append(SearchResult(chunk=chosen.chunk, score=chosen.score, rank=len(final_results)))
                selected_sources.append(chosen.purana)

            # Save to Redis
            if redis_client:
                try:
                    # We store the raw dictionaries
                    cache_data = json.dumps([res.to_dict() for res in final_results])
                    await redis_client.setex(cache_key, CACHE_TTL, cache_data)
                except Exception as e:
                    logger.warning("Redis cache write failed for hybrid_search %r: %s", query, e)

            return final_results

        except Exception as e:
            logger.error("Hybrid Postgres search error: %s", e, exc_info=True)
            return []

    # ── Find All Instances ─────────────────────────────────────────────

    async def find_all_instances(
        self,
        query: str,
        min_score: float = 0.3,
        category: str | None = None,
        max_results: int = 200,
        embed_phrase: str | None = None,
        fts_phrase: str | None = None,
    ) -> list[SearchResult]:
        filters = {"category": category} if category else None
        results = await self.hybrid_search(
            query, top_k=max_results, filters=filters, 
            semantic_weight=0.5, mmr_lambda=1.0, sharma_weighting=False,
            embed_phrase=embed_phrase, fts_phrase=fts_phrase
        )
        return [r for r in results if r.score >= min_score]

    # ── Purana Statistics ──────────────────────────────────────────────

    def get_purana_stats(self) -> list[dict[str, Any]]:
        """Return stats for all indexed Puranas (name + chunk count)."""
        counts: dict[str, int] = {}
        for chunk in self._chunk_map:
            purana = chunk.get("purana", "Unknown")
            counts[purana] = counts.get(purana, 0) + 1

        return [
            {"name": purana, "chunk_count": count}
            for purana, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]
