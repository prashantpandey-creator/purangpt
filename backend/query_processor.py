"""
PuranGPT — Cross-Lingual, Sanskrit-Aware Query Processor
========================================================
Maps a seeker's query — in ANY language (English, Hindi, Russian, Sanskrit) and
ANY script (Latin, Devanagari, Cyrillic) — onto the canonical Sanskrit concepts
that actually appear in the IAST-romanized corpus, so the embedding lands in the
right region of the vector space regardless of the input language.

Why this exists: `multilingual-e5-small` embeds English, Russian, Hindi and
IAST-Sanskrit in *different* neighborhoods. A raw English ("what happens to the
soul after death") or Russian ("что происходит с душой после смерти") query embeds
nowhere near the IAST scripture. The OLD processor only expanded queries that
*looked* Sanskrit (a root/ending heuristic) and passed everything else through
raw — so conceptual English and ALL Cyrillic queries missed the corpus entirely.

The fix: route every non-trivial query through one LLM call that returns
  - canonical IAST term        ("ātman")
  - related IAST synonyms       (["jīva", "puruṣa", "punarjanma"])
  - an ENGLISH gloss of the question  (the cross-lingual anchor)
  - Devanagari form             ("आत्मन्")
and build an `embed_phrase` of  "<english gloss>. Key concepts: <iast terms>".
Because the gloss is the same English meaning for every source language, EN/HI/RU
phrasings of one concept converge on nearly the same embed_phrase → the same
vector → the same scripture.

Key outputs per query:
  - canonical IAST form        ("maheśvara")
  - top synonyms               (["shiva", "rudra", "mahadeva"])
  - enriched embedding phrase  ("the great lord. Key concepts: maheśvara, śiva")
  - FTS multi-term phrase      ("maheśvara OR shiva OR rudra")
  - Devanagari form            ("महेश्वर") for GRETIL Devanagari search
  - detected language          ("Sanskrit (Roman)" | "Hindi" | "English" | "Devanagari")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    import redis as redis_sync
    import redis.asyncio as redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    if REDIS_URL:
        try:
            _probe = redis_sync.from_url(REDIS_URL, socket_connect_timeout=2)
            _probe.ping()
            _probe.close()
            redis_client = redis.from_url(REDIS_URL)
        except Exception as _e:
            logging.getLogger(__name__).warning("Redis unavailable (%s) — expansion cache disabled", _e)
            redis_client = None
    else:
        redis_client = None
except ImportError:
    redis_client = None

logger = logging.getLogger(__name__)

CACHE_TTL = 86400 * 7  # Cache expansions for 7 days
CACHE_VERSION = "v3-notroll"  # bump: engagement+mood removed, graph_terms added to cache
EXPANSION_TIMEOUT_S = float(os.getenv("EXPANSION_TIMEOUT_S", "8"))

# ── Sanskrit phoneme heuristic (retained; informational only) ───────────────
# No longer gates expansion — kept for `detected_lang` hinting and any callers.
_SKT_ENDINGS = re.compile(
    r"(a|am|ya|va|na|sha|shva|tha|dha|ma|ra|ka|ga|la|ha|tra|"
    r"pati|deva|vara|atma|brahm|dharma|karma|marga|purana|tantra|"
    r"mantra|shakti|vidya|loka|pada|stha|ksha|shti|anda|anta)$",
    re.IGNORECASE,
)

_SKT_ROOTS = {
    "brahm", "vishnu", "shiva", "shakti", "devi", "rudra", "indra",
    "agni", "vayu", "varuna", "yama", "soma", "surya", "chandra",
    "param", "para", "maha", "adi", "sat", "chit", "ananda", "atma",
    "dharma", "karma", "moksha", "maya", "prakriti", "purusha",
    "yoga", "tantra", "mantra", "yantra", "mudra", "chakra", "nadi",
    "prana", "kundalini", "guru", "shishya", "samadhi", "nirvana",
    "samsara", "lila", "bhakti", "jnana", "vairagya", "viveka",
}

_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "when", "where", "how", "why", "who", "which", "this", "that", "these",
    "those", "then", "just", "so", "than", "such", "both", "through", "about",
    "for", "is", "of", "to", "in", "it", "you", "he", "she", "we", "they",
    "i", "me", "my", "mine", "your", "yours", "his", "her", "hers", "its",
    "our", "ours", "their", "theirs", "am", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must", "on", "at", "by", "with",
    "from", "into", "up", "down", "out", "over", "under", "again", "here",
    "there", "all", "any", "each", "few", "more", "most", "other", "some",
    "only", "own", "same", "too", "very", "now", "not", "no", "yes",
}

# Trivial / non-retrievable inputs — skip the LLM, pass through fast.
_TRIVIAL = {
    "hi", "hello", "hey", "yo", "thanks", "thank you", "ty", "ok", "okay",
    "yes", "no", "yep", "nope", "cool", "nice", "great", "help", "test",
    "who are you", "what is your name", "what can you do", "namaste", "namaskar",
    "good morning", "good evening", "good night", "bye", "goodbye",
}


def _is_likely_sanskrit(query: str) -> bool:
    """Cheap heuristic: does this ASCII query look like it contains a Sanskrit term?
    Retained for language hinting; no longer used to gate expansion."""
    tokens = [t for t in query.lower().split() if t not in _STOP_WORDS]
    for tok in tokens:
        for root in _SKT_ROOTS:
            if tok.startswith(root) or tok == root:
                return True
        if len(tok) >= 5 and _SKT_ENDINGS.search(tok):
            return True
    return False


def _is_devanagari(text: str) -> bool:
    return any("ऀ" <= c <= "ॿ" for c in text)


def _is_latin(text: str) -> bool:
    """True if the query is (almost) entirely Latin script — i.e. English or
    romanized Sanskrit. Cyrillic / Devanagari / CJK return False."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    latin = sum(1 for c in letters if "a" <= c.lower() <= "z" or "À" <= c <= "ɏ")
    return latin / len(letters) >= 0.8


