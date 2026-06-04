"""
PuranGPT — Hybrid Search Engine
Combines semantic (dense vector) search via ChromaDB with
BM25 keyword search, fused using Reciprocal Rank Fusion (RRF).

This gives us the best of both worlds:
- Semantic: "stories of devotion" finds passages about bhakti even without the exact word
- BM25: "Narada" finds exact name matches that embeddings might rank lower
"""

from __future__ import annotations

import json
import logging
import math
import pickle
from pathlib import Path
from typing import Any, Optional

import chromadb
from backend.pinecone_client import semantic_search as pinecone_search
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
import os

logger = logging.getLogger(__name__)


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
    Hybrid retrieval engine: dense semantic search (ChromaDB) + sparse
    keyword search (BM25), fused via Reciprocal Rank Fusion.

    Initialize once at startup (expensive: loads ~2 GB embedding model + indexes),
    then reuse across all queries.

    Parameters
    ----------
    db_dir : str | Path
        Directory containing the ChromaDB persistent store.
    index_dir : str | Path
        Directory containing bm25_index.pkl and chunk_map.json.
    collection_name : str
        Name of the ChromaDB collection.
    rrf_k : int
        RRF constant. Higher k gives smoother rank fusion.
        Typical values: 60 (standard), 10 (emphasize top ranks).
    """

    def __init__(
        self,
        db_dir:          str | Path = "data/chroma_db",
        index_dir:       str | Path = "data/indexes",
        collection_name: str        = "purana_verses",
        rrf_k:           int        = 60,
    ) -> None:
        self.db_dir          = Path(db_dir)
        self.index_dir       = Path(index_dir)
        self.collection_name = collection_name
        self.rrf_k           = rrf_k

        self._chroma_client: Optional[chromadb.ClientAPI]  = None
        self._collection:    Optional[chromadb.Collection] = None
        self._bm25:          Optional[BM25Okapi]           = None
        self._chunk_map:     list[dict[str, Any]]          = []  # index → chunk dict
        self._embed_model:   Optional[SentenceTransformer] = None
        self._initialized    = False

    def initialize(self) -> "HybridSearcher":
        """Load ChromaDB, BM25 index, and chunk map. Call once at startup."""
        logger.info("Initializing HybridSearcher…")

        # ── ChromaDB ───────────────────────────────────────────────────
        self._chroma_client = chromadb.PersistentClient(
            path=str(self.db_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            self._collection = self._chroma_client.get_collection(self.collection_name)
            logger.info(
                "Loaded ChromaDB collection '%s' with %d documents",
                self.collection_name,
                self._collection.count(),
            )
        except Exception as e:
            logger.warning(
                "ChromaDB collection '%s' not found: %s. Semantic search will be unavailable.",
                self.collection_name, e,
            )

        # ── BM25 + Chunk Map ──────────────────────────────────────────
        bm25_path     = self.index_dir / "bm25_index.pkl"
        chunk_map_path = self.index_dir / "chunk_map.json"

        if bm25_path.exists():
            with open(bm25_path, "rb") as f:
                self._bm25 = pickle.load(f)
            logger.info("Loaded BM25 index (%d documents)", getattr(self._bm25, 'corpus_size', 0))
        else:
            logger.warning("BM25 index not found at %s. Keyword search unavailable.", bm25_path)

        if chunk_map_path.exists():
            with open(chunk_map_path, "r", encoding="utf-8") as f:
                self._chunk_map = json.load(f)
            logger.info("Loaded chunk map: %d entries", len(self._chunk_map))
        else:
            logger.warning("Chunk map not found at %s.", chunk_map_path)
            
        # ── Embed Model ───────────────────────────────────────────────
        embed_model_name = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
        logger.info("Loading embedding model: %s", embed_model_name)
        self._embed_model = SentenceTransformer(embed_model_name)

        self._initialized = True
        logger.info("HybridSearcher initialized ✓")
        return self

    @property
    def is_ready(self) -> bool:
        return self._initialized and (
            self._collection is not None or self._bm25 is not None
        )

    @property
    def total_documents(self) -> int:
        if self._collection:
            return self._collection.count()
        return len(self._chunk_map)

    # ── Semantic Search ────────────────────────────────────────────────

    def semantic_search(
        self,
        query:   str,
        top_k:   int                   = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Dense vector similarity search via ChromaDB.

        Parameters
        ----------
        query   : Natural language query (will be embedded by ChromaDB's model)
        top_k   : Maximum number of results to return
        filters : ChromaDB where-clause, e.g. {"purana": "Bhagavata Purana"}
        """
        if not self._collection or not self._embed_model:
            logger.warning("ChromaDB collection or embed model not loaded; skipping semantic search")
            return []

        try:
            # Generate query embeddings in the correct vector space with required prefix
            query_emb = self._embed_model.encode([f"query: {query}"], normalize_embeddings=True).tolist()
            
            kwargs: dict[str, Any] = {
                "query_embeddings": query_emb,
                "n_results":        min(top_k, self._collection.count() or 1),
                "include":          ["documents", "metadatas", "distances"],
            }
            if filters:
                # Build ChromaDB where clause
                if len(filters) == 1:
                    key, val = next(iter(filters.items()))
                    kwargs["where"] = {key: {"$eq": val}}
                else:
                    kwargs["where"] = {"$and": [{k: {"$eq": v}} for k, v in filters.items()]}

            results = self._collection.query(**kwargs)

            search_results: list[SearchResult] = []
            docs      = results["documents"][0]
            metas     = results["metadatas"][0]
            distances = results["distances"][0]

            for rank, (doc, meta, dist) in enumerate(zip(docs, metas, distances)):
                # ChromaDB returns L2 distance; convert to similarity score
                score = 1.0 / (1.0 + dist)
                chunk = {**meta, "text": doc}
                search_results.append(SearchResult(chunk=chunk, score=score, rank=rank))

            return search_results

        except Exception as e:
            logger.error("Semantic search error: %s", e, exc_info=True)
            return []

    # ── Keyword Search (BM25) ─────────────────────────────────────────

    def keyword_search(
        self,
        query: str,
        top_k: int = 20,
    ) -> list[SearchResult]:
        """
        BM25 Okapi sparse keyword retrieval.
        Excellent for finding exact Sanskrit deity names, specific terms.
        """
        if not self._bm25 or not self._chunk_map:
            return []

        # Tokenize query (simple whitespace + devanagari-aware split)
        tokens = self._tokenize(query)
        if not tokens:
            return []

        try:
            scores = self._bm25.get_scores(tokens)
            # Get top-k indices by score
            top_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )[:top_k]

            results: list[SearchResult] = []
            for rank, idx in enumerate(top_indices):
                if scores[idx] <= 0:
                    break  # No more matching documents
                if idx < len(self._chunk_map):
                    chunk = self._chunk_map[idx]
                    # Normalize BM25 score to 0-1 range (approximate)
                    max_score = scores[top_indices[0]] if scores[top_indices[0]] > 0 else 1.0
                    norm_score = scores[idx] / max_score
                    results.append(SearchResult(chunk=chunk, score=norm_score, rank=rank))

            return results

        except Exception as e:
            logger.error("BM25 search error: %s", e, exc_info=True)
            return []

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for BM25 (handles both Devanagari and Latin)."""
        import re
        # Split on whitespace and punctuation, keeping Devanagari characters
        tokens = re.findall(r'[\u0900-\u097F]+|[a-zA-Z]+', text.lower())
        return [t for t in tokens if len(t) > 1]

    # \u2500\u2500 Source weighting \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    # Shailendra Sharma's corpus has two very different tiers:
    #   \u2022 Curated book commentary (Shiv Sutra, Ojas & Amrita, Yoga & Alchemy,
    #     Khechari, Gorakh Bodh \u2026): a few dozen dense, high-signal chunks tagged
    #     category == "yogic-commentary".
    #   \u2022 ~3,100 conversational darshan Q&A transcripts (id prefix "darshan-").
    # Without weighting the transcripts swamp the commentary by sheer volume.
    # These multipliers are applied to fused RRF scores, so they only re-rank
    # results that already matched the query \u2014 they never inject Sharma content
    # into an unrelated query.
    # Curated Sharma book tier is tagged with one of these categories (and only
    # Sharma's book files use them). `category` is one of the few fields preserved
    # in both the BM25 chunk_map and the Chroma metadata, so it's the reliable
    # signal at retrieval time (`bias`/`author` are not stored there).
    COMMENTARY_CATEGORIES = {"yogic-commentary", "yogic-discourse"}
    COMMENTARY_BOOST = 1.4   # curated book commentary / discourse
    DARSHAN_DAMPEN   = 0.85  # bulk conversational transcripts

    def _source_weight(self, chunk: dict[str, Any]) -> float:
        """Relevance multiplier based on the source tier of a chunk."""
        if (chunk.get("category") or "").lower() in self.COMMENTARY_CATEGORIES:
            return self.COMMENTARY_BOOST
        cid = chunk.get("id", "")
        if cid.startswith("darshan-") or chunk.get("purana") == "Shailendra Sharma Darshans":
            return self.DARSHAN_DAMPEN
        return 1.0

    # ── Hybrid Search (RRF Fusion) ─────────────────────────────────────

    def hybrid_search(
        self,
        query:            str,
        top_k:            int                   = 10,
        filters:          dict[str, Any] | None = None,
        semantic_weight:  float                 = 0.6,
        mmr_lambda:       float                 = 0.7,
        sharma_weighting: bool                  = True,
    ) -> list[SearchResult]:
        """
        Hybrid search combining semantic + BM25 via Reciprocal Rank Fusion,
        followed by Maximal Marginal Relevance (MMR) to ensure cross-textual diversity.

        RRF score for document d = Σ 1/(k + rank_i(d))
        MMR selects results balancing relevance vs source diversity so answers
        draw from multiple Puranas rather than the same text repeatedly.

        Parameters
        ----------
        query           : Natural language or Sanskrit/Hindi query
        top_k           : Number of final results to return
        filters         : Optional Purana/chapter filter (applied to semantic search)
        semantic_weight : Weight for semantic vs keyword (0.6 = 60% semantic)
        mmr_lambda      : MMR trade-off: 1.0 = pure relevance, 0.0 = pure diversity
                          0.7 keeps relevance dominant while ensuring cross-text coverage
        """
        fetch_k = top_k * 4  # Fetch more from each source before fusion + MMR

        # Run both searches
        semantic_results = self.semantic_search(query, top_k=fetch_k, filters=filters)
        keyword_results  = self.keyword_search(query,  top_k=fetch_k)

        # Build RRF score map: doc_id → cumulative RRF score
        rrf_scores: dict[str, float] = {}
        chunk_registry: dict[str, dict[str, Any]] = {}  # doc_id → chunk data

        # Apply RRF from semantic results
        for rank, result in enumerate(semantic_results):
            doc_id = result.id or f"sem_{rank}"
            rrf_scores[doc_id]    = rrf_scores.get(doc_id, 0.0) + semantic_weight / (self.rrf_k + rank + 1)
            chunk_registry[doc_id] = result.chunk

        # Apply RRF from keyword results
        kw_weight = 1.0 - semantic_weight
        for rank, result in enumerate(keyword_results):
            doc_id = result.id or f"kw_{rank}"
            rrf_scores[doc_id]     = rrf_scores.get(doc_id, 0.0) + kw_weight / (self.rrf_k + rank + 1)
            if doc_id not in chunk_registry:
                chunk_registry[doc_id] = result.chunk

        # Source-tier weighting: lift curated Sharma commentary and damp bulk
        # transcripts so high-signal commentary isn't buried by transcript volume.
        # Applied to fused scores only, so it re-ranks matches without pulling in
        # off-topic content.
        if sharma_weighting:
            for doc_id, chunk in chunk_registry.items():
                w = self._source_weight(chunk)
                if w != 1.0:
                    rrf_scores[doc_id] *= w

        # Sort by RRF score (descending) — full candidate pool for MMR
        sorted_ids = sorted(rrf_scores.keys(), key=lambda d: rrf_scores[d], reverse=True)
        candidates = [
            SearchResult(chunk=chunk_registry[doc_id], score=rrf_scores[doc_id], rank=i)
            for i, doc_id in enumerate(sorted_ids)
        ]

        # ── MMR diversity reranking ──────────────────────────────────────
        # Penalty strategy: source-text diversity (purana + book_section).
        # A document from the same purana as an already-selected result incurs
        # a similarity penalty. This prevents the top-10 being all Bhagavata Purana.
        final_results: list[SearchResult] = []
        selected_sources: list[str] = []   # e.g. ["Bhagavata Purana", "Shiva Purana"]

        while len(final_results) < top_k and candidates:
            if not final_results:
                # Always pick highest-relevance result first
                best = candidates.pop(0)
                final_results.append(SearchResult(chunk=best.chunk, score=best.score, rank=0))
                selected_sources.append(best.purana)
                continue

            # MMR score = λ * relevance - (1-λ) * source_overlap_penalty
            best_mmr   = -math.inf
            best_idx   = 0
            source_counts: dict[str, int] = {}
            for src in selected_sources:
                source_counts[src] = source_counts.get(src, 0) + 1

            for i, cand in enumerate(candidates):
                relevance = cand.score
                # Penalty proportional to how many times this source is already selected
                overlap = source_counts.get(cand.purana, 0)
                # Soft penalty: first duplicate costs 0.15 of max rrf score, each extra 0.1 more
                max_rrf = candidates[0].score if candidates else 1.0
                diversity_penalty = overlap * 0.15 * max_rrf
                mmr_score = mmr_lambda * relevance - (1.0 - mmr_lambda) * diversity_penalty
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i

            chosen = candidates.pop(best_idx)
            final_results.append(
                SearchResult(chunk=chosen.chunk, score=chosen.score, rank=len(final_results))
            )
            selected_sources.append(chosen.purana)

        logger.debug(
            "Hybrid+MMR search for %r: %d semantic + %d keyword → %d fused → %d diverse results",
            query, len(semantic_results), len(keyword_results), len(candidates) + len(final_results), len(final_results),
        )
        return final_results

    # ── Find All Instances ─────────────────────────────────────────────

    def find_all_instances(
        self,
        query:      str,
        min_score:  float                  = 0.3,
        category:   str | None            = None,
        max_results: int                   = 200,
    ) -> list[SearchResult]:
        """
        Find ALL passages matching a query across all indexed texts.
        Returns a comprehensive list, not just top-k.

        This is the "find every mention of Narada" function.
        Uses a large fetch size from both indexes, then deduplicates.
        """
        # Fetch many more results than usual
        fetch_k = min(max_results * 2, self.total_documents)
        filters = {"category": category} if category else None

        semantic_results = self.semantic_search(query, top_k=fetch_k, filters=filters)
        keyword_results  = self.keyword_search(query,  top_k=fetch_k)

        # Merge and deduplicate by chunk ID
        seen_ids: set[str] = set()
        all_results: list[SearchResult] = []

        for result in semantic_results + keyword_results:
            if result.id in seen_ids:
                continue
            if result.score >= min_score:
                seen_ids.add(result.id)
                all_results.append(result)

        # Sort by score descending
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:max_results]

    # ── Purana Statistics ──────────────────────────────────────────────

    def get_purana_stats(self) -> list[dict[str, Any]]:
        """Return stats for all indexed Puranas (name + chunk count)."""
        if not self._collection:
            return []
        try:
            # Get all unique purana values from metadata
            results = self._collection.get(include=["metadatas"])
            counts: dict[str, int] = {}
            for meta in results.get("metadatas", []):
                purana = meta.get("purana", "Unknown")
                counts[purana] = counts.get(purana, 0) + 1

            return [
                {"name": purana, "chunk_count": count}
                for purana, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
            ]
        except Exception as e:
            logger.error("Error fetching purana stats: %s", e)
            return []
