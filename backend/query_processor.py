"""
PuranGPT — Sanskrit-Aware Query Processor
==========================================
Replaces the static _SANSKRIT_SYNONYMS map with a dynamic LLM-powered
expansion pipeline that understands any Sanskrit term in any romanization
scheme, along with indic-transliteration normalization.

Key outputs per query:
  - canonical IAST form        ("maheśvara")
  - top synonyms               (["shiva", "rudra", "mahadeva"])
  - enriched embedding phrase  ("query: maheśvara, epithet of Shiva")
  - FTS multi-term phrase      ("maheśvara | shiva | rudra")
  - Devanagari form            ("महेश्वर") for GRETIL Devanagari search
  - detected language          ("Sanskrit (Roman)" | "Hindi" | "English" | "Devanagari")
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None
except ImportError:
    redis_client = None

logger = logging.getLogger(__name__)

CACHE_TTL = 86400 * 7  # Cache expansions for 7 days

# ── Sanskrit phoneme heuristic ─────────────────────────────────────────────
# Common endings of Sanskrit words in Roman transliteration.
# We use this to cheaply detect whether a token is likely Sanskrit
# before spending an LLM call on it.
_SKT_ENDINGS = re.compile(
    r"(a|am|ya|va|na|sha|shva|tha|dha|ma|ra|ka|ga|la|ha|tra|"
    r"pati|deva|vara|atma|brahm|dharma|karma|marga|purana|tantra|"
    r"mantra|shakti|vidya|loka|pada|stha|ksha|shti|anda|anta)$",
    re.IGNORECASE,
)

_SKT_ROOTS = {
    # Well-known roots that appear as prefixes/standalone
    "brahm", "vishnu", "shiva", "shakti", "devi", "rudra", "indra",
    "agni", "vayu", "varuna", "yama", "soma", "surya", "chandra",
    "param", "para", "maha", "adi", "sat", "chit", "ananda", "atma",
    "dharma", "karma", "moksha", "maya", "prakriti", "purusha",
    "yoga", "tantra", "mantra", "yantra", "mudra", "chakra", "nadi",
    "prana", "kundalini", "guru", "shishya", "samadhi", "nirvana",
    "samsara", "lila", "bhakti", "jnana", "vairagya", "viveka",
}


def _is_likely_sanskrit(query: str) -> bool:
    """
    Cheap heuristic: does this query (already ASCII) look like Sanskrit?
    Returns True if any token matches Sanskrit phoneme patterns.
    Intentionally has false positives — the LLM will catch non-Sanskrit.
    """
    tokens = query.lower().split()
    for tok in tokens:
        # Check root membership
        for root in _SKT_ROOTS:
            if tok.startswith(root) or tok == root:
                return True
        # Check suffix patterns (only for tokens ≥ 5 chars to avoid noise)
        if len(tok) >= 5 and _SKT_ENDINGS.search(tok):
            return True
    return False


def _is_devanagari(text: str) -> bool:
    return any("\u0900" <= c <= "\u097F" for c in text)


def _normalize_iast(text: str) -> str:
    """Strip IAST diacritics to ASCII for fuzzy matching."""
    import unicodedata as _ud
    _MAP = str.maketrans(
        "āĀīĪūŪṛṚṝḷṃṄṅñṭṬḍḌṇṆśŚṣṢḥḤ",
        "aaiiuurrrlmnnnttddnnsssshh"
    )
    return _ud.normalize("NFC", text).translate(_MAP).lower()


def _to_devanagari(iast_text: str) -> str:
    """
    Convert IAST text to Devanagari using indic-transliteration.
    Returns empty string if the library is not installed or conversion fails.
    """
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
        return transliterate(iast_text, sanscript.IAST, sanscript.DEVANAGARI)
    except ImportError:
        logger.debug("indic-transliteration not installed; skipping Devanagari conversion")
        return ""
    except Exception as e:
        logger.debug("Devanagari conversion failed for %r: %s", iast_text, e)
        return ""


# ── QueryExpansion dataclass ───────────────────────────────────────────────

@dataclass
class QueryExpansion:
    """
    The fully-expanded, normalized form of a user query.
    Used downstream to drive both pgvector and GRETIL search.
    """
    original: str                   # raw user input
    detected_lang: str              # "Sanskrit (Roman)" | "Hindi" | "English" | "Devanagari"
    is_sanskrit: bool               # True if any Sanskrit expansion was performed
    canonical: str                  # canonical IAST form (or original if English)
    synonyms: list[str] = field(default_factory=list)   # top 4 Sanskrit synonyms
    english_gloss: str = ""         # English explanation of the concept
    devanagari: str = ""            # Devanagari script form (for GRETIL)

    @property
    def embed_phrase(self) -> str:
        """
        Enriched phrase for the embedding model.
        Preserves the full semantic context of the original query while injecting
        canonical Sanskrit terms to land in a much better region of the vector space.
        """
        if not self.is_sanskrit or not self.english_gloss:
            return self.original
            
        # Join canonical and synonyms for a dense keyword cluster
        all_names = [self.canonical] + self.synonyms[:3]
        names_str = ", ".join(dict.fromkeys(all_names))
        
        return f"{self.original} (Context: {names_str} — {self.english_gloss})"

    @property
    def fts_phrase(self) -> str:
        """
        Multi-term OR phrase for Postgres FTS websearch_to_tsquery.
        Must use literal ' OR ' instead of '|' because websearch_to_tsquery
        does not parse '|' as a logical operator.
        """
        terms = [self.canonical] + self.synonyms[:3]
        return " OR ".join(dict.fromkeys(terms))  # deduplicate, preserve order

    @property
    def gretil_search_terms(self) -> list[str]:
        """
        All terms to search GRETIL with, in priority order.
        Includes Devanagari if available.
        """
        terms = [self.canonical]
        if self.devanagari:
            terms.append(self.devanagari)
        terms.extend(self.synonyms[:2])
        return [t for t in dict.fromkeys(terms) if t]  # deduplicate, no empty


# ── LLM prompt ────────────────────────────────────────────────────────────

_SANSKRIT_EXPANSION_PROMPT = """\
You are a Sanskrit NLP and Vedic philosophy expert. The user typed this search query: "{query}"