def _is_trivial(query: str) -> bool:
    ql = query.lower().strip().rstrip("?!. ")
    if len(ql) < 3:
        return True
    if ql in _TRIVIAL:
        return True
    toks = [t for t in re.split(r"\W+", ql) if t]
    if not toks:
        return True
    # all stop-words → nothing to retrieve on
    if all(t in _STOP_WORDS for t in toks):
        return True
    # all tokens are trivial words ("hi hello", "ok thanks", "yes cool")
    if all(t in _TRIVIAL for t in toks):
        return True
    return False


# ── Troll / abuse patterns ─────────────────────────────────────────────────
# Catch obvious insults and noise so the LLM doesn't have to be the gatekeeper.
# These are regex patterns matched against the lowercase query.
_TROLL_PATTERNS = [
    r"^you (are|re)\b.*\b(dog|stupid|idiot|dumb|trash|garbage|useless|worthless|shit|crap|fuck)",
    r"^fuck\b", r"^shit\b",
    r"\b(fuck|shit|asshole|bastard)\b.*you",
    r"^you .* (suck|blow)\b",
    r"^what (the|a) (fuck|shit|hell|crap)",
    r"^(kill|die|shut)\b.*(yourself|you)\b",
    r"^i (hate|despise)\b",
    r"^stfu\b", r"^gtfo\b", r"^wtf\b",
]
_TROLL_RE = [re.compile(p, re.IGNORECASE) for p in _TROLL_PATTERNS]


def _is_trolling(query: str) -> bool:
    """Deterministic troll check — catches what the LLM gatekeeper misses."""
    q = query.strip()
    if len(q) < 2:
        return False
    return any(p.search(q) for p in _TROLL_RE)


def _resolve_engagement(query: str) -> str:
    """Deterministic engagement gate. LLM no longer decides this."""
    if _is_trivial(query):
        return "brief"
    if _is_trolling(query):
        return "redirect"
    return "full"


def _normalize_iast(text: str) -> str:
    """Strip IAST diacritics to ASCII for fuzzy matching."""
    import unicodedata as _ud
    _MAP = str.maketrans(
        "āĀīĪūŪṛṚṝḷṃṄṅñṭṬḍḌṇṆśŚṣṢḥḤ",
        "aaiiuurrrlmnnnttddnnsssshh"
    )
    return _ud.normalize("NFC", text).translate(_MAP).lower()


