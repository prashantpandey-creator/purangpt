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
import re
import hashlib
import unicodedata
import asyncpg
from typing import Any, Optional

try:
    import redis as redis_sync
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        # Probe synchronously at startup; if Redis is unreachable or auth fails,
        # disable caching entirely so no per-request warnings flood the logs.
        try:
            _probe = redis_sync.from_url(REDIS_URL, socket_connect_timeout=2)
            _probe.ping()
            _probe.close()
            redis_client = redis.from_url(REDIS_URL)
        except Exception as _e:
            logging.getLogger(__name__).warning("Redis unavailable (%s) — search cache disabled", _e)
            redis_client = None
    else:
        redis_client = None
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


# ── Ranking helpers (pure, unit-tested in test_search_ranking.py) ───────────

FLOOR_REL_FRAC = 0.55


def _floor_keep(rel: float, top_score: float, frac: float = FLOOR_REL_FRAC) -> bool:
    """Gate for scripture-floor injection. The floor exists to give broad English
    thematic queries cross-text breadth — there, every category pool returns a hit
    that scores NEAR the best, so it passes. A narrow named-entity query drops
    off-topic pools whose scores fall below the fraction threshold."""
    if top_score <= 0:
        return True
    return rel >= frac * top_score


def _mmr_select(results: list["SearchResult"], top_k: int,
                mmr_lambda: float = 0.7) -> list["SearchResult"]:
    """MMR with diversity penalty scaled by the candidate's OWN score.
    A weakly-relevant chunk from a fresh source can never out-rank a strongly-relevant
    one already shown — the old `max_rrf` global let parity-injected off-topic chunks
    leapfrog genuine results."""
    ordered = sorted(results, key=lambda x: x.score, reverse=True)
    final: list["SearchResult"] = []
    selected_sources: list[str] = []
    candidates = list(ordered)
    while len(final) < top_k and candidates:
        if not final:
            best = candidates.pop(0)
            final.append(SearchResult(chunk=best.chunk, score=best.score, rank=0))
            selected_sources.append(best.purana)
            continue
        source_counts: dict[str, int] = {}
        for src in selected_sources:
            source_counts[src] = source_counts.get(src, 0) + 1
        best_mmr, best_idx = -math.inf, 0
        for i, cand in enumerate(candidates):
            overlap = source_counts.get(cand.purana, 0)
            diversity_penalty = overlap * 0.15 * cand.score
            mmr_score = mmr_lambda * cand.score - (1.0 - mmr_lambda) * diversity_penalty
            if mmr_score > best_mmr:
                best_mmr, best_idx = mmr_score, i
        chosen = candidates.pop(best_idx)
        final.append(SearchResult(chunk=chosen.chunk, score=chosen.score, rank=len(final)))
        selected_sources.append(chosen.purana)
    return final


_IAST_FOLD = str.maketrans(
    "āĀīĪūŪṛṚṝḷṃṄṅñṭṬḍḌṇṆśŚṣṢḥḤ",
    "aaiiuurrrlmnnnttddnnsssshh",
)
_KW_SKIP = frozenset({"and", "the", "or", "with", "what", "how", "who", "was",
                      "for", "from", "that", "this", "about", "does", "did"})


def _iast_ascii(text: str) -> str:
    """Fold IAST diacritics to ASCII for cross-script substring matching."""
    return unicodedata.normalize("NFC", text).translate(_IAST_FOLD).lower()