Determine if this query contains Sanskrit terms (in any romanization scheme: IAST, Harvard-Kyoto, common English transliteration, etc.).

Respond with ONLY valid JSON, no extra text:
{{
  "is_sanskrit": true,
  "canonical_iast": "the canonical IAST form of the primary term (e.g. maheśvara)",
  "synonyms": ["shiva", "rudra", "mahadeva", "hara"],
  "english_gloss": "brief English gloss, max 12 words (e.g. epithet of Shiva, the great lord)",
  "devanagari": "महेश्वर"
}}

If the query is plain English with NO Sanskrit terms, respond:
{{
  "is_sanskrit": false,
  "canonical_iast": "{query}",
  "synonyms": [],
  "english_gloss": "",
  "devanagari": ""
}}

Rules:
- canonical_iast: use proper IAST diacritics (ā, ī, ū, ṛ, ṃ, ś, ṣ, ṭ, ḍ, ṇ, ḥ)
- synonyms: Sanskrit names/epithets only, max 4, ordered by relevance
- english_gloss: factual, concise — not a definition, just enough to enrich the embedding
- If query has multiple Sanskrit terms, focus on the primary concept
"""


# ── SanskritQueryProcessor ────────────────────────────────────────────────

class SanskritQueryProcessor:
    """
    Entry point for query understanding. Call `expand(query)` before search.

    Decision tree:
      1. Devanagari script       → LLM translates (existing path preserved)
      2. ASCII + looks Sanskrit  → LLM expands (new path)
      3. ASCII + looks English   → pass through unchanged (fast path preserved)
    """

    def __init__(self, llm_caller):
        """
        llm_caller: async callable (messages: list[dict]) -> str
        Should be call_llm_once or equivalent. Injected to avoid circular imports.
        """
        self._call_llm = llm_caller

    async def expand(self, query: str) -> QueryExpansion:
        """
        Main entry point. Returns a QueryExpansion for any query.
        Never raises — falls back to passthrough on any error.
        """
        query = query.strip()

        # ── Fast path: Devanagari ──────────────────────────────────────────
        if _is_devanagari(query):
            return await self._expand_devanagari(query)

        # ── Fast path: doesn't look Sanskrit → return as-is ───────────────
        if not _is_likely_sanskrit(query):
            return QueryExpansion(
                original=query,
                detected_lang="English",
                is_sanskrit=False,
                canonical=query,
            )

        # ── Sanskrit path: call LLM to expand ─────────────────────────────
        return await self._expand_sanskrit(query)

    async def _expand_sanskrit(self, query: str) -> QueryExpansion:
        """LLM-powered expansion for Sanskrit terms in Roman script."""
        cache_key = f"expansion:{query.lower().strip()}"
        
        # 1. Check Redis cache
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    logger.debug("Cache hit for Sanskrit expansion: %r", query)
                    return QueryExpansion(
                        original=query,
                        detected_lang=data.get("detected_lang", "Sanskrit (Roman)"),
                        is_sanskrit=data.get("is_sanskrit", False),
                        canonical=data.get("canonical", query),
                        synonyms=data.get("synonyms", []),
                        english_gloss=data.get("english_gloss", ""),
                        devanagari=data.get("devanagari", ""),
                    )
            except Exception as e:
                logger.warning("Redis cache read failed for %r: %s", query, e)

        # 2. Call LLM
        prompt = _SANSKRIT_EXPANSION_PROMPT.format(query=query)
        try:
            raw = await self._call_llm(
                [{"role": "user", "content": prompt}],
                temperature=0.0,  # deterministic
            )
            # Strip markdown code fences if present
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
            # Strip DeepSeek-style <think>...</think> tags if they leak into content
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            data = json.loads(raw)

            if not data.get("is_sanskrit", False):
                return QueryExpansion(
                    original=query,
                    detected_lang="English",
                    is_sanskrit=False,
                    canonical=query,
                )

            canonical = data.get("canonical_iast") or _normalize_iast(query)
            synonyms  = [s.strip() for s in data.get("synonyms", []) if s.strip()][:4]
            gloss     = (data.get("english_gloss") or "").strip()
            deva      = data.get("devanagari", "").strip()

            # Fallback: generate Devanagari from canonical IAST via library
            if not deva:
                deva = _to_devanagari(canonical)

            logger.info(
                "Sanskrit expansion: %r → canonical=%r synonyms=%r",
                query, canonical, synonyms
            )

            expansion = QueryExpansion(
                original=query,
                detected_lang="Sanskrit (Roman)",
                is_sanskrit=True,
                canonical=canonical,
                synonyms=synonyms,
                english_gloss=gloss,
                devanagari=deva,
            )
            
            # Save to Redis
            if redis_client:
                try:
                    cache_data = json.dumps({
                        "detected_lang": expansion.detected_lang,
                        "is_sanskrit": expansion.is_sanskrit,
                        "canonical": expansion.canonical,
                        "synonyms": expansion.synonyms,
                        "english_gloss": expansion.english_gloss,
                        "devanagari": expansion.devanagari,
                    })
                    await redis_client.setex(cache_key, CACHE_TTL, cache_data)
                except Exception as e:
                    logger.warning("Redis cache write failed for %r: %s", query, e)
                    
            return expansion

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Sanskrit expansion JSON parse failed for %r: %s", query, e)
        except Exception as e:
            logger.warning("Sanskrit expansion failed for %r: %s", query, e)

        # Graceful fallback: treat as passthrough
        return QueryExpansion(
            original=query,
            detected_lang="Sanskrit (Roman)",
            is_sanskrit=False,
            canonical=_normalize_iast(query),
        )

    async def _expand_devanagari(self, query: str) -> QueryExpansion:
        """
        For Devanagari input: transliterate to IAST, then expand.
        Preserves the existing detect_and_translate_query path for Hindi queries
        but adds Sanskrit awareness.
        """
        # Try library-based transliteration first (fast, no LLM)
        iast_form = ""
        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            iast_form = transliterate(query, sanscript.DEVANAGARI, sanscript.IAST)
        except Exception:
            pass

        if iast_form:
            # Now expand the IAST form
            expansion = await self._expand_sanskrit(iast_form)
            expansion.original = query
            expansion.detected_lang = "Devanagari"
            expansion.devanagari = query  # keep original Devanagari
            return expansion

        # Fallback: treat as opaque string
        return QueryExpansion(
            original=query,
            detected_lang="Devanagari",
            is_sanskrit=True,
            canonical=query,
            devanagari=query,
        )