def _to_devanagari(iast_text: str) -> str:
    """Convert IAST text to Devanagari. Empty string on failure / missing lib."""
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
    """The fully-expanded, normalized form of a user query."""
    original: str                   # raw user input
    detected_lang: str              # "Sanskrit (Roman)" | "Hindi" | "English" | ...
    is_sanskrit: bool               # True if a canonical-Sanskrit expansion was performed
    canonical: str                  # canonical IAST form (or original if passthrough)
    synonyms: list[str] = field(default_factory=list)   # related Sanskrit terms (IAST, for embedding)
    english_gloss: str = ""         # the seeker's question in clear English (x-lingual anchor)
    devanagari: str = ""            # Devanagari script form (for GRETIL)
    engagement: str = "full"        # deterministic gate: _resolve_engagement()
    mood: str = "warm"              # kept for SSE event compatibility, always "warm"
    graph_terms: list[str] = field(default_factory=list)  # entity names for graph recall (English/Sanskrit), distinct from IAST synonyms

    @property
    def _iast_terms(self) -> list[str]:
        return list(dict.fromkeys([t for t in ([self.canonical] + self.synonyms[:4]) if t]))

    @property
    def embed_phrase(self) -> str:
        """
        Enriched phrase for the embedding model.

        Built as "<english gloss>. Key concepts: <iast terms>" — NOT the raw query.
        The English gloss is identical in meaning across source languages, so
        EN/HI/RU phrasings of one concept converge on (nearly) the same phrase and
        therefore the same vector; the IAST terms pull that vector toward the
        IAST-romanized corpus. Falls back to the raw query only when no expansion
        was performed (trivial / failed).
        """
        if not self.is_sanskrit:
            return self.original
        gloss = (self.english_gloss or self.original).strip().rstrip(".?! ")
        # Lead with the canonical IAST term — it is the MOST stable cross-lingual
        # anchor (the LLM maps soul/душа/आत्मा → "ātman" every time), so leading with
        # it pulls EN/HI/RU phrasings of one concept to the same vector neighborhood.
        # Then the English gloss, then the (more variable) synonyms for recall.
        # IAST is always lowercase — a capitalised canonical ("Nārada") with
        # "query: " prefix hits a dead zone in e5-small's embedding space (0 hits;
        # proven live). Lowercase before building the head so the vector lands in
        # the same neighbourhood regardless of LLM capitalisation drift.
        _canon_lc = self.canonical.lower() if self.canonical else ""
        if _canon_lc and gloss:
            head = f"{_canon_lc}. {gloss}"
        else:
            head = _canon_lc or gloss
        syn = ", ".join(self.synonyms[:4])
        return f"{head}. Related: {syn}" if syn else head

    @property
    def fts_phrase(self) -> str:
        """
        Multi-term OR phrase for Postgres FTS websearch_to_tsquery.
        Uses literal ' OR ' (websearch_to_tsquery does not parse '|').
        Built from the diacritic-stripped IAST terms so it matches the corpus's
        ASCII FTS tokens; falls back to the raw query when no expansion happened.
        """
        terms = [_normalize_iast(t) for t in self._iast_terms]
        terms = [t for t in dict.fromkeys(terms) if t]
        return " OR ".join(terms) if terms else self.original

    @property
    def gretil_search_terms(self) -> list[str]:
        """All terms to search GRETIL with, in priority order (+ Devanagari)."""
        terms = [self.canonical]
        if self.devanagari:
            terms.append(self.devanagari)
        terms.extend(self.synonyms[:2])
        return [t for t in dict.fromkeys(terms) if t]

    @property
    def devanagari_embed_phrase(self) -> str | None:
        """Secondary embedding phrase for bi-directional Sanskrit retrieval.

        The primary embed_phrase leads with the IAST canonical term, which shifts
        the vector toward the ASCII-IAST corpus and away from Devanagari-embedded
        texts (YV was re-embedded from Devanagari). The secondary uses the plain
        English gloss — no IAST prefix — which e5-small aligns more naturally with
        Devanagari-embedded Sanskrit. Verified live: plain-EN gloss → YV=4/8;
        IAST-led embed_phrase → YV=0/8 for advaita queries.

        Returns None for non-conceptual / trivial queries.
        """
        if not self.is_sanskrit:
            return None
        return self.english_gloss or None


# ── LLM prompt ────────────────────────────────────────────────────────────

