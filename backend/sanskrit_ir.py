"""
Sanskrit IR — Intermediate Representation for PuranGPT queries.

English enters the frontend. The backend compiles it to a formal Sanskrit
instruction block (the IR) which acts as a semantic "coding language":
precise, unambiguous, and directly mappable to executable operations via
the same 384-dim multilingual-e5-small embeddings that index the corpus.

Architecture:
  English query → LLM compiler → Sanskrit IR (structured block)
  Sanskrit IR → embedding match → operation dispatch
  Operation → RAG / reasoning / citation pipeline → English response

The user never sees Sanskrit. It is the machine's internal representation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger("purangpt.sanskrit_ir")

# ── Sanskrit Operation Codes (क्रिया) ────────────────────────────────────
# Each operation has:
#   code       — the Sanskrit imperative/verbal noun used in the IR
#   english    — human-readable label
#   embedding  — reference description for semantic matching (embedded at
#                module load by the active embedding model)
#   weight     — default semantic weight for hybrid search when this op
#                is active (higher = more vector, lower = more keyword)

@dataclass
class SanskritOp:
    code: str
    english: str
    description: str
    default_weight: float = 0.5

# The क्रिया catalogue. Ordered by priority — the first match wins when
# the compiler is ambiguous.
KRITYA: List[SanskritOp] = [
    SanskritOp("अन्वेषणम्",  "search",      "semantic vector search across the Puranic corpus for factual retrieval", 0.55),
    SanskritOp("प्रमाणय",   "cite",         "retrieve exact verses with chapter-verse citations and source metadata", 0.40),
    SanskritOp("तर्कय",     "reason",       "chain-of-thought reasoning through a multi-step logical argument", 0.70),
    SanskritOp("सारं कुरु",  "summarize",   "condense a large retrieved context into a brief synthesis", 0.50),
    SanskritOp("भाष्य",      "commentary",  "deep expository analysis drawing on traditional commentary lineages", 0.45),
    SanskritOp("प्रश्नः",    "question",    "direct conversational answer — the default when no specialised op fires", 0.50),
    SanskritOp("सन्देहः",    "doubt",       "the seeker is uncertain or confused — clarify and reassure before answering", 0.50),
    SanskritOp("उपदेशः",     "counsel",     "practical spiritual guidance in Guruji's voice, grounded in lived tradition", 0.40),
    SanskritOp("ध्यानम्",    "meditation",  "guided contemplative instruction — a short practice, not an explanation", 0.35),
]

# ── Compiler Prompt ──────────────────────────────────────────────────────
# Compact prompt that asks the LLM to output ONLY the Sanskrit IR block.
# The LLM is instructed to be terse and structural — this is a compiler,
# not a conversational response.

COMPILER_SYSTEM = """You are a Sanskrit-to-Operation compiler. Your ONLY job is to translate an English query into a structured Sanskrit instruction block.

Output EXACTLY this format — nothing else, no preamble, no explanation:

```
क्रिया: <one operation from the list below>
विषयः: <core topic in 2-5 English words>
बलम्: <0.0 to 1.0 — how strongly this operation matches, where 1.0 is a perfect fit>
भाषा: <original query language: en|hi|sa|ru|fr>
```

Available operations (क्रिया):
- अन्वेषणम् — factual search: the seeker wants information, facts, verses, sources
- प्रमाणय — citation: the seeker explicitly wants exact verse references and citations
- तर्कय — reasoning: the query requires logical chain-of-thought or multi-step analysis
- सारं कुरु — summarise: condense a large topic into a brief overview
- भाष्य — commentary: deep expository analysis, traditional interpretation
- प्रश्नः — question: a direct, conversational question (default)
- सन्देहः — doubt: the seeker is confused or uncertain and needs clarification
- उपदेशः — counsel: practical spiritual or life guidance in a warm voice
- ध्यानम् — meditation: a guided contemplative practice or instruction

Pick the SINGLE best क्रिया. If multiple fit, choose the most specific one.
बलम् should reflect confidence — 0.9+ for obvious matches, 0.5 for ambiguous ones."""

COMPILER_USER = """English query: {query}