def _keyword_promote(results: list["SearchResult"], fts_phrase: str | None,
                     query: str = "") -> list["SearchResult"]:
    """Re-rank: float chunks that contain query terms (after ASCII folding) to the top.

    This bridges the IAST gap that breaks the Postgres FTS channel for Sanskrit
    named-entity queries: 'Krishna' and 'Sudharma' are ASCII; the corpus stores
    'kṛṣṇa' and 'sudharmā'. After _iast_ascii both collapse to 'krsna'/'sudharma',
    so substring matching finds them. No result is dropped; only ordering changes.

    Term-length floor of 7 filters common Sanskrit vocabulary (dharma=6, sabha=5,
    karma=5, loka=4) that would otherwise match thousands of unrelated chunks and
    defeat the promotion. Specific names like sudharma(8), dvaraka(7), krishna(7)
    pass through."""
    raw = fts_phrase or query or ""
    terms = [_iast_ascii(t) for t in re.findall(r'\w+', raw)
             if len(t) >= 7 and t.lower() not in _KW_SKIP]
    if not terms:
        return results
    hits = [r for r in results if any(t in _iast_ascii(r.text) for t in terms)]
    misses = [r for r in results if not any(t in _iast_ascii(r.text) for t in terms)]
    return hits + misses


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
        corpus_type: str | None = None,
        secondary_embed_phrase: str | None = None,
    ) -> list[SearchResult]:
        """
        Executes the hybrid_search RPC on Postgres, which performs pgvector distance
        and FTS websearch natively, fusing them with RRF.

        Args:
            query:                  Original user query (used for FTS if fts_phrase not given).
            embed_phrase:           Enriched phrase for embedding, e.g. from SanskritQueryProcessor.
                                    Falls back to "query: {query}" if None.
            fts_phrase:             Multi-term OR phrase for Postgres FTS.
                                    Falls back to raw query if None.
            secondary_embed_phrase: Optional Devanagari Sanskrit phrase for bi-directional
                                    retrieval. e5-small has a hard cross-lingual gap — English
                                    queries embed near English darshans; a second search with
                                    this Devanagari phrase opens the Sanskrit manifold. Results
                                    from both passes are unioned before MMR.
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
            # corpus_type changes the result set (scripture-only / guruji-only / floored)
            # but was absent from the key — a guruji-only query collided with the default
            # mixed result for the same text. Part of the cache identity.
            "corpus_type": corpus_type,
            # secondary_embed_phrase (Devanagari bi-query) opens the Sanskrit manifold
            "secondary_embed_phrase": secondary_embed_phrase,
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

        # Guruji material categories — chunks with these categories are from Shailendra
        # Sharma's darshans/commentaries (voice/cognition), NOT citable scripture.
        # "yoga_commentary" is Yogeshwari, Sharma's own Bhagavad Gita commentary — his
        # voice, not independent scripture, so it must not count toward the scripture floor.
        GURUJI_CATEGORIES = {"yogic-commentary", "yogic-discourse", "yoga_commentary"}

        try:
            # Embed primary phrase + optional Devanagari secondary in one batch call.
            import asyncio
            loop = asyncio.get_running_loop()
            phrase_to_embed = embed_phrase if embed_phrase else f"query: {query}"
            phrases = [phrase_to_embed]
            if secondary_embed_phrase:
                phrases.append(f"query: {secondary_embed_phrase}")

            embs = await loop.run_in_executor(
                None,
                lambda: self._embed_model.encode(phrases, show_progress_bar=False),
            )
            primary_emb = embs[0].tolist() if hasattr(embs[0], "tolist") else list(embs[0])
            emb_str = "[" + ",".join(map(str, primary_emb)) + "]"
            sec_emb_str = None
            if secondary_embed_phrase:
                sec_emb = embs[1].tolist() if hasattr(embs[1], "tolist") else list(embs[1])
                sec_emb_str = "[" + ",".join(map(str, sec_emb)) + "]"

            # Build filter JSON
            pg_filter = {}
            if filters:
                for k, v in filters.items():
                    if isinstance(v, dict) and "$eq" in v:
                        pg_filter[k] = v["$eq"]
                    else:
                        pg_filter[k] = v
            filter_json = json.dumps(pg_filter)

            # Strip generic short-word terms (e.g. "dharma", "sabha", "karma") from the
            # FTS phrase before sending to Postgres. These common Sanskrit words appear
            # in unrelated texts (Amarakosha vocabulary headers, etc.) and generate false
            # FTS rank boosts that override the semantic signal. Only named-entity-length
            # terms (>=7 chars) are precise enough for FTS discrimination.
            if fts_phrase:
                _fts_terms = [t for t in re.findall(r'\w+', fts_phrase)
                              if len(t) >= 7 and t.lower() not in _KW_SKIP]
                fts_query = " OR ".join(_fts_terms) if _fts_terms else fts_phrase
            else:
                fts_query = query
            fetch_k = top_k * 6 if corpus_type else top_k * 4

            async def _fetch(emb_s: str, fk: int):
                async with self._pool.acquire() as conn:
                    return await conn.fetch(
                        'SELECT id, content, metadata, similarity '
                        'FROM hybrid_search($1, $2::vector, $3, $4::jsonb)',
                        fts_query, emb_s, fk, filter_json)

            if sec_emb_str:
                # Run both retrievals in parallel; union by id (best score wins).
                primary_rows, sec_rows = await asyncio.gather(
                    _fetch(emb_str, fetch_k),
                    _fetch(sec_emb_str, fetch_k // 2),
                )
                merged: dict[str, Any] = {}
                for row in primary_rows:
                    merged[row['id']] = row
                for row in sec_rows:
                    rid = row['id']
                    if rid not in merged or float(row['similarity']) > float(merged[rid]['similarity']):
                        merged[rid] = row
                rows = sorted(merged.values(), key=lambda r: float(r['similarity']), reverse=True)
                logger.debug("bi-query union: primary=%d sec=%d merged=%d", len(primary_rows), len(sec_rows), len(rows))
            else:
                rows = await _fetch(emb_str, fetch_k)

            if not rows:
                return []

            # Create SearchResult objects
            results = []
            for rank, row in enumerate(rows):
                meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                score = float(row['similarity'])
                chunk = {**meta, "id": row['id'], "text": row['content']}
                results.append(SearchResult(chunk=chunk, score=score, rank=rank))

            # corpus_type filter: "scripture" excludes Guruji chunks; "guruji" keeps only them.
            # This runs BEFORE sharma_weighting so score inflation doesn't fight the filter.
            if corpus_type == "scripture":
                results = [r for r in results
                           if (r.chunk.get("category") or "").lower() not in GURUJI_CATEGORIES
                           and not r.id.startswith("darshan-")]
            elif corpus_type == "guruji":
                results = [r for r in results
                           if (r.chunk.get("category") or "").lower() in GURUJI_CATEGORIES
                           or r.id.startswith("darshan-")]

            # ── CANONICAL ILIKE INJECTION ─────────────────────────────────────
            # e5-small cannot find Sanskrit named entities in oblique grammatical
            # cases (sudharmāṃ, sudharmāyāṃ rank ~2758 for the query that asks
            # about Sudharmā). The ASCII stem of the canonical term (e.g. 'sudharm'
            # from 'sudharma') IS a substring of every IAST declined form — LIKE
            # '%sudharm%' matches sudharmā, sudharmāṃ, sudharmāyāṃ, sudharmāk.
            # Inject up to 20 such chunks at their actual semantic score so MMR
            # can interleave them with the semantic pool.
            if fts_phrase:
                _canon_stems = [_iast_ascii(t)[:7]
                                for t in re.findall(r'\w+', fts_phrase)
                                if len(t) >= 7 and t.lower() not in _KW_SKIP]
                if _canon_stems:
                    _seen_ids = {r.id for r in results}
                    try:
                        for _stem in _canon_stems[:2]:
                            async with self._pool.acquire() as _ci:
                                _ilike_rows = await _ci.fetch(
                                    'SELECT id, content, metadata, '
                                    '       1 - (embedding <=> $2::vector) AS similarity '
                                    'FROM purana_verses '
                                    'WHERE embedding IS NOT NULL AND content LIKE $1 '
                                    'ORDER BY embedding <=> $2::vector LIMIT 20',
                                    f"%{_stem}%", emb_str)
                            for _row in _ilike_rows:
                                if _row["id"] in _seen_ids:
                                    continue
                                _m = (json.loads(_row["metadata"])
                                      if isinstance(_row["metadata"], str) else _row["metadata"])
                                if corpus_type == "scripture" and (
                                        (_m.get("category") or "").lower() in GURUJI_CATEGORIES
                                        or _row["id"].startswith("darshan-")):
                                    continue
                                _seen_ids.add(_row["id"])
                                _chunk = {**_m, "id": _row["id"], "text": _row["content"]}
                                results.append(SearchResult(chunk=_chunk,
                                                            score=float(_row["similarity"]),
                                                            rank=len(results)))
                    except Exception as _e:
                        logger.warning("canonical ilike injection failed: %s", _e)

            # Apply source weighting
            if sharma_weighting:
                for res in results:
                    cat = (res.chunk.get("category") or "").lower()
                    if cat in GURUJI_CATEGORIES:
                        res.score *= 1.6
                    elif res.id.startswith("darshan-") or res.purana == "Shailendra Sharma Darshans":
                        res.score *= 0.6

            # ── SCRIPTURE FLOOR ──────────────────────────────────────────────
            # English natural-language queries embed near the English darshan
            # transcripts and never surface Sanskrit scripture (cross-lingual gap
            # in e5-small), so the answer quotes Guruji's voice but can't synthesize
            # across the texts. Guarantee a scripture quota by retrieving per-category
            # scripture pools at the DB level — where ranking happens WITHIN scripture
            # — then let MMR source-diversity interleave them ("all angles"). Validated
            # live: lifts a 0-scripture English query to ~20 results across ~14 texts.
            # Skipped when the caller explicitly wants guruji-only.
            if corpus_type != "guruji":
                def _is_scripture(r):
                    return ((r.chunk.get("category") or "").lower() not in GURUJI_CATEGORIES
                            and not str(r.id).startswith("darshan-"))
                floor = max(3, top_k // 2)
                # Count scripture in the OUTPUT window (top_k by score), NOT the full
                # fetch_k candidate pool. fetch_k = top_k*4 drags deep-tail scripture into
                # `results` that can never survive MMR against the ×1.6-boosted darshan, so
                # counting the whole pool reports the floor as already met and it never
                # fires — the bug that left English/conceptual queries 100% darshan. Measure
                # what will actually be returned.
                _window = sorted(results, key=lambda r: r.score, reverse=True)[:top_k]
                if sum(1 for r in _window if _is_scripture(r)) < floor:
                    # Every non-Guruji category (mirror of the corpus minus GURUJI_CATEGORIES).
                    # A missing category silently starves the floor of that whole tradition —
                    # shaiva-vaishnava (4k), nath-sampradaya (Guruji's own Nath lineage), and
                    # kosha were absent before and never surfaced.
                    SCRIPTURE_CATS = ["mahapurana", "vaishnava", "vedic", "shaiva",
                                      "shaiva-vaishnava", "shakta", "dharma", "vedanta",
                                      "kosha", "nath-sampradaya", "mixed", "other"]
                    per = max(2, top_k // 2)

                    async def _scrip_pool(cat):
                        async with self._pool.acquire() as c:
                            return await c.fetch(
                                'SELECT id, content, metadata, similarity '
                                'FROM hybrid_search($1, $2::vector, $3, $4::jsonb)',
                                fts_query, emb_str, per, json.dumps({"category": cat}))
                    try:
                        pools = await asyncio.gather(
                            *[_scrip_pool(c) for c in SCRIPTURE_CATS],
                            return_exceptions=True)
                        seen = {r.id for r in results}
                        top_score = max((r.score for r in results), default=1.0)
                        for pool in pools:
                            if isinstance(pool, Exception):
                                continue
                            for row in pool:
                                if row["id"] in seen:
                                    continue
                                seen.add(row["id"])
                                m = (json.loads(row["metadata"])
                                     if isinstance(row["metadata"], str) else row["metadata"])
                                if (m.get("category") or "").lower() in GURUJI_CATEGORIES:
                                    continue
                                rel = float(row["similarity"])
                                if not _floor_keep(rel, top_score):
                                    continue
                                chunk = {**m, "id": row["id"], "text": row["content"]}
                                results.append(SearchResult(chunk=chunk, score=rel,
                                                            rank=len(results)))
                    except Exception as e:
                        logger.warning("scripture floor failed, skipping: %s", e)

            # Sort by updated scores
            results.sort(key=lambda x: x.score, reverse=True)

            # Select top_k with MMR diversity (cand.score-based penalty).
            final_results = _mmr_select(results, top_k, mmr_lambda)

            # ── SCRIPTURE FLOOR GUARANTEE (post-MMR, deterministic) ──────────
            # MMR is heuristic. Guarantee the scripture quota actually landed in the
            # output by swapping the lowest-scored darshan for the best scripture
            # candidates MMR left behind. No-op in the common case (the floor append
            # already wins MMR); this is the belt-and-braces that makes "all angles"
            # a guarantee, not a hope. _is_scripture/floor are in scope from the floor
            # block above (same `corpus_type != "guruji"` guard).
            if corpus_type != "guruji":
                _scrip_in_final = [r for r in final_results if _is_scripture(r)]
                if len(_scrip_in_final) < floor:
                    _chosen_ids = {r.id for r in final_results}
                    _spare = sorted(
                        (r for r in results if _is_scripture(r) and r.id not in _chosen_ids),
                        key=lambda r: r.score, reverse=True)
                    _darshan = sorted(
                        (r for r in final_results if not _is_scripture(r)),
                        key=lambda r: r.score)  # lowest score first
                    _need = floor - len(_scrip_in_final)
                    for i in range(min(_need, len(_spare), len(_darshan))):
                        final_results.remove(_darshan[i])
                        final_results.append(_spare[i])
                    final_results.sort(key=lambda x: x.score, reverse=True)

            # Promote chunks that contain query keywords (IAST-bridged substring match).
            # Bridges the FTS gap for Sanskrit named-entity queries: 'Krishna'/'Sudharma'
            # are ASCII; the IAST corpus stores 'kṛṣṇa'/'sudharmā'. After _iast_ascii
            # folding both collapse so substring match finds genuine hits. No result is
            # dropped; only ordering changes — keyword-matching chunks rise first.
            final_results = _keyword_promote(final_results, fts_phrase, query)

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

    # ── Content Explorer Data Layer ──────────────────────────────────

    async def get_chunk_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Fetch a single verse/chunk by its primary key."""
        if not self._pool:
            return None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT id, content, metadata FROM purana_verses WHERE id = $1',
                chunk_id
            )
        if not row:
            return None
        meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
        return {**meta, "id": row['id'], "text": row['content']}

    async def find_similar_verses(self, chunk_id: str, top_k: int = 10,
                                  requesting_user: str | None = None) -> list[SearchResult]:
        """Find the top_k most semantically similar verses to the given chunk.

        Privacy scope (Sangama): a workspace (user-uploaded) chunk is only ever
        returned to the seeker who uploaded it. The public corpus — chunks with no
        'workspace' flag in metadata — is visible to everyone; another seeker's
        private upload is NEVER surfaced. A guest (requesting_user=None) sees only the
        public corpus. The `(workspace IS NULL OR user_id = $3)` clause is the whole
        guard: public rows pass the first branch, the owner's own uploads pass the
        second, everyone else's uploads pass neither.
        """
        if not self._pool:
            return []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch('''
                WITH source AS (
                    SELECT embedding FROM purana_verses WHERE id = $1
                )
                SELECT pv.id, pv.content, pv.metadata,
                       1 - (pv.embedding <=> s.embedding) AS similarity
                FROM purana_verses pv, source s
                WHERE pv.id != $1
                  AND pv.embedding IS NOT NULL
                  AND (pv.metadata->>'workspace' IS NULL
                       OR pv.metadata->>'user_id' = $3)
                ORDER BY pv.embedding <=> s.embedding
                LIMIT $2
            ''', chunk_id, top_k, requesting_user)
        results = []
        for rank, row in enumerate(rows):
            meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            chunk = {**meta, "id": row['id'], "text": row['content']}
            results.append(SearchResult(chunk=chunk, score=float(row['similarity']), rank=rank))
        return results

    # Catalog slug → actual chunk-id prefix, only where they diverge (audited against
    # the live index 2026-06-27). Every other slug already equals its chunk-id prefix.
    _SLUG_PREFIX_REMAP = {
        "bhagavad_gita":   "gita",
        "brahma_sutras":   "brahmasutras",
        "gorakshashataka": "goraksha_shataka",
        "hatha_yoga":      "hatha_yoga_pradipika",
    }

    async def get_chapter_verses(
        self, text_id: str, chapter: int, limit: int = 500
    ) -> list[dict[str, Any]]:
        """Fetch all verses for a given text + chapter, ordered by id.

        Resolves the caller's text_id to chunks TWO ways, so every caller works:
        - the corpus reader passes a catalog slug → matched by chunk-id prefix
          (`id LIKE '{prefix}-{chapter}-%'`); the slug IS the prefix for most texts,
          with four audited remaps above. This is what the display-name filter alone
          missed: the index stores `purana` as the long display name
          ("Vishnu Purana (Critical Edition)"), never the slug.
        - the citation deep-link + workspace reader pass the metadata `purana`
          (display name / doc_id) → matched by `metadata @> {purana, chapter}`.
        The OR covers all three input shapes; the '-{chapter}-' delimiter keeps one
        text's prefix from bleeding into another's.
        """
        if not self._pool:
            return []
        prefix = self._SLUG_PREFIX_REMAP.get(text_id, text_id)
        # Escape LIKE wildcards so underscores in slugs (yoga_vasistha, shiva_1_7)
        # match literally, not as the single-char wildcard.
        esc = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        id_like = f"{esc}-{chapter}-%"
        filter_meta = json.dumps({"purana": text_id, "chapter": chapter})
        async with self._pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT id, content, metadata
                FROM purana_verses
                WHERE id LIKE $1 OR metadata @> $2::jsonb
                ORDER BY id
                LIMIT $3
            ''', id_like, filter_meta, limit)
            # Chaptered texts (Mahabharata is the only one — real parvas, no chapter 0)
            # have nothing at the reader's default chapter 0. Fall back to the text's
            # lowest actual chapter so "open the text" still lands on its beginning.
            # ORDER BY id puts chapter 1 first. Flat texts never reach here (their
            # chapter-0 query already matched), so this only rescues the chaptered case.
            if not rows:
                rows = await conn.fetch('''
                    SELECT id, content, metadata
                    FROM purana_verses
                    WHERE id LIKE $1
                    ORDER BY id
                    LIMIT $2
                ''', f"{esc}-%", limit)
        results = []
        for row in rows:
            meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            results.append({**meta, "id": row['id'], "text": row['content']})
        return results

    async def get_doc_chunks(
        self, doc_id: str, user_id: str, limit: int = 80
    ) -> list[dict[str, Any]]:
        """Fetch a workspace document's own chunks, in order — scoped to its owner.

        The `metadata @> {doc_id, user_id}` containment is the whole guard: a chunk is
        returned only when BOTH its doc_id and user_id match, so one seeker can never
        read another seeker's uploaded document. Used by the paper-review endpoint to
        assemble the text the Guru reviews.
        """
        if not self._pool:
            return []
        filter_meta = json.dumps({"doc_id": doc_id, "user_id": user_id})
        async with self._pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT id, content, metadata
                FROM purana_verses
                WHERE metadata @> $1::jsonb
                ORDER BY id
                LIMIT $2
            ''', filter_meta, limit)
        results = []
        for row in rows:
            meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
            results.append({**meta, "id": row['id'], "text": row['content']})
        return results

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