_CROSSLINGUAL_PROMPT = """\
You are a Sanskrit / Vedic-philosophy expert and a multilingual translator. A seeker \
typed this search query. It may be in ANY language (English, Hindi, Russian, Sanskrit, \
etc.) and ANY script (Latin, Devanagari, Cyrillic):

"{query}"

The corpus being searched is Hindu scripture (Vedas, Upanishads, Puranas, Bhagavad Gita, \
Mahabharata, Yoga texts) stored in IAST-romanized Sanskrit. Map the seeker's query — \
whatever its language — onto the canonical Sanskrit concepts that appear in those texts, \
so the search lands in the right place.

Respond with ONLY valid JSON, no extra text:
{{
  "is_conceptual": true,
  "canonical_iast": "the single most central Sanskrit concept in IAST (e.g. ātman, dharma, mṛtyu)",
  "synonyms": ["up to 4 related Sanskrit terms or epithets in IAST, most relevant first"],
  "english_gloss": "the seeker's actual question, stated plainly in ENGLISH, max 18 words",
  "devanagari": "the canonical concept in Devanagari",
  "graph_terms": ["English or Sanskrit entity names for knowledge graph lookup"]
}}

If the query is a greeting, chit-chat, or has no retrievable scriptural concept, set \
is_conceptual:false:
{{ "is_conceptual": false, "canonical_iast": "", "synonyms": [], "english_gloss": "", "devanagari": "", "graph_terms": [] }}

Rules:
- Translate the MEANING, not the words. Examples:
  "what happens to the soul after death" -> canonical_iast: ātman, synonyms: [mṛtyu, punarjanma, jīva], graph_terms: [Atman, Soul, Death, Rebirth, Jiva]
  "природа дхармы и долга" -> canonical_iast: dharma, synonyms: [kartavya, svadharma], graph_terms: [Dharma, Duty]
  "how to still the mind" -> canonical_iast: citta-vṛtti-nirodha, synonyms: [dhyāna, samādhi, manas], graph_terms: [Citta, Manas, Mind, Dhyana, Samadhi, Yoga]
  "what are the layers of the mind" -> canonical_iast: manas, synonyms: [buddhi, mahat, puruṣa, ātman], graph_terms: [Manas, Buddhi, Mahat, Purusa, Atman, Brahman, Mind, Intellect, Consciousness]
  "how do the three gunas affect consciousness" -> canonical_iast: guṇa, synonyms: [sattva, rajas, tamas], graph_terms: [Sattva, Rajas, Tamas, Guna, Consciousness, Mind]
- graph_terms: Up to 8 English/Sanskrit entity names the knowledge graph can activate. Include ALL related concepts, not just the single canonical one. Use PascalCase for Sanskrit entity names (Manas, Buddhi, Atman) and English for concept names (Mind, Consciousness, Time). The graph has entities for Manas, Buddhi, Mahat, Purusa, Purusha, Atman, Brahman, Jiva, Sattva, Rajas, Tamas, Yoga, Kriya, Dhyana, Samadhi, Vairagya, Granthi, Prakriti, Ahamkara, Chitta — when the query touches mind/consciousness, include the relevant ones.
- canonical_iast and synonyms: proper IAST diacritics (ā ī ū ṛ ṝ ṃ ṅ ñ ṭ ḍ ṇ ś ṣ ḥ), Sanskrit only.
- english_gloss: a clear English restatement — the cross-lingual anchor, always fill for conceptual queries.
"""


# ── SanskritQueryProcessor ────────────────────────────────────────────────