Sanskrit IR:"""


def parse_sanskrit_ir(raw: str) -> Dict[str, str]:
    """Parse a Sanskrit IR block into a dict of {field: value}."""
    ir: Dict[str, str] = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("```"):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value:
                ir[key] = value
    return ir


def match_operation(kriya_field: str) -> Tuple[SanskritOp, float]:
    """Match a क्रिया field value to the closest SanskritOp.

    Returns (best_match, confidence). If no match found, returns (प्रश्नः, 0.3).
    """
    kriya_clean = kriya_field.strip().lower()

    # Exact match first
    for op in KRITYA:
        if op.code.strip().lower() == kriya_clean:
            return (op, 1.0)

    # Substring match
    for op in KRITYA:
        if op.code.strip().lower() in kriya_clean or kriya_clean in op.code.strip().lower():
            return (op, 0.7)

    # Default
    default = KRITYA[5]  # प्रश्नः
    return (default, 0.3)


def compile_query(query: str, language: str = "en") -> Dict:
    """Compile an English query into a Sanskrit IR — lightweight, no LLM call.

    This is the fast-path heuristic compiler. It uses keyword signals
    to route to the correct operation without an extra LLM round-trip.
    For full semantic compilation, use compile_query_llm().

    Returns {"op": SanskritOp, "topic": str, "confidence": float, "language": str}
    """
    q = query.lower()

    # Citation signals → प्रमाणय
    cite_signals = ["cite", "citation", "reference", "verse", "source",
                    "what exactly does", "according to", "exact words",
                    "which verse", "where in the", "chapter and verse"]
    if any(s in q for s in cite_signals):
        op = KRITYA[1]  # प्रमाणय
        return {"op": op, "topic": _extract_topic(query), "confidence": 0.85, "language": language}

    # Reasoning signals → तर्कय
    reason_signals = ["why", "how does", "explain the logic", "reason",
                      "what is the relationship", "compare", "contrast",
                      "if .* then", "cause", "effect"]
    if any(s in q for s in reason_signals) or (len(query.split()) > 25):
        op = KRITYA[2]  # तर्कय
        confidence = 0.75 if len(query.split()) > 25 else 0.65
        return {"op": op, "topic": _extract_topic(query), "confidence": confidence, "language": language}

    # Doubt/confusion signals → सन्देहः
    doubt_signals = ["confused", "don't understand", "doesn't make sense",
                     "contradiction", "how can", "why would", "i'm not sure"]
    if any(s in q for s in doubt_signals):
        op = KRITYA[6]  # सन्देहः
        return {"op": op, "topic": _extract_topic(query), "confidence": 0.80, "language": language}

    # Guidance/counsel signals → उपदेशः
    counsel_signals = ["should i", "what should", "how to live", "advice",
                       "guidance", "help me", "struggling", "path", "sadhana"]
    if any(s in q for s in counsel_signals):
        op = KRITYA[7]  # उपदेशः
        return {"op": op, "topic": _extract_topic(query), "confidence": 0.78, "language": language}

    # Meditation signals → ध्यानम्
    meditate_signals = ["meditation", "meditate", "practice", "breathe",
                        "mantra", "japa", "contemplat", "silence", "inner"]
    if any(s in q for s in meditate_signals):
        op = KRITYA[8]  # ध्यानम्
        return {"op": op, "topic": _extract_topic(query), "confidence": 0.80, "language": language}

    # Summarise signals → सारं कुरु
    summary_signals = ["summary", "summarise", "summarize", "overview",
                       "tldr", "brief", "in short", "quick"]
    if any(s in q for s in summary_signals):
        op = KRITYA[3]  # सारं कुरु
        return {"op": op, "topic": _extract_topic(query), "confidence": 0.82, "language": language}

    # Deep analysis signals → भाष्य
    commentary_signals = ["commentary", "analysis", "deep dive", "explain in detail",
                          "traditional interpretation", "what does .* mean",
                          "significance of", "symbolism"]
    if any(s in q for s in commentary_signals):
        op = KRITYA[4]  # भाष्य
        return {"op": op, "topic": _extract_topic(query), "confidence": 0.70, "language": language}

    # Default: search → अन्वेषणम् (for factual queries with clear topic)
    # or question → प्रश्नः (for conversational)
    if len(query.split()) <= 8:
        op = KRITYA[5]  # प्रश्नः — short, conversational
    else:
        op = KRITYA[0]  # अन्वेषणम् — longer, likely factual

    return {"op": op, "topic": _extract_topic(query), "confidence": 0.55, "language": language}


def _extract_topic(query: str, max_words: int = 5) -> str:
    """Extract a brief topic phrase from the query."""
    # Remove common question words
    cleaned = re.sub(r'\b(what|who|where|when|why|how|is|are|was|were|do|does|did|can|could|would|should|tell me|explain|describe|please|help)\b', '', query, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    words = cleaned.split()[:max_words]
    return ' '.join(words) if words else query.split()[0]


async def compile_query_llm(query: str, language: str = "en") -> Dict:
    """Full semantic compilation using the LLM.

    Sends the query to the LLM with the COMPILER_SYSTEM prompt, gets back
    a Sanskrit IR block, parses it, and matches to an operation.

    This is more accurate than the heuristic compiler for ambiguous queries
    but adds ~0.5-1s latency for the extra LLM call.
    """
    from backend.main import stream_one_provider, get_providers

    messages = [
        {"role": "system", "content": COMPILER_SYSTEM},
        {"role": "user", "content": COMPILER_USER.format(query=query)},
    ]

    raw_ir = ""
    providers = get_providers()
    if not providers:
        # Fall back to heuristic if no LLM available
        logger.warning("No LLM available for Sanskrit IR compilation — using heuristic")
        return compile_query(query, language)

    try:
        async for chunk in stream_one_provider(
            providers[0],
            messages,
            temperature=0.1,  # very cold — we want structural output
            max_tokens=120,    # the IR block is small
        ):
            if "choices" in chunk:
                delta = chunk["choices"][0].get("delta", {})
                raw_ir += delta.get("content", "")
    except Exception as e:
        logger.warning(f"LLM Sanskrit IR compilation failed: {e} — falling back to heuristic")
        return compile_query(query, language)

    # Parse the IR
    ir = parse_sanskrit_ir(raw_ir)
    kriya = ir.get("क्रिया", "").strip()

    if not kriya:
        logger.info("LLM did not return valid क्रिया — falling back to heuristic")
        return compile_query(query, language)

    op, confidence = match_operation(kriya)
    topic = ir.get("विषयः", _extract_topic(query))
    llm_confidence = float(ir.get("बलम्", confidence))

    logger.info(
        f"Sanskrit IR compiled: क्रिया={op.code} ({op.english}) "
        f"confidence={llm_confidence:.2f} topic='{topic}'"
    )

    return {
        "op": op,
        "topic": topic,
        "confidence": llm_confidence,
        "language": ir.get("भाषा", language),
        "raw_ir": raw_ir.strip(),
    }


def get_semantic_weight(op: SanskritOp, ir_confidence: float) -> float:
    """Compute the semantic (vector) weight for hybrid search based on the
    Sanskrit IR operation. Higher weight = more vector similarity, lower =
    more keyword/BM25 matching."""
    base = op.default_weight
    # Boost vector weight when the compiler is confident
    adjusted = base + (ir_confidence - 0.5) * 0.3
    return max(0.15, min(0.85, adjusted))


# ── Embedding-based operation matching (for use with multilingual-e5-small) ──

# Pre-computed embeddings for each operation's description — populated at
# module load if an embedding model is available. Otherwise, match_operation()
# does string-based matching as a fallback.
_op_embeddings: Optional[Dict[str, List[float]]] = None


def _load_op_embeddings():
    """Load embeddings for Sanskrit operation descriptions.

    Tries to use the same sentence-transformers model that powers
    the HybridSearcher. If unavailable, string matching is the fallback.
    """
    global _op_embeddings
    if _op_embeddings is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("intfloat/multilingual-e5-small")
        _op_embeddings = {}
        for op in KRITYA:
            # E5 expects "query: " prefix for asymmetric embeddings
            emb = model.encode(f"query: {op.description}", normalize_embeddings=True)
            _op_embeddings[op.code] = emb.tolist()
        logger.info(f"Loaded {len(_op_embeddings)} Sanskrit IR operation embeddings")
    except Exception as e:
        logger.warning(f"Could not load op embeddings: {e} — string matching fallback active")
        _op_embeddings = {}


def embed_match(query: str) -> Tuple[SanskritOp, float]:
    """Match a query to the closest SanskritOp using embedding similarity.

    Falls back to string-based match_operation() if embeddings aren't loaded.
    """
    if _op_embeddings is None:
        try:
            _load_op_embeddings()
        except Exception:
            pass

    if _op_embeddings is None:
        return match_operation(query)

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("intfloat/multilingual-e5-small")
        q_emb = model.encode(f"query: {query}", normalize_embeddings=True)

        best_op = KRITYA[5]  # default प्रश्नः
        best_score = -1.0

        for op in KRITYA:
            op_emb = np.array(_op_embeddings[op.code])
            score = float(np.dot(q_emb, op_emb))
            if score > best_score:
                best_score = score
                best_op = op

        return (best_op, best_score)
    except Exception as e:
        logger.warning(f"Embedding match failed: {e}")
        return match_operation(query)