class SanskritQueryProcessor:
    """
    Entry point for query understanding. Call `expand(query)` before search.

    Decision tree:
      1. Trivial (greeting / all stop-words)  → passthrough, no LLM (fast).
      2. Devanagari script                    → transliterate to IAST, then x-lingual expand.
      3. Everything else (English, Cyrillic,  → cross-lingual concept extraction (LLM).
         romanized Sanskrit, …)
    """

    def __init__(self, llm_caller):
        """llm_caller: async (messages, temperature=, req_model=) -> str."""
        self._call_llm = llm_caller

    # ---- detected_lang hinting (cheap, script-based) -----------------------
    @staticmethod
    def _hint_lang(query: str) -> str:
        if _is_devanagari(query):
            return "Devanagari"
        if not _is_latin(query):
            return "Other"
        if _is_likely_sanskrit(query):
            return "Sanskrit (Roman)"
        return "English"

    _expand_cache: dict = {}
    _EXPAND_CACHE_MAX = 256
    _EXPAND_CACHE_TTL = 600
    async def expand(self, query: str) -> QueryExpansion:
        """Main entry point. Returns a QueryExpansion for any query. Never raises."""
        query = query.strip()
        import time as _time
        cache_key = query.lower()[:120]
        cached = self._expand_cache.get(cache_key)
        if cached and (_time.time() - cached[0]) < self._EXPAND_CACHE_TTL:
            return cached[1]

        if not query or _is_trivial(query):
            return QueryExpansion(
                original=query, detected_lang=self._hint_lang(query),
                is_sanskrit=False, canonical=query,
                engagement=_resolve_engagement(query),
            )

        if _is_devanagari(query):
            return await self._expand_devanagari(query)

        # English / Cyrillic / romanized Sanskrit / anything else.
        return await self._expand_crosslingual(query, detected_lang=self._hint_lang(query))

    async def expand_with_history(self, query: str, history_str: str) -> QueryExpansion:
        """
        Merge follow-up rewriting (resolve "and then?" against history) with
        cross-lingual concept extraction in ONE LLM call. Bypasses cache (the
        history makes the context unique).
        """
        prompt = f"""You are a Sanskrit / Vedic-philosophy expert and multilingual translator.
Conversation history:
{history_str}

The seeker's follow-up query is: "{query}"

Step 1: Rewrite the follow-up to be self-contained, using the history (keep its language).
Step 2: Map the REWRITTEN query's meaning onto canonical Sanskrit concepts in the
IAST-romanized scripture corpus, regardless of the query's language/script.

Respond with ONLY valid JSON, no extra text:
{{{{
  "rewritten_query": "the self-contained version of the query",
  "is_conceptual": true,
  "canonical_iast": "the central Sanskrit concept in IAST",
  "synonyms": ["related IAST terms, most relevant first"],
  "english_gloss": "the question stated plainly in English, max 18 words",
  "devanagari": "the canonical concept in Devanagari",
  "graph_terms": ["entity names for knowledge graph lookup"]
}}}}

If the rewritten query is a greeting / chit-chat / has no scriptural concept, set
is_conceptual:false:
{{{{ "rewritten_query": "...", "is_conceptual": false, "canonical_iast": "", "synonyms": [], "english_gloss": "", "devanagari": "", "graph_terms": [] }}}}

Rules: translate MEANING not words; proper IAST diacritics; always fill english_gloss for a conceptual query. Include graph_terms as entity names (PascalCase for Sanskrit, English for concepts) — list ALL related entities the knowledge graph should activate, not just the canonical one. Mind/consciousness queries should include Manas, Buddhi, Mahat, Purusa, Atman, Brahman where relevant.
"""
        try:
            resp = await asyncio.wait_for(
                self._call_llm([{"role": "user", "content": prompt}], temperature=0.0, req_model="auto"),
                timeout=EXPANSION_TIMEOUT_S,
            )
            data = self._parse_json(resp)
            if data is not None:
                rewritten = (data.get("rewritten_query") or query).strip()
                if not data.get("is_conceptual", data.get("is_sanskrit", False)):
                    return QueryExpansion(
                        original=rewritten, detected_lang=self._hint_lang(rewritten),
                        is_sanskrit=False, canonical=rewritten,
                        engagement=_resolve_engagement(rewritten), mood="warm",
                    )
                return self._build_expansion(rewritten, data, detected_lang=self._hint_lang(rewritten))
        except asyncio.TimeoutError:
            logger.warning("rewrite+expansion timed out (>%ss) for %r", EXPANSION_TIMEOUT_S, query)
        except Exception as e:
            logger.error("Combined rewrite+expansion failed: %s", e)

        # Fallback: plain cross-lingual expansion of the raw follow-up.
        return await self.expand(query)

    # ---- internals ---------------------------------------------------------

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        """Tolerant JSON extraction (strips code fences, <think> tags, prose)."""
        try:
            raw = re.sub(r"```(?:json)?", "", raw)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            return json.loads(m.group(0)) if m else None
        except (json.JSONDecodeError, AttributeError, TypeError):
            return None

    def _build_expansion(self, original: str, data: dict, detected_lang: str) -> QueryExpansion:
        canonical = (data.get("canonical_iast") or "").strip() or _normalize_iast(original)
        synonyms = [s.strip() for s in (data.get("synonyms") or []) if s and s.strip()][:4]
        gloss = (data.get("english_gloss") or "").strip()
        deva = (data.get("devanagari") or "").strip() or _to_devanagari(canonical)
        graph_terms = [t.strip() for t in (data.get("graph_terms") or []) if t and t.strip()][:8]
        return QueryExpansion(
            original=original, detected_lang=detected_lang, is_sanskrit=True,
            canonical=canonical, synonyms=synonyms, english_gloss=gloss, devanagari=deva,
            engagement=_resolve_engagement(original), mood="warm", graph_terms=graph_terms,
        )

    async def _expand_crosslingual(self, query: str, detected_lang: str) -> QueryExpansion:
        """One LLM call mapping any-language query → canonical Sanskrit concepts."""
        cache_key = f"expansion:{CACHE_VERSION}:{query.lower().strip()}"

        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    d = json.loads(cached)
                    return QueryExpansion(
                        original=query,
                        detected_lang=d.get("detected_lang", detected_lang),
                        is_sanskrit=d.get("is_sanskrit", False),
                        canonical=d.get("canonical", query),
                        synonyms=d.get("synonyms", []),
                        english_gloss=d.get("english_gloss", ""),
                        devanagari=d.get("devanagari", ""),
                        graph_terms=d.get("graph_terms", []),
                        engagement=_resolve_engagement(query), mood="warm",
                    )
            except Exception as e:
                logger.warning("Redis cache read failed for %r: %s", query, e)

        prompt = _CROSSLINGUAL_PROMPT.format(query=query)
        try:
            raw = await asyncio.wait_for(
                self._call_llm([{"role": "user", "content": prompt}], temperature=0.0, req_model="auto"),
                timeout=EXPANSION_TIMEOUT_S,
            )
            data = self._parse_json(raw)
            if data is None:
                raise json.JSONDecodeError("no json", raw or "", 0)

            if not data.get("is_conceptual", data.get("is_sanskrit", False)):
                exp = QueryExpansion(
                    original=query, detected_lang=detected_lang,
                    is_sanskrit=False, canonical=query,
                    engagement=_resolve_engagement(query), mood="warm",
                )
            else:
                exp = self._build_expansion(query, data, detected_lang)

            logger.info("x-lingual expansion: %r (%s) → canonical=%r synonyms=%r",
                        query, detected_lang, exp.canonical, exp.synonyms)

            if redis_client:
                try:
                    await redis_client.setex(cache_key, CACHE_TTL, json.dumps({
                        "detected_lang": exp.detected_lang,
                        "is_sanskrit": exp.is_sanskrit,
                        "canonical": exp.canonical,
                        "synonyms": exp.synonyms,
                        "english_gloss": exp.english_gloss,
                        "devanagari": exp.devanagari,
                        "graph_terms": getattr(exp, "graph_terms", []),
                    }))
                except Exception as e:
                    logger.warning("Redis cache write failed for %r: %s", query, e)
            return exp

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("x-lingual expansion JSON parse failed for %r: %s", query, e)
        except asyncio.TimeoutError:
            logger.warning("x-lingual expansion timed out (>%ss) for %r — passthrough", EXPANSION_TIMEOUT_S, query)
        except Exception as e:
            logger.warning("x-lingual expansion failed for %r: %s", query, e)

        # Graceful fallback: passthrough (raw query embed). Default to "full" so
        # we never skip RAG on a transient LLM failure — better to over-retrieve
        # than to wrongly redirect a genuine seeker.
        return QueryExpansion(
            original=query, detected_lang=detected_lang,
            is_sanskrit=False, canonical=_normalize_iast(query) if _is_latin(query) else query,
            engagement="full",
        )

    async def _expand_devanagari(self, query: str) -> QueryExpansion:
        """Devanagari input: transliterate to IAST, then cross-lingual expand."""
        iast_form = ""
        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            iast_form = transliterate(query, sanscript.DEVANAGARI, sanscript.IAST)
        except Exception:
            pass

        if iast_form:
            expansion = await self._expand_crosslingual(iast_form, detected_lang="Devanagari")
            expansion.original = query
            expansion.detected_lang = "Devanagari"
            if not expansion.devanagari:
                expansion.devanagari = query
            return expansion

        return QueryExpansion(
            original=query, detected_lang="Devanagari",
            is_sanskrit=True, canonical=query, devanagari=query,
        )
