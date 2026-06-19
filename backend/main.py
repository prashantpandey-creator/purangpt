"""
PuranGPT — Production Backend v2
=================================
New in v2:
  - Conversation memory (per-session history)
  - Deep Research mode (multi-step chain-of-thought)
  - Sanskrit full-text search across GRETIL corpus
  - Source transparency (language, edition, bias rating)
  - Expanded text catalog (Nath tradition, Darshanas, Yoga Vasistha)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import asyncio
import sys
import time
import unicodedata
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from typing import Union

import contextvars

# Context variable for Bring-Your-Own-Key
custom_keys_var = contextvars.ContextVar('custom_keys', default={})

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("purangpt.backend")

# ── Config ─────────────────────────────────────────────────────────────────
LLM_PROVIDER  = os.getenv("LLM_PROVIDER", "groq")
GEMINI_API_KEY= os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL  = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL",   "llama-3.3-70b-versatile")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
ZHIPU_API_KEY    = os.getenv("ZHIPU_API_KEY", "")
INDEX_DIR     = os.getenv("INDEX_DIR",   "./data/indexes")
INDEX_URL     = os.getenv("INDEX_URL",   "https://purangpt.s3.us-east-1.amazonaws.com/purangpt-indexes-v2.tar.gz")
GRETIL_DIR    = Path("./data/raw_texts/gretil")
FRONTEND_DIR  = Path(__file__).parent.parent / "frontend"
MAX_HISTORY   = 100  # messages kept in session memory


from backend.auth import get_current_user, require_auth, require_role, get_guest_id, check_guest_rate_limit, increment_guest_usage, validate_query
from backend.db_client import update_profile, get_admin_stats, get_all_users, encrypt_keys, decrypt_keys, increment_usage, check_rate_limit, check_research_limit, increment_research_usage

from backend.session_manager import SessionManager
from backend.monitor import run_health_checks

# ── Session Memory ─────────────────────────────────────────────────────────
session_manager = SessionManager(MAX_HISTORY)

# ── Source Catalog (language + edition metadata) ───────────────────────────
SOURCE_META: Dict[str, dict] = {
    "agni":           {"lang": "Sanskrit", "edition": "Bibliotheca Indica (BI)", "tradition": "mixed",   "bias": "✅ neutral"},
    "bhagavata":      {"lang": "Sanskrit", "edition": "Critical edition (GRETIL)", "tradition": "vaishnava","bias": "⚠️ Vaishnava"},
    "brahma":         {"lang": "Sanskrit", "edition": "Anandasrama Sanskrit Series", "tradition": "mixed",   "bias": "✅ mostly neutral"},
    "brahmanda":      {"lang": "Sanskrit", "edition": "Sansknet / GRETIL",         "tradition": "mixed",   "bias": "✅ neutral"},
    "garuda":         {"lang": "Sanskrit", "edition": "Sansknet / GRETIL",         "tradition": "vaishnava","bias": "⚠️ Vaishnava"},
    "kurma":          {"lang": "Sanskrit", "edition": "All-India Kashiraj Trust",  "tradition": "shaiva-vaishnava","bias": "✅ syncretic"},
    "linga_1":        {"lang": "Sanskrit", "edition": "Venkatesvara Press 1906",   "tradition": "shaiva",  "bias": "✅ Shaiva"},
    "markandeya":     {"lang": "Sanskrit", "edition": "Bibliotheca Indica",        "tradition": "shakta",  "bias": "✅ most stable"},
    "matsya":         {"lang": "Sanskrit", "edition": "Oliver Hellwig / GRETIL",   "tradition": "mixed",   "bias": "✅ neutral"},
    "narada":         {"lang": "Sanskrit", "edition": "Sansknet / GRETIL",         "tradition": "vaishnava","bias": "⚠️ strong Vaishnava"},
    "shiva_1_7":      {"lang": "Sanskrit", "edition": "Jun Takashima / GRETIL",    "tradition": "shaiva",  "bias": "✅ Shaiva"},
    "vamana":         {"lang": "Sanskrit", "edition": "Sansknet / GRETIL",         "tradition": "vaishnava","bias": "⚠️ Vaishnava"},
    "vishnu_critical":{"lang": "Sanskrit", "edition": "Peter Schreiner critical",  "tradition": "vaishnava","bias": "⚠️ Vaishnava (best critical)"},
    "yoga_vasistha":  {"lang": "Sanskrit", "edition": "GRETIL / Nirnaya Sagar",    "tradition": "advaita", "bias": "✅ non-sectarian"},
    "gorakshashataka":{"lang": "Sanskrit", "edition": "GRETIL",                    "tradition": "nath",    "bias": "✅ Nath tradition"},
    "samkhya_karika": {"lang": "Sanskrit", "edition": "GRETIL",                    "tradition": "darshana","bias": "✅ pre-sectarian"},
    "yoga_sutras":    {"lang": "Sanskrit", "edition": "GRETIL",                    "tradition": "darshana","bias": "✅ pre-sectarian"},
    "bhagavad_gita":  {"lang": "Sanskrit", "edition": "BORI Critical (1966-73)",   "tradition": "mixed",   "bias": "✅ most critical edition"},
}

# ── Prompts ────────────────────────────────────────────────────────────────
KNOWN_INTERPOLATIONS = """
⚠️ KNOWN CONTESTED PASSAGES (always flag these explicitly):
• Padma Purana Uttara Khanda — "Shiva admitting" he spread false philosophies → universally identified as late Vaishnava insertion (Rocher 1986, Doniger 2009)
• Bhagavata 1.1.1 — claim of supremacy over all Puranas → self-promotional late addition
• Brahma Purana passages demoting Shiva → Hazra (1940) identifies as sectarian redactions
• Skanda Purana tirtha-mahatmyas → locally inserted by temple traditions, vary across manuscripts
"""

GUARDRAIL_INSTRUCTION = """
## BEHAVIORAL GUARDRAILS
1. **Troll/Disrespectful Prompts**: If the user's input is a troll question, disrespectful, profane, or completely irrelevant to Vedic/Puranic/spiritual topics, you must REPRIMAND them firmly but calmly for disrespecting the sacred texts and this space. Do not attempt to answer the troll question.
2. **Unclear Questions**: If the user's question is very broad or unclear, answer it to the best of your ability using the retrieved passages, then gently invite them to refine their question for a deeper dive.
"""

RESEARCH_SYSTEM = """You are PuranGPT — a critical Puranic scholar conducting deep comparative analysis across the sacred texts.

## MANDATORY RESPONSE STRUCTURE — follow this order strictly:

### 📋 Summary
Provide a clear, concise summary derived directly from the extracted text in 3–5 sentences. State the core answer immediately.

### 📖 Extracted Sacred Texts
Extract the most highly relevant verses and texts from the provided context.
Format them beautifully in isolated paragraphs.
- You MUST quote the original Sanskrit or Hindi where available.
- You MUST provide the direct English translation.
- You MUST include inline citations matching the source index (e.g., [1], [2]) directly after each quoted text block.

### 💡 Explanation & Synthesis
After quoting the texts, provide a detailed and thoughtful explanation of their meaning.
Break down the complex philosophical or theological concepts into understandable terms, showing how the cited verses answer the user's query.

**Keep responses highly organized, elegant, and always use inline citations like [1] when referencing the extracted texts.**
- If a retrieved text chunk appears corrupted or like a random string of characters (OCR errors), silently IGNORE it entirely; do not mention it or create a section/warning for it.

{interpolations}

{language_instruction}

## Retrieved Source Passages
The passages below are indexed as [1], [2], [3], etc. You MUST use these exact bracketed numbers for inline citations.

{context}

{history}
""" + "\n" + GUARDRAIL_INSTRUCTION


GUIDE_SYSTEM = """You are PuranGPT in GUIDE MODE. You are a wise, compassionate spiritual mentor drawing upon Vedic knowledge, the Puranas, the Bhagavad Gita, and the specific yogic commentaries of Guruji Sri Shailendra Sharma.

Your goal is to provide profound life lessons, spiritual advice, and comforting wisdom to individuals seeking guidance.

## Response Guidelines
1. **Natural Flow**: Do not strictly follow a rigid structure. Let your response flow naturally and loosely.
2. **Concise & Impactful**: Your answers should be extremely concise, profound, and impactful, much like Guruji's direct way of speaking. Aim for a single, powerful paragraph whenever possible.
3. **Tone**: Warm, empathetic, profound, and non-judgmental. Speak directly to the seeker's soul without academic lecturing.
4. **Citations**: Do not clutter the text with numbers or citations. Weave references into your natural speech loosely (e.g., "The Gita teaches us...").
5. **Format**: Avoid bullet points, headers, and heavy formatting. Speak naturally.

{interpolations}

{language_instruction}

## Relevant Wisdom Passages
{context}

{history}
""" + "\n" + GUARDRAIL_INSTRUCTION


PROMPTS = {
    "research": RESEARCH_SYSTEM,
    "guide":    GUIDE_SYSTEM,
}


# ── App State ──────────────────────────────────────────────────────────────
class AppState:
    searcher: Any = None
    index_ready: bool = False
    total_verses: int = 0
    gretil_loaded: bool = False
    gretil_corpus: Dict[str, str] = {}   # text_id → full text
    total_gretil_chars: int = 0
    active_provider: str = "unknown"     # set at startup after key validation
    active_model: str = ""
    http_client: aiohttp.ClientSession = None

state = AppState()


# ── GRETIL Corpus Loader ───────────────────────────────────────────────────
def load_gretil_corpus():
    """Load all GRETIL plain-text files into memory for Sanskrit search."""
    if not GRETIL_DIR.exists():
        return
    count = 0
    for text_dir in sorted(GRETIL_DIR.iterdir()):
        if not text_dir.is_dir():
            continue
        for txt_file in text_dir.glob("*.txt"):
            text_id = text_dir.name
            try:
                content = txt_file.read_text(encoding="utf-8", errors="replace")
                state.gretil_corpus[text_id] = content
                state.total_gretil_chars += len(content)
                count += 1
            except Exception as e:
                logger.warning("Failed to load %s: %s", txt_file, e)
    state.gretil_loaded = count > 0
    logger.info("✓ GRETIL corpus: %d texts, %d chars total", count, state.total_gretil_chars)


# ── Sanskrit Search ────────────────────────────────────────────────────────
def search_sanskrit(query: str, max_results: int = 20, text_ids: Optional[List[str]] = None) -> List[dict]:
    """
    Full-text search through the GRETIL Sanskrit corpus.
    Handles Devanagari, exact IAST, and diacritic-stripped (normalized) matches.
    Returns list of matching excerpts with 6-line context window.
    """
    if not state.gretil_corpus:
        return []

    results       : List[dict] = []
    seen_keys     : set        = set()          # (text_id, line_num) dedup
    query_str     = query.strip()
    query_deva    = is_devanagari(query_str)
    query_lower   = query_str.lower()
    query_normed  = normalize_iast(query_str)   # diacritic-stripped ASCII

    corpus = state.gretil_corpus
    if text_ids:
        corpus = {k: v for k, v in corpus.items() if k in text_ids}

    for text_id, full_text in corpus.items():
        lines       = full_text.splitlines()
        source_meta = SOURCE_META.get(text_id, {})
        name        = source_meta.get("name", text_id.replace("_", " ").title())

        for i, line in enumerate(lines):
            if not line.strip():
                continue

            # Three-level matching: Devanagari exact → IAST exact → IAST normalized
            if query_deva:
                matched = query_str in line
            else:
                matched = (
                    query_lower   in line.lower()
                    or query_normed in normalize_iast(line)
                )

            if not matched:
                continue

            key = (text_id, i)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Wider context window: 5 lines before, 5 after
            start         = max(0, i - 5)
            end           = min(len(lines), i + 6)
            context_lines = lines[start:end]
            context       = "\n".join(l for l in context_lines if l.strip())
            ref           = extract_reference(lines, i)

            results.append({
                "text_id":      text_id,
                "text_name":    name,
                "language":     source_meta.get("lang", "Sanskrit"),
                "tradition":    source_meta.get("tradition", ""),
                "bias":         source_meta.get("bias", ""),
                "edition":      source_meta.get("edition", "GRETIL"),
                "reference":    ref,
                "line_num":     i + 1,
                "excerpt":      context[:1200],
                "matched_line": line.strip(),
            })

            if len(results) >= max_results:
                return results

    return results


def extract_reference(lines: List[str], pos: int) -> str:
    """Try to find a chapter/verse marker near the given line."""
    ref_patterns = [
        re.compile(r'\b(\d+)\s*[.|,]\s*(\d+)\b'),  # N.N pattern
        re.compile(r'adhyāya\s*(\d+)', re.I),
        re.compile(r'chapter\s*(\d+)', re.I),
        re.compile(r'sarga\s*(\d+)', re.I),
    ]
    # Search backwards up to 10 lines
    for i in range(pos, max(-1, pos - 10), -1):
        line = lines[i]
        for pat in ref_patterns:
            m = pat.search(line)
            if m:
                return line.strip()[:60]
    return f"Line {pos + 1}"


def is_devanagari(text: str) -> bool:
    return any('\u0900' <= c <= '\u097F' for c in text)


# IAST diacritic normalization map — allows "narada" to match "nārada"
_IAST_MAP = str.maketrans(
    "āĀīĪūŪṛṚṝḷṃṄṅñṭṬḍḌṇṆśŚṣṢḥḤ",
    "aaiiuurrrlmnnnttddnnsssshh"
)

def normalize_iast(text: str) -> str:
    """Strip IAST diacritics to ASCII for fuzzy Sanskrit matching."""
    import unicodedata as _ud
    return _ud.normalize('NFC', text).translate(_IAST_MAP).lower()


# Sanskrit synonym expansions for common research queries
_SANSKRIT_SYNONYMS: dict = {
    "creation":    ["srishti", "sristi", "utpatti", "prabhava"],
    "destruction": ["pralaya", "samhara", "vinasha"],
    "vishnu":      ["narayana", "hari", "vasudeva", "kesava"],
    "shiva":       ["rudra", "mahadeva", "maheshvara", "hara"],
    "brahma":      ["pitamaha", "prajapati", "hiranyagarbha"],
    "devi":        ["durga", "parvati", "shakti", "kali", "ambika"],
    "krishna":     ["govinda", "gopala", "madhava"],
    "moksha":      ["mukti", "liberation", "kaivalya", "vimukti"],
    "karma":       ["kriya", "dharma", "phala"],
    "yoga":        ["samadhi", "dhyana", "pranayama"],
    "atman":       ["jivatma", "brahman", "paramatman"],
    "time":        ["kala", "yuga", "manvantara", "kalpa"],
    "narada":      ["naradiya", "devarshi"],
    "rama":        ["raghava", "raghunatha", "dasharathi"],
}

def expand_query_terms(query: str) -> list:
    """Return query + Sanskrit synonyms for richer retrieval."""
    terms = [query.lower()]
    for key, synonyms in _SANSKRIT_SYNONYMS.items():
        if key in query.lower():
            terms.extend(synonyms)
    return list(dict.fromkeys(terms))[:5]



async def _validate_llm_providers() -> None:
    """
    Probe each configured LLM provider with a minimal request at startup.
    Respects LLM_PROVIDER env var for priority ordering.
    Sets state.active_provider / state.active_model so every request knows
    which provider is live without retrying a known-bad key every time.
    """
    preferred = LLM_PROVIDER  # from env: "deepseek" | "groq" | "gemini" | "auto"

    # Build ordered probe list: preferred provider goes first
    DEEPSEEK_API_KEY_VAL = os.getenv("DEEPSEEK_API_KEY", "")

    async def _probe_deepseek() -> bool:
        if not DEEPSEEK_API_KEY_VAL or DEEPSEEK_API_KEY_VAL.startswith("your_"):
            return False
        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY_VAL}", "Content-Type": "application/json"}
        payload = {"model": "deepseek-v4-flash", "messages": [{"role":"user","content":"hi"}],
                   "max_tokens": 1, "stream": False}
        try:
            async with get_http_session() as s:
                async with s.post(url, headers=headers, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        state.active_provider = "deepseek"
                        state.active_model    = "deepseek-v4-flash"
                        logger.info("✓ DeepSeek API key valid — model: deepseek-v4-flash")
                        return True
                    body = await r.text()
                    logger.warning("✗ DeepSeek API key invalid (HTTP %d): %s", r.status, body[:120])
        except Exception as e:
            logger.warning("✗ DeepSeek probe failed: %s", e)
        return False

    async def _probe_groq() -> bool:
        if not GROQ_API_KEY or GROQ_API_KEY.startswith("your_"):
            return False
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": GROQ_MODEL, "messages": [{"role":"user","content":"hi"}],
                   "max_tokens": 1, "stream": False}
        try:
            async with get_http_session() as s:
                async with s.post(url, headers=headers, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        state.active_provider = "groq"
                        state.active_model    = GROQ_MODEL
                        logger.info("✓ Groq API key valid — model: %s", GROQ_MODEL)
                        return True
                    body = await r.text()
                    logger.warning("✗ Groq API key invalid (HTTP %d): %s", r.status, body[:120])
        except Exception as e:
            logger.warning("✗ Groq probe failed: %s", e)
        return False

    async def _probe_gemini() -> bool:
        if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your_"):
            return False
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": GEMINI_MODEL, "messages": [{"role":"user","content":"hi"}],
                   "max_tokens": 1, "stream": False}
        try:
            async with get_http_session() as s:
                async with s.post(url, headers=headers, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        state.active_provider = "gemini"
                        state.active_model    = GEMINI_MODEL
                        logger.info("✓ Gemini API key valid — model: %s", GEMINI_MODEL)
                        return True
                    body = await r.text()
                    logger.warning("✗ Gemini API key invalid (HTTP %d): %s", r.status, body[:120])
        except Exception as e:
            logger.warning("✗ Gemini probe failed: %s", e)
        return False

    # Try in LLM_PROVIDER-first order
    probe_order = {
        "deepseek": [_probe_deepseek, _probe_groq, _probe_gemini],
        "groq":     [_probe_groq, _probe_deepseek, _probe_gemini],
        "gemini":   [_probe_gemini, _probe_deepseek, _probe_groq],
    }.get(preferred, [_probe_deepseek, _probe_groq, _probe_gemini])

    for probe in probe_order:
        if await probe():
            return

    logger.error("✗ No working LLM provider found — check your .env API keys!")
    state.active_provider = "none"


# ── Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🕉️  PuranGPT v2 starting…")

    # Load GRETIL Sanskrit corpus for search
    load_gretil_corpus()

    # Try to load vector search index
    try:
        from indexer.search import HybridSearcher
        searcher = HybridSearcher()
        await searcher.initialize()
        state.searcher = searcher
        state.index_ready = True
        # Cache verse count for /api/status
        try:
            from backend.db_client import get_db_conn
            conn = get_db_conn()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM purana_verses")
                    state.total_verses = cur.fetchone()[0]
                conn.close()
        except Exception:
            pass
        logger.info("✓ Vector index ready (%d verses)", state.total_verses)
    except Exception as e:
        logger.info("Vector index not built yet: %s", e)

    # Create HTTP client BEFORE provider validation (probes need it)
    state.http_client = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=60),
        connector=aiohttp.TCPConnector(limit=100)
    )

    # Validate API keys and determine active provider
    await _validate_llm_providers()

    logger.info("🚀 Active provider: %s (%s) — Ready at http://localhost:%s",
                state.active_provider, state.active_model, os.getenv("PORT", "8000"))

    yield

    if state.http_client:
        await state.http_client.close()

@asynccontextmanager
async def get_http_session():
    # Helper to avoid changing indentation in 10 different places
    yield state.http_client


# ── FastAPI ────────────────────────────────────────────────────────────────
app = FastAPI(title="PuranGPT", version="2.0.0", lifespan=lifespan)
_CORS_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://204.168.176.229:3000,http://localhost:3000,http://127.0.0.1:3000"
).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def extract_custom_keys(request: Request, call_next):
    keys = {
        "groq": request.headers.get("x-groq-key"),
        "together": request.headers.get("x-together-key"),
        "deepseek": request.headers.get("x-deepseek-key"),
        "gemini": request.headers.get("x-gemini-key"),
        "zhipu": request.headers.get("x-zhipu-key"),
    }
    custom_keys_var.set({k: v for k, v in keys.items() if v})
    return await call_next(request)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Pydantic Models ────────────────────────────────────────────────────────

class SourceModel(BaseModel):
    """Typed representation of a single retrieved source passage."""
    text_id:    str = ""
    text_name:  str = ""          # human-readable name (Bhagavata Purana, etc.)
    purana:     str = ""          # same as text_name for vector-index results
    reference:  str = ""          # e.g. "Skandha 10 · Ch. 29 · Verse 14"
    chapter:    Optional[Any] = None
    verse_range: str = ""
    text:       str = ""          # actual passage text
    excerpt:    str = ""          # alias used by GRETIL results
    language:   str = "Sanskrit"
    edition:    str = ""
    tradition:  str = ""
    bias:       str = ""
    score:      float = 0.0
    line_num:   int = 0

    @property
    def display_name(self) -> str:
        return self.text_name or self.purana or self.text_id or "Unknown"

    @property
    def display_text(self) -> str:
        return self.text or self.excerpt

    def to_frontend_dict(self) -> dict:
        """Serialise to the shape expected by the frontend source-card renderer."""
        return {
            "text_id":    self.text_id,
            "text_name":  self.display_name,
            "purana":     self.purana or self.text_name,
            "reference":  self.reference,
            "chapter":    self.chapter,
            "verse_range":self.verse_range,
            "text":       self.display_text[:600],   # cap for SSE payload size
            "language":   self.language,
            "edition":    self.edition,
            "tradition":  self.tradition,
            "bias":       self.bias,
            "score":      round(self.score, 4),
            "line_num":   self.line_num,
        }


class ChatRequest(BaseModel):
    query:      str
    mode:       str = "research"
    session_id: str = "default"
    filters:    Optional[dict] = None
    stream:     bool = True
    top_k:      int = 10
    model:      str = "auto"
    language:   str = "en"
    truncate_history_from_index: Optional[int] = None

class SanskritSearchRequest(BaseModel):
    query:    str
    text_ids: Optional[List[str]] = None
    max_results: int = 30

class SearchRequest(BaseModel):
    query:   str
    top_k:   int = 20
    filters: Optional[dict] = None

class InstancesRequest(BaseModel):
    query:       str
    category:    Optional[str] = None
    max_results: int = 100
    model:       str = "auto"


# ── LLM Streaming ──────────────────────────────────────────────────────────
import asyncio

async def stream_groq(messages: List[dict], temperature: float = 0.3, max_retries: int = 5, req_model: str = "auto", custom_key: str = None) -> AsyncGenerator[Union[str, dict], None]:
    """Stream tokens from Groq API with full conversation messages and rate limit handling."""
    key = custom_key or GROQ_API_KEY
    if not key: raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured.")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }
    
    target_model = GROQ_MODEL
    if req_model == "llama-3.1-8b-instant":
        target_model = "llama-3.1-8b-instant"
    elif req_model == "llama-3.3-70b-versatile":
        target_model = "llama-3.3-70b-versatile"
        
    fallback_model = "llama-3.1-8b-instant"
    
    payload = {
        "model":       target_model,
        "messages":    messages,
        "stream":      True,
        "temperature": temperature,
        "max_tokens":  8192,
    }
    
    for attempt in range(max_retries):
        async with get_http_session() as sess:
            async with sess.post(url, headers=headers, json=payload,
                                 timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status in (429, 413):
                    if payload["model"] != fallback_model:
                        logger.warning(f"Groq error {resp.status} on {payload['model']}. Switching to Groq fallback model {fallback_model}...")
                        payload["model"] = fallback_model
                        continue
                    else:
                        # Both Groq models exhausted — escape to cross-provider fallback
                        logger.warning(f"Groq rate limit exhausted on all models after {attempt+1} attempts. Escalating to next provider...")
                        raise _ProviderRateLimited("groq")

                if resp.status != 200:
                    body = await resp.text()
                    raise HTTPException(status_code=resp.status, detail=f"Groq error: {body}")

                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        try:
                            data  = json.loads(line[6:])
                            token = data["choices"][0]["delta"].get("content", "")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                return  # Successful completion

async def stream_gemini(messages: List[dict], temperature: float = 0.3, custom_key: str = None) -> AsyncGenerator[Union[str, dict], None]:
    """Stream tokens from Gemini API via its OpenAI-compatible endpoint."""
    key = custom_key or GEMINI_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured")
        
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }
    
    payload = {
        "model":       GEMINI_MODEL,
        "messages":    messages,
        "stream":      True,
        "temperature": temperature,
        "max_tokens":  4096,
    }
    
    async with get_http_session() as sess:
        async with sess.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Gemini error: {body}")
                
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data  = json.loads(line[6:])
                        token = data["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

async def stream_deepseek(messages: List[dict], temperature: float = 0.3, req_model: str = "deepseek-chat", custom_key: str = None) -> AsyncGenerator[Union[str, dict], None]:
    key = custom_key or DEEPSEEK_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="DEEPSEEK_API_KEY not configured")
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": req_model, "messages": messages, "stream": True}
    if req_model != "deepseek-reasoner":
        payload["temperature"] = temperature

    async with get_http_session() as sess:
        async with sess.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"DeepSeek error: {body}")
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line or line == "data: [DONE]": continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data["choices"][0]["delta"]
                        
                        # Yield reasoning token if present
                        reasoning = delta.get("reasoning_content", "")
                        if reasoning:
                            yield {"type": "reasoning", "content": reasoning}
                            
                        # Yield standard content token if present
                        token = delta.get("content", "")
                        if token: yield token
                    except: continue

async def stream_together(messages: List[dict], temperature: float = 0.3, req_model: str = "Qwen/Qwen2.5-72B-Instruct-Turbo", custom_key: str = None) -> AsyncGenerator[Union[str, dict], None]:
    key = custom_key or TOGETHER_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="TOGETHER_API_KEY not configured")
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": req_model, "messages": messages, "stream": True, "temperature": temperature}
    async with get_http_session() as sess:
        async with sess.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Together error: {body}")
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line or line == "data: [DONE]": continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        token = data["choices"][0]["delta"].get("content", "")
                        if token: yield token
                    except: continue

async def stream_zhipu(messages: List[dict], temperature: float = 0.3, req_model: str = "glm-5.1", custom_key: str = None) -> AsyncGenerator[Union[str, dict], None]:
    key = custom_key or ZHIPU_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="ZHIPU_API_KEY not configured")
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": req_model, "messages": messages, "stream": True, "temperature": temperature}
    async with get_http_session() as sess:
        async with sess.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Zhipu error: {body}")
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line or line == "data: [DONE]": continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        token = data["choices"][0]["delta"].get("content", "")
                        if token: yield token
                    except: continue

async def stream_ollama(messages: List[dict], temperature: float = 0.3, req_model: str = "qwen2.5:7b") -> AsyncGenerator[Union[str, dict], None]:
    url = f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/chat"
    payload = {"model": req_model, "messages": messages, "stream": True, "options": {"temperature": temperature}}
    async with get_http_session() as sess:
        async with sess.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Ollama error: {body}")
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line: continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token: yield token
                    if data.get("done"): break
                except Exception:
                    continue

class _ProviderRateLimited(Exception):
    """Raised internally when a provider exhausts its rate limit — triggers cross-provider fallback."""
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"{provider} rate limit exhausted")

# Semaphore: max 3 concurrent LLM calls across all gunicorn workers sharing this event loop.
# Prevents thundering-herd burst against the same API key.
_llm_semaphore = asyncio.Semaphore(3)

async def stream_llm(messages: List[dict], temperature: float = 0.3, max_retries: int = 5, req_model: str = "auto", custom_keys: dict = None) -> AsyncGenerator[Union[str, dict], None]:
    """Route to LLM provider with full cross-provider fallback: Groq → Gemini → DeepSeek → Ollama"""
    custom_keys = custom_keys or custom_keys_var.get()

    if req_model == "auto":
        provider = state.active_provider
        if provider == "deepseek":
            req_model = "deepseek-deepseek-chat"
        elif provider == "groq":
            req_model = f"groq-{state.active_model}"
        elif provider == "gemini":
            req_model = f"gemini-{state.active_model}"
        else:
            req_model = "deepseek-deepseek-chat"

    async with _llm_semaphore:
        try:
            if req_model.startswith("groq"):
                if not custom_keys.get("groq") and not GROQ_API_KEY:
                    raise HTTPException(status_code=503, detail="GROQ_API_KEY missing")
                async for token in stream_groq(messages, temperature, max_retries, req_model.replace("groq-", ""), custom_keys.get("groq")):
                    yield token
                return
            elif req_model.startswith("deepseek"):
                model_name = req_model[len("deepseek-"):] or "deepseek-chat"
                async for token in stream_deepseek(messages, temperature, model_name, custom_keys.get("deepseek")):
                    yield token
                return
            elif req_model.startswith("ollama"):
                async for token in stream_ollama(messages, temperature, os.getenv("OLLAMA_MODEL", "qwen2.5:7b")):
                    yield token
                return
            elif req_model.startswith("gemini"):
                async for token in stream_gemini(messages, temperature, custom_keys.get("gemini")):
                    yield token
                return
            elif req_model.startswith("zhipu"):
                async for token in stream_zhipu(messages, temperature, req_model.replace("zhipu-", ""), custom_keys.get("zhipu")):
                    yield token
                return
        except (_ProviderRateLimited, HTTPException) as e:
            status = getattr(e, 'status_code', 429)
            if status not in (429, 503, 413):
                raise
            logger.warning(f"Primary LLM ({req_model}) rate-limited or unavailable: {e}")

        # ── Cross-provider fallback cascade ─────────────────────────────
        # Fallback 1: Gemini Flash (generous free quota)
        if GEMINI_API_KEY and not req_model.startswith("gemini"):
            try:
                logger.info("Falling back to Gemini Flash...")
                yield {"type": "info", "message": "Switching to Gemini Flash..."}
                async for token in stream_gemini(messages, temperature, custom_keys.get("gemini")):
                    yield token
                return
            except Exception as e:
                logger.warning(f"Gemini fallback failed: {e}")

        # Fallback 2: DeepSeek
        if DEEPSEEK_API_KEY and not req_model.startswith("deepseek"):
            try:
                logger.info("Falling back to DeepSeek Chat...")
                yield {"type": "info", "message": "Switching to DeepSeek Chat..."}
                async for token in stream_deepseek(messages, temperature, "deepseek-chat", custom_keys.get("deepseek")):
                    yield token
                return
            except Exception as e:
                logger.warning(f"DeepSeek fallback failed: {e}")

        # Fallback 3: Ollama local (if available)
        try:
            logger.info("Last resort: falling back to local Ollama...")
            yield {"type": "info", "message": "Using local model (may be slower)..."}
            async for token in stream_ollama(messages, temperature, os.getenv("OLLAMA_MODEL", "qwen2.5:7b")):
                yield token
            return
        except Exception as e:
            logger.error(f"All LLM providers failed: {e}")
            yield {"type": "error", "message": "All AI providers are temporarily unavailable. Please try again in a moment."}
            raise HTTPException(status_code=503, detail="All LLM providers are currently unavailable.")


async def call_llm_once(messages: List[dict], temperature: float = 0.2, req_model: str = "auto") -> str:
    """Single non-streaming LLM call. Used for sub-queries in deep research."""
    full = []
    async for item in stream_llm(messages, temperature, req_model=req_model):
        if isinstance(item, str):
            full.append(item)
    return "".join(full)


def _looks_english(text: str) -> bool:
    """Cheap heuristic: is this query already plain English/IAST (ASCII letters)?
    If so we can skip the LLM translation round-trip entirely, which removes 1-3s
    of latency before the first answer token for the ~majority of queries that are
    typed in English. Any non-Latin script (Devanagari, Cyrillic, CJK…) returns
    False so we fall back to the real LLM translation path."""
    if not text:
        return True
    non_ascii = sum(1 for ch in text if ord(ch) > 0x2FF)  # beyond Latin-1+extended
    return non_ascii == 0


async def detect_and_translate_query(query: str) -> tuple[str, str]:
    """
    Detect language of query. If it's not pure English/IAST, translate to English+Sanskrit keywords.
    Returns (detected_language_name, english_search_query).
    """
    # Fast path: query is already ASCII/English → no LLM call needed.
    if _looks_english(query):
        return "English", query

    prompt = f"""Analyze this user search query: "{query}"

Respond with ONLY valid JSON in this exact format:
{{
  "language": "Full Name of Language in English (e.g., Hindi, Russian, French, English)",
  "search_query": "The query translated into English, but keep core Sanskrit concepts (like dharma, karma, purusha) as IAST transliterated Sanskrit words."
}}

Do not include any other text or formatting. Just the JSON."""

    try:
        response_text = await call_llm_once([{"role": "user", "content": prompt}])
        # Extract JSON if wrapped in markdown
        import re
        match = re.search(r'\{.*\}', response_text.strip(), re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            lang = data.get("language", "English")
            translated = data.get("search_query", query)
            # If the user typed english, just use their exact query
            if lang.lower() == "english":
                return lang, query
            return lang, translated
    except Exception as e:
        logger.error("Query translation failed: %s", e)
    
    return "English", query



def format_history(history: List[dict]) -> str:
    """Format conversation history with a rolling character window."""
    if not history:
        return "(No previous conversation)"
    
    # Take up to last 20 messages, but enforce a rolling character limit
    max_chars = 8000
    current_chars = 0
    lines = []

    for msg in reversed(history[-10:]):
        role = "User" if msg["role"] == "user" else "PuranGPT"
        content = msg['content']
        
        # INTELLIGENT FIX: Retain ONLY the Summary part of PuranGPT's previous answers.
        # This gives the LLM context of what the user was already told, but completely
        # strips out the heavy Sanskrit citations and quotes that cause RAG overfitting.
        if role == "PuranGPT":
            if "### 📋 Summary" in content:
                # Extract just the summary section
                parts = content.split("### 📋 Summary")
                if len(parts) > 1:
                    summary_part = parts[1].split("### 📚 Citations")[0].strip()
                    # Keep only the first 250 characters of the summary just to be safe
                    if len(summary_part) > 250:
                        summary_part = summary_part[:250] + "..."
                    content = f"(Summary of previous answer): {summary_part}"
                else:
                    continue # Couldn't parse, drop it
            else:
                # If no summary header found, keep a tiny snippet
                if len(content) > 100:
                    content = content[:100] + "..."
                content = f"(Summary of previous answer): {content}"
            
        line = f"**{role}**: {content}"
        
        if current_chars + len(line) > max_chars:
            break
            
        lines.insert(0, line)
        current_chars += len(line)
        
    return "\n\n".join(lines)


def build_rag_context(results: list) -> str:
    if not results:
        return ""
    out = ["\n## Passages Retrieved from Indexed Corpus\n"]
    for i, r in enumerate(results[:8], 1):
        if isinstance(r, dict):
            ref  = r.get("reference", "")
            text = r.get("text", "") or r.get("excerpt", "")
            lang = r.get("language", "") or r.get("lang", "")
            edition = r.get("edition", "")
            bias    = r.get("bias", "")
        else:
            ref     = getattr(r, "reference", "")
            text    = getattr(r, "text", "")
            lang    = getattr(r, "language", "")
            edition = getattr(r, "edition", "")
            bias    = getattr(r, "bias", "")
        meta_parts = [p for p in [lang, edition, bias] if p]
        meta_str   = f" [{', '.join(meta_parts)}]" if meta_parts else ""
        out.append(f"**[{i}]** {ref}{meta_str}\n{text[:1500]}\n{'─'*60}")
    return "\n".join(out)


def build_source_list(results: list) -> List[dict]:
    """Convert raw search results (SearchResult objects or dicts) to typed SourceModel dicts."""
    sources = []
    for r in results[:8]:
        if isinstance(r, dict):
            sm = SourceModel(
                text_id    = r.get("text_id", ""),
                text_name  = r.get("text_name", "") or r.get("purana", ""),
                purana     = r.get("purana", "") or r.get("text_name", ""),
                reference  = r.get("reference", ""),
                chapter    = r.get("chapter"),
                verse_range= r.get("verse_range", ""),
                text       = r.get("text", ""),
                excerpt    = r.get("excerpt", ""),
                language   = r.get("language", "Sanskrit"),
                edition    = r.get("edition", ""),
                tradition  = r.get("tradition", ""),
                bias       = r.get("bias", ""),
                score      = float(r.get("score", 0)),
                line_num   = int(r.get("line_num", 0)),
            )
        else:
            sm = SourceModel(
                text_id    = getattr(r, "id", ""),
                text_name  = getattr(r, "purana", ""),
                purana     = getattr(r, "purana", ""),
                reference  = getattr(r, "reference", ""),
                chapter    = getattr(r, "chapter", None),
                verse_range= getattr(r, "verse_range", ""),
                text       = getattr(r, "text", ""),
                language   = getattr(r, "language", "Sanskrit"),
                edition    = getattr(r, "edition", ""),
                tradition  = getattr(r, "tradition", ""),
                bias       = getattr(r, "bias", ""),
                score      = float(getattr(r, "score", 0)),
            )
        sources.append(sm.to_frontend_dict())
    return sources


# ── Deep Research Pipeline ─────────────────────────────────────────────────
async def deep_research(query: str, session_id: str, user_id: str = None) -> AsyncGenerator[str, None]:
    """
    Two-stage Interactive Deep Research:
    Stage 1: Ask clarifying question based on initial query.
    Stage 2: Execute deep research based on combined context.
    """
    session_data = session_manager.get_session(session_id)
    history = session_data["history"]
    history_str = format_history(history)

    is_clarifier_response = False
    if history and history[-1].get("is_clarifier"):
        is_clarifier_response = True

    if not is_clarifier_response:
        # Stage 1: Clarification — ask one focused question to sharpen the research direction
        _clarifier = (
            "You are PuranGPT's research planner. The user wants a deep, web-grounded research answer "
            "on a Vedic or Puranic topic. Ask ONE short clarifying question to focus the research "
            "(e.g. which tradition, timeframe, comparison angle). Be concise — one sentence."
        )
        clarify_msgs = [
            {"role": "system", "content": _clarifier},
            {"role": "user", "content": f"User query: {query}"}
        ]
        
        yield f"data: {json.dumps({'type':'status','message':'🤔 Analyzing query to focus research…'})}\n\n"
        
        full_response = []
        async for item in stream_llm(clarify_msgs):
            if isinstance(item, dict):
                yield f"data: {json.dumps(item)}\n\n"
            else:
                full_response.append(item)
                yield f"data: {json.dumps({'type':'token','content':item})}\n\n"
        
        full_text = "".join(full_response)
        session_manager.append_messages(session_id, [
            {"role": "user",      "content": query},
            {"role": "assistant", "content": full_text, "is_clarifier": True}
        ], user_id)
        
        yield f"data: {json.dumps({'type':'done'})}\n\n"
        return

    # Stage 2: Execution
    from backend.agents.deep_research import DeepResearchAgent
    from backend.db_client import get_profile
    
    role = "free"
    if user_id:
        profile = get_profile(user_id)
        if profile:
            role = profile.get("role", "free")
            
    use_reasoner = (role in ["pro", "scholar", "admin"])
    agent = DeepResearchAgent(model="deepseek-reasoner" if use_reasoner else "deepseek-chat")

    original_query = history[-2]["content"] if len(history) >= 2 else query
    combined_query = f"Original Query: {original_query}\nClarification: {query}"

    final_text = []
    
    async for event_type, content in agent.execute(combined_query, history):
        if event_type == "status":
            yield f"data: {json.dumps({'type':'status','message':content})}\n\n"
        elif event_type == "reasoning":
            yield f"data: {json.dumps({'type':'reasoning','content':content})}\n\n"
        elif event_type == "token":
            final_text.append(content)
            yield f"data: {json.dumps({'type':'token','content':content})}\n\n"
            
    # Save to memory
    full_text = "".join(final_text)
    session_manager.append_messages(session_id, [
        {"role": "user",      "content": combined_query},
        {"role": "assistant", "content": full_text}
    ], user_id)
    
    # Emit sources (dummy for now as DeepResearchAgent handles links in text)
    yield f"data: {json.dumps({'type':'sources','sources':[]})}\n\n"
    yield f"data: {json.dumps({'type':'done'})}\n\n"


# ── Routes ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def index_html_page():
    idx = FRONTEND_DIR / "index.html"
    if idx.exists():
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(idx, headers=headers)
    return HTMLResponse("<h1>🕉️ PuranGPT v2</h1>")

@app.get("/auth.js")
async def serve_auth_js():
    f = FRONTEND_DIR / "auth.js"
    if f.exists():
        return FileResponse(str(f))
    raise HTTPException(404, "Not Found")

@app.get("/landing.html", response_class=HTMLResponse)
async def landing():
    f = FRONTEND_DIR / "landing.html"
    if f.exists():
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return FileResponse(f, headers=headers)
    raise HTTPException(404, "Frontend not built.")

@app.get("/login.html", response_class=HTMLResponse)
async def login_page():
    f = FRONTEND_DIR / "login.html"
    if f.exists():
        return FileResponse(str(f))
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.get("/ios", response_class=HTMLResponse)
async def ios_frontend():
    idx = FRONTEND_DIR / "generated_ui.html"
    if idx.exists():
        return FileResponse(str(idx))
    return HTMLResponse("<h1>iOS UI not found</h1>")


@app.get("/api/status")
async def status():
    provider_ok = state.active_provider not in ("none", "unknown")
    return {
        "status":          "ok" if provider_ok else "degraded",
        "version":         "2.0",
        "llm_provider":    state.active_provider,
        "model":           state.active_model or GROQ_MODEL,
        "groq_key_valid":  state.active_provider == "groq",
        "gemini_key_valid":state.active_provider == "gemini" or (GEMINI_API_KEY and state.active_provider == "groq"),
        "index_ready":     state.index_ready,
        "total_verses":    getattr(state, "total_verses", 0),
        "gretil_loaded":   state.gretil_loaded,
        "gretil_texts":    len(state.gretil_corpus),
        "gretil_chars":    state.total_gretil_chars,
        "features":        ["conversation_memory", "deep_research", "sanskrit_search", "source_transparency"],
    }


@app.get("/api/puranas")
async def list_puranas():
    catalog = [
        {"id":"agni",           "name":"Agni Purana",          "category":"mahapurana","tradition":"mixed",   "lang":"Sanskrit","bias":"✅ neutral",           "gretil":True},
        {"id":"bhagavata",      "name":"Bhagavata Purana",     "category":"mahapurana","tradition":"vaishnava","lang":"Sanskrit","bias":"⚠️ Vaishnava",          "gretil":True},
        {"id":"brahma",         "name":"Brahma Purana",        "category":"mahapurana","tradition":"mixed",   "lang":"Sanskrit","bias":"✅ mostly neutral",     "gretil":True},
        {"id":"brahmanda",      "name":"Brahmanda Purana",     "category":"mahapurana","tradition":"mixed",   "lang":"Sanskrit","bias":"✅ neutral",            "gretil":True},
        {"id":"garuda",         "name":"Garuda Purana",        "category":"mahapurana","tradition":"vaishnava","lang":"Sanskrit","bias":"⚠️ Vaishnava",          "gretil":True},
        {"id":"kurma",          "name":"Kurma Purana",         "category":"mahapurana","tradition":"shaiva-vaishnava","lang":"Sanskrit","bias":"✅ syncretic","gretil":True},
        {"id":"linga_1",        "name":"Linga Purana",         "category":"mahapurana","tradition":"shaiva",  "lang":"Sanskrit","bias":"✅ Shaiva",             "gretil":True},
        {"id":"markandeya",     "name":"Markandeya Purana",    "category":"mahapurana","tradition":"shakta",  "lang":"Sanskrit","bias":"✅ most stable",        "gretil":True},
        {"id":"matsya",         "name":"Matsya Purana",        "category":"mahapurana","tradition":"mixed",   "lang":"Sanskrit","bias":"✅ neutral",            "gretil":True},
        {"id":"narada",         "name":"Narada Purana",        "category":"mahapurana","tradition":"vaishnava","lang":"Sanskrit","bias":"⚠️ strong Vaishnava",   "gretil":True},
        {"id":"shiva_1_7",      "name":"Shiva Purana",         "category":"mahapurana","tradition":"shaiva",  "lang":"Sanskrit","bias":"✅ Shaiva",             "gretil":True},
        {"id":"vamana",         "name":"Vamana Purana",        "category":"mahapurana","tradition":"vaishnava","lang":"Sanskrit","bias":"⚠️ Vaishnava",          "gretil":True},
        {"id":"vishnu_critical","name":"Vishnu Purana",        "category":"mahapurana","tradition":"vaishnava","lang":"Sanskrit","bias":"⚠️ Vaishnava (critical)","gretil":True},
        # Yogic
        {"id":"yoga_vasistha",  "name":"Yoga Vasistha",        "category":"yoga",      "tradition":"advaita", "lang":"Sanskrit","bias":"✅ non-sectarian",       "gretil":False},
        {"id":"gorakshashataka","name":"Gorakshashataka (Gorakhnath)","category":"nath","tradition":"nath",  "lang":"Sanskrit","bias":"✅ Nath",               "gretil":False},
        {"id":"hatha_yoga",     "name":"Hatha Yoga Pradipika", "category":"yoga",      "tradition":"nath",    "lang":"Sanskrit","bias":"✅ Hatha-Yoga",         "gretil":False},
        {"id":"yoga_sutras",    "name":"Yoga Sutras (Patanjali)","category":"darshana","tradition":"darshana","lang":"Sanskrit","bias":"✅ pre-sectarian",       "gretil":False},
        # Darshanas
        {"id":"samkhya_karika", "name":"Samkhya Karika",       "category":"darshana",  "tradition":"darshana","lang":"Sanskrit","bias":"✅ pre-sectarian",       "gretil":False},
        {"id":"brahma_sutras",  "name":"Brahma Sutras (Vedanta)","category":"darshana","tradition":"darshana","lang":"Sanskrit","bias":"✅ pre-sectarian",       "gretil":False},
        # Epics
        {"id":"bhagavad_gita",  "name":"Bhagavad Gita",        "category":"epic",      "tradition":"mixed",   "lang":"Sanskrit","bias":"✅ BORI critical",       "gretil":False},
        {"id":"mahabharata",    "name":"Mahabharata",          "category":"epic",      "tradition":"mixed",   "lang":"Sanskrit","bias":"✅ BORI critical",       "gretil":False},
        {"id":"ramayana",       "name":"Valmiki Ramayana",     "category":"epic",      "tradition":"mixed",   "lang":"Sanskrit","bias":"✅ neutral",            "gretil":False},
        # Upanishads
        {"id":"upanishads_108", "name":"108 Upanishads",       "category":"upanishad", "tradition":"vedic",   "lang":"Sanskrit","bias":"✅ pre-sectarian",       "gretil":False},
    ]
    # Mark which are actually downloaded
    for item in catalog:
        item["downloaded"] = item["id"] in state.gretil_corpus
    return {"puranas": catalog, "total_downloaded": len(state.gretil_corpus)}


@app.get("/api/modes")
async def list_modes():
    return {"modes": [
        {"id":"research", "label":"📖 Research", "description":"Scholarly analysis with verse citations"},
        {"id":"guide",    "label":"🪔 Guide",    "description":"Spiritual guidance in Guruji's voice"},
        {"id":"deep",     "label":"🔬 Deep",     "description":"Web-grounded multi-step research"},
    ]}


@app.get("/api/sessions")
async def get_all_sessions(req: Request, user: Optional[dict] = Depends(get_current_user)):
    """List all saved sessions."""
    user_id = user.get("id") if user else None
    guest_id = get_guest_id(req)
    return {"sessions": session_manager.get_all_sessions(user_id, guest_id)}

@app.get("/api/session/{session_id}")
async def get_session(session_id: str, req: Request, user: Optional[dict] = Depends(get_current_user)):
    """Get conversation history for a session."""
    user_id = user.get("id") if user else None
    guest_id = get_guest_id(req)
    session_data = session_manager.get_session(session_id, user_id, guest_id)
    history = session_data.get("history", [])
    return {"session_id": session_id, "message_count": len(history), "history": history[-20:]}

@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str, req: Request, user: Optional[dict] = Depends(get_current_user)):
    """Clear conversation history."""
    user_id = user.get("id") if user else None
    guest_id = get_guest_id(req)
    session_manager.clear_session(session_id, user_id, guest_id)
    return {"cleared": True}


@app.get("/api/limits")
async def get_user_limits(req: Request, user: Optional[dict] = Depends(get_current_user)):
    """Return the remaining messages and research limits for the current user or guest."""
    is_byok = bool(custom_keys_var.get())
    if not user:
        guest_id = get_guest_id(req)
        allowed, rem = check_guest_rate_limit(guest_id)
        return {
            "role": "guest", 
            "messages_remaining": rem, 
            "research_remaining": 0,
            "max_messages": 10,
            "max_research": 0
        }
    else:
        role = user.get("role", "free")
        allowed, rem = check_rate_limit(user.get("id"), role, is_byok=is_byok)
        r_allowed, r_rem = check_research_limit(user.get("id"), role, is_byok=is_byok)
        
        max_msgs = 999999 if role in ["pro", "scholar", "admin"] or is_byok else 10
        max_res = 50 if role in ["pro", "scholar", "admin"] or is_byok else 3
        
        return {
            "role": role, 
            "messages_remaining": rem, 
            "research_remaining": r_rem,
            "max_messages": max_msgs,
            "max_research": max_res
        }

@app.get("/api/monitor/health")
async def monitor_health(user: dict = Depends(require_role(["admin"]))):
    """Run all health checks for the monitoring dashboard. Admin only."""
    active_sessions = len(session_manager.sessions) if hasattr(session_manager, 'sessions') else 0
    results = await run_health_checks(active_sessions)
    return results

@app.post("/api/chat")
async def chat(request: ChatRequest, req: Request, user: Optional[dict] = Depends(get_current_user)):
    validate_query(request.query)
        
    # Check BYOK
    is_byok = bool(custom_keys_var.get())
    
    # Rate Limiting — run sync Supabase calls in threadpool to avoid blocking the event loop
    if not user:
        guest_id = get_guest_id(req)
        allowed, rem = check_guest_rate_limit(guest_id)
        if not allowed:
            raise HTTPException(429, "Guest rate limit exceeded. Please sign in.")
    else:
        allowed, rem = await asyncio.to_thread(
            check_rate_limit, user.get("id"), user.get("role", "free"), is_byok
        )
        if not allowed:
            raise HTTPException(429, "Daily message limit exceeded. Please upgrade your plan.")
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        raise HTTPException(503, "No LLM credentials configured")

    user_id = user.get("id") if user else None
    session_id = request.session_id or "default"
    guest_id = get_guest_id(req) if not user else None
    
    if request.truncate_history_from_index is not None:
        session_manager.truncate_session(session_id, request.truncate_history_from_index, user_id, guest_id)

    # ── Deep Research Mode ──────────────────────────────────────────────────
    if request.mode == "deep":
        if user:
            r_allowed, r_rem = check_research_limit(user.get("id"), user.get("role", "free"), is_byok=is_byok)
            if not r_allowed:
                raise HTTPException(403, "Daily deep research limit reached. Please upgrade to Pro or provide your own API key.")
            increment_research_usage(user.get("id"))
        else:
            raise HTTPException(401, "Please sign in to use Deep Research.")
            
        async def deep_gen():
            async for chunk in deep_research(request.query, session_id, user.get("id") if user else None):
                yield {"data": chunk.replace("data: ", "").strip()}
        return EventSourceResponse(deep_gen(), headers={"X-Accel-Buffering": "no"})

    # ── Standard Chat ────────────────────────────────────────────────────────
    async def event_gen() -> AsyncGenerator[dict, None]:
        # Immediate feedback so the UI shows motion while we translate+search,
        # rather than dead air until the first LLM token.
        yield {"type": "status", "message": "🔍 Searching the sacred texts…"}

        # 0. Detect and Translate Query (skips the LLM call for English queries)
        detected_lang, search_query = await detect_and_translate_query(request.query)
        logger.info("Original Query: %r | Detected Lang: %s | Search Query: %r", request.query, detected_lang, search_query)

        # 1. RAG search (vector index if available)
        sources = []
        rag_context = ""
        if state.searcher and state.index_ready:
            try:
                # Use translated query for semantic search
                results = await state.searcher.hybrid_search(
                    query=search_query, top_k=request.top_k, filters=request.filters, sharma_weighting=(request.mode == "guide")
                )
                sources    = build_source_list(results)
                rag_context = build_rag_context(results)
            except Exception as e:
                logger.warning("RAG search failed: %s", e)

        # 2. Sanskrit corpus search (always runs against GRETIL)
        skt_results = []
        if state.gretil_corpus:
            # Use query expansion: try synonyms if primary search returns nothing
            words = [w for w in search_query.split() if len(w) > 3]
            primary_key = search_query if not words else " ".join(words[:2])
            skt_results = await asyncio.to_thread(search_sanskrit, primary_key, max_results=8)
            if not skt_results:
                for term in expand_query_terms(search_query)[1:]:   # skip first = original
                    skt_results = await asyncio.to_thread(search_sanskrit, term, max_results=8)
                    if skt_results:
                        break
            if skt_results and not rag_context:
                skt_ctx = "\n".join(
                    f"[{r['text_name']} / {r['edition']} / {r['language']} / {r['bias']}]\n"
                    f"Reference: {r['reference']}\n{r['excerpt'][:800]}"
                    for r in skt_results[:5]
                )
                rag_context += f"\n\n## Sanskrit Corpus (GRETIL — Primary Source)\n{skt_ctx}"
            elif skt_results and rag_context:
                # Append GRETIL alongside vector results for richer context
                skt_ctx = "\n".join(
                    f"[GRETIL: {r['text_name']} / {r['edition']}]\n"
                    f"Reference: {r['reference']}\n{r['excerpt'][:600]}"
                    for r in skt_results[:3]
                )
                rag_context += f"\n\n## Additional Sanskrit Primary Sources (GRETIL)\n{skt_ctx}"

        all_sources = sources + skt_results[:3]
        
        # Determine grounding quality
        if len(sources) > 0:
            grounding_quality = "grounded"
        elif len(skt_results) > 0:
            grounding_quality = "partial"
        else:
            grounding_quality = "ungrounded"
        yield {"data": json.dumps({"type": "sources", "sources": all_sources})}

        # 3. Build conversation messages with history
        session_data = session_manager.get_session(session_id)
        history    = session_data.get("history", [])
        history_str = format_history(history)

        prompt_tpl  = PROMPTS.get(request.mode, RESEARCH_SYSTEM)
        
        # Override detected language with user's explicit UI preference if provided
        target_lang = detected_lang
        if hasattr(request, "language") and request.language:
            lang_map = {"en": "English", "hi": "Hindi", "ru": "Russian"}
            target_lang = lang_map.get(request.language.lower(), detected_lang)

        lang_instr = f"## IMPORTANT: Respond strictly in {target_lang}. Translate all explanations to {target_lang}, but keep Sanskrit terms in IAST transliteration." if target_lang.lower() != "english" else ""
        system_text = prompt_tpl.format(
            interpolations=KNOWN_INTERPOLATIONS,
            language_instruction=lang_instr,
            context=rag_context or "(No indexed passages — answering from deep Puranic knowledge)",
            history=f"## Previous Conversation\n{history_str}" if history else ""
        )

        # 4. Build messages list (system + history + new query)
        messages = [{"role": "system", "content": system_text}]
        for msg in history[-10:]:   # include last 5 exchanges
            messages.append({"role": msg["role"], "content": msg["content"][:1200]})
        messages.append({"role": "user", "content": request.query})

        # 5. Determine Model by Subscription Tier and Stream
        if not user:
            target_model = "auto"  # Guest: use validated active provider
        else:
            role = user.get("role", "free")
            if role in ["pro", "scholar", "admin"]:
                target_model = "deepseek-deepseek-reasoner" # Pro users get DeepSeek Reasoner
            else:
                target_model = "auto"  # Free users: use validated active provider

        full_response = []
        try:
            async for item in stream_llm(messages, req_model=target_model):
                if await req.is_disconnected():
                    break
                if isinstance(item, dict):
                    yield {"data": json.dumps(item)}
                else:
                    full_response.append(item)
                    yield {"data": json.dumps({"type": "token", "content": item})}
        except Exception as e:
            logger.error("Groq stream error: %s", e)
            yield {"data": json.dumps({"type": "error", "message": str(e)})}
            return

        # 6. Save to session memory
        full_text = "".join(full_response)
        session_data = session_manager.append_messages(session_id, [
            {"role": "user",      "content": request.query},
            {"role": "assistant", "content": full_text}
        ], user_id, guest_id)
        
        if not user:
            increment_guest_usage(get_guest_id(req))
        else:
            # Non-blocking: fire-and-forget usage increment in threadpool
            asyncio.create_task(asyncio.to_thread(
                increment_usage, user.get("id"), session_id
            ))
        
        # 7. Done signal with source metadata
        yield {"data": json.dumps({
            "type":         "done",
            "session_id":   session_id,
            "history_len":  len(session_data["history"]),
            "sources_used": [s.get("text_name") or s.get("purana","") for s in all_sources[:4]],
            "grounding_quality": grounding_quality,
            "total_sources_found": len(all_sources)
        })}

    return EventSourceResponse(event_gen(), headers={"X-Accel-Buffering": "no"})


@app.post("/api/sanskrit-search")
async def sanskrit_search(request: SanskritSearchRequest):
    """Semantic full-text search with LLM query translation and result translation."""
    if not state.gretil_corpus:
        raise HTTPException(503, "GRETIL corpus not loaded. Run python fetch_gretil.py first.")
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")

    async def search_gen():
        query = request.query.strip()
        # 1. Translate query if it is English
        translated_terms = []
        if not is_devanagari(query) and len(query.split()) > 0:
            try:
                msgs = [
                    {"role": "system", "content": "You are a Sanskrit linguistic expert. Translate the user's English concept into 1 to 3 pertinent Sanskrit noun stems in IAST (romanized) format. Return ONLY a comma-separated list of the IAST words. Do not add quotes or explanation."},
                    {"role": "user", "content": query}
                ]
                ans = await call_llm_once(msgs, temperature=0.1)
                translated_terms = [t.strip().lower() for t in ans.split(",") if t.strip()]
            except Exception:
                translated_terms = [query.lower()]
        else:
            translated_terms = [query]

        if not translated_terms:
            translated_terms = [query]

        yield {"data": json.dumps({"type": "query_translated", "original": query, "terms": translated_terms})}

        # 2. Search GRETIL — try translated terms first, then synonym expansion
        results = []
        all_terms = translated_terms + expand_query_terms(query)
        seen_ids: set = set()
        for term in all_terms:
            res = await asyncio.to_thread(search_sanskrit, term, max_results=request.max_results, text_ids=request.text_ids)
            for r in res:
                key = (r["text_id"], r["line_num"])
                if key not in seen_ids:
                    seen_ids.add(key)
                    results.append(r)
            if len(results) >= request.max_results:
                break
        results = results[:request.max_results]
        
        yield {"data": json.dumps({
            "type": "search_complete",
            "total": len(results),
            "corpus_size": len(state.gretil_corpus),
            "source_tier": "TIER_1 — GRETIL University of Göttingen",
            "results": results
        })}

        # 3. Translate top 5 results
        for i, r in enumerate(results[:5]):
            excerpt = r.get("excerpt", "")
            if excerpt:
                try:
                    msgs = [
                        {"role": "system", "content": "You are a Sanskrit scholar. Translate this Sanskrit passage into English. Give a short, clear translation that captures the spiritual or philosophical meaning. No extra commentary."},
                        {"role": "user", "content": excerpt}
                    ]
                    translation = await call_llm_once(msgs, temperature=0.2)
                    yield {"data": json.dumps({"type": "translation_ready", "result_index": i, "translation": translation.strip()})}
                except Exception:
                    pass
            await asyncio.sleep(0.1)

    return EventSourceResponse(search_gen(), headers={"X-Accel-Buffering": "no"})


@app.post("/api/search")
async def search(request: SearchRequest):
    if not state.searcher:
        raise HTTPException(503, "Vector index not built. Run: python extract_and_index.py")
    results = await state.searcher.hybrid_search(
        query=request.query, top_k=request.top_k, filters=request.filters
    )
    return {
        "query":   request.query,
        "count":   len(results),
        "results": build_source_list(results),
    }


@app.post("/api/instances")
async def instances(request: InstancesRequest):
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        raise HTTPException(503, "No LLM credentials configured")

    # 1. Sanskrit corpus search
    skt_results = await asyncio.to_thread(search_sanskrit, request.query, max_results=request.max_results)

    # 2. Vector search if available
    indexed = []
    if state.searcher and state.index_ready:
        try:
            indexed = [r.to_dict() for r in await state.searcher.find_all_instances(request.query)]
        except Exception:
            pass

    all_results = skt_results + indexed
    if all_results:
        return {
            "topic":     request.query,
            "total":     len(all_results),
            "instances": all_results,
            "source":    "GRETIL Sanskrit corpus + vector index",
        }

    # 3. Groq fallback
    msgs = [
        {"role": "system", "content": RESEARCH_SYSTEM.format(
            interpolations=KNOWN_INTERPOLATIONS, language_instruction="", context="", history="")},
        {"role": "user", "content": f"List EVERY instance of '{request.query}' across all 18 Mahapuranas and Hindu sacred texts. Be exhaustive, cite chapter and verse."}
    ]
    answer_parts = []
    async for item in stream_llm(msgs, req_model=request.model):
        if isinstance(item, str):
            answer_parts.append(item)
    return {
        "topic":      request.query,
        "total":      None,
        "instances":  [],
        "llm_answer": "".join(answer_parts),
        "source":     "Groq LLM (scholarly knowledge)",
    }

@app.get("/api/citation-lookup")
async def citation_lookup(ref: str):
    """Looks up a citation, gets Sanskrit text, and translates it instantly."""
    results = await asyncio.to_thread(search_sanskrit, ref, max_results=1)
    
    if not results:
        # Fallback: maybe just find the first text that matches the book name
        ref_lower = ref.lower()
        for text_id, full_text in state.gretil_corpus.items():
            name = SOURCE_META.get(text_id, {}).get("name", text_id).lower()
            if name in ref_lower or ref_lower in name:
                excerpt = "\n".join(full_text.splitlines()[:5])
                results = [{
                    "text_id": text_id,
                    "text_name": SOURCE_META.get(text_id, {}).get("name", text_id),
                    "line_num": 1,
                    "excerpt": excerpt
                }]
                break
                
    if not results:
        raise HTTPException(404, "Citation not found in corpus.")
        
    result = results[0]
    sanskrit_text = result["excerpt"]
    
    # Translate it
    try:
        msgs = [
            {"role": "system", "content": "You are a Sanskrit scholar. Translate this short excerpt into clear English. Output ONLY the translation without any introduction or markdown formatting."},
            {"role": "user", "content": sanskrit_text}
        ]
        translation = await call_llm_once(msgs, temperature=0.1)
    except Exception as e:
        translation = "(Translation unavailable right now. Open document to explore further.)"
    
    return {
        "text_id": result["text_id"],
        "text_name": result["text_name"],
        "line_num": result.get("line_num", 1),
        "sanskrit": sanskrit_text,
        "translation": translation.strip()
    }

@app.get("/api/text/{text_id}")
async def get_text(text_id: str, page: int = 1, size: int = 100):
    if text_id not in state.gretil_corpus:
        raise HTTPException(404, f"Text {text_id} not found in memory.")
    
    full_text = state.gretil_corpus[text_id]
    lines = full_text.splitlines()
    total_lines = len(lines)
    
    start = (page - 1) * size
    end = start + size
    
    if start >= total_lines:
        return {"text_id": text_id, "lines": [], "page": page, "total_pages": (total_lines // size) + 1}
        
    return {
        "text_id": text_id,
        "lines": lines[start:end],
        "page": page,
        "total_pages": (total_lines // size) + 1,
        "total_lines": total_lines,
        "start_line": start
    }



class InferRequest(BaseModel):
    topic: str
    mode: str = "synthesis"      # synthesis | contradiction | evolution | practical
    session_id: str = "default"
    top_k: int = 15

INFER_PROMPT = """You are PuranGPT's Inference Engine — a senior Indological scholar producing ORIGINAL ANALYSIS.

Your task: Given retrieved passages on a topic, go beyond summarizing and produce scholarly inferences.

## Output Format — strictly follow all four sections:

### 📜 What the Texts Directly Say
Summarize the primary textual evidence with exact citations: (Text, Section, Ch. X, Verse Y).
Quote Sanskrit/Hindi originals where present. Identify which tradition each source represents.

### 🔗 Cross-Textual Synthesis
Identify patterns, agreements, and contradictions ACROSS texts that a reader wouldn't notice from any single source.
Which texts agree? Where do they diverge, and why (sectarian, chronological, geographical reasons)?

### 💡 Original Inferences & Scholarly Insights
Draw inferences that go BEYOND the literal text. This is the research value — what does the combined evidence suggest?
Examples: evolution of a concept over time, hidden cosmological logic, parallels with other philosophical traditions,
what the contradictions reveal about the social context of composition.
Mark clearly: *"Inference:"* before each one.

### 🧘 Practical / Philosophical Significance
What does this mean for understanding Hindu philosophy, practice, or cosmology TODAY?
How does this connect to the Darshanas, to Yoga, or to lived tradition?

## Retrieved Passages
{context}

---
Topic for analysis: **{topic}**
"""

@app.post("/api/infer")
async def infer(request: InferRequest, user: Optional[dict] = Depends(get_current_user)):
    """
    Original inference and scholarly synthesis endpoint.
    Retrieves passages from all indexed sources and produces structured analysis
    that goes beyond citation — draws cross-textual inferences.
    """
    if not user:
        raise HTTPException(401, "Sign in required for Scholarly Inference.")
        
    role = user.get("role", "free")
    if not check_inference_limit(user.get("id"), role):
        raise HTTPException(403, "Free trial for Scholarly Inference exhausted. Please upgrade to Pro.")
        
    if not request.topic.strip():
        raise HTTPException(400, "Topic cannot be empty")

    async def infer_gen() -> AsyncGenerator[dict, None]:
        increment_inference_usage(user.get("id"))
        # 1. Wide retrieval from both vector index and GRETIL
        all_passages = []
        if state.searcher and state.index_ready:
            try:
                results = await state.searcher.hybrid_search(query=request.topic, top_k=request.top_k)
                all_passages.extend(results)
            except Exception as e:
                logger.warning("Vector search failed for infer: %s", e)

        skt_hits = []
        for term in expand_query_terms(request.topic):
            hits = await asyncio.to_thread(search_sanskrit, term, max_results=10)
            skt_hits.extend(hits)
            if len(skt_hits) >= 10:
                break

        context = build_rag_context(all_passages)
        if skt_hits:
            gretil_ctx = "\n".join(
                f"[GRETIL: {r['text_name']} / {r['edition']}]\n{r['reference']}\n{r['excerpt'][:800]}"
                for r in skt_hits[:5]
            )
            context += f"\n\n## GRETIL Sanskrit Primary Sources\n{gretil_ctx}"

        sources = build_source_list(all_passages) + skt_hits[:5]
        yield {"data": json.dumps({"type": "sources", "sources": sources})}

        if not context.strip():
            context = "(No indexed passages found. Use general Puranic knowledge.)"

        prompt = INFER_PROMPT.format(context=context, topic=request.topic)
        msgs = [{"role": "system", "content": prompt}]

        yield {"data": json.dumps({"type": "status", "message": f"🔬 Synthesizing inferences across {len(all_passages) + len(skt_hits)} passages…"})}

        full_response = []
        async for item in stream_llm(msgs):
            if isinstance(item, str):
                full_response.append(item)
                yield {"data": json.dumps({"type": "token", "content": item})}
            elif isinstance(item, dict):
                yield {"data": json.dumps(item)}

        session_manager.append_messages(request.session_id, [
            {"role": "user",      "content": f"[INFER] {request.topic}"},
            {"role": "assistant", "content": "".join(full_response)},
        ], user_id)
        yield {"data": json.dumps({"type": "done"})}

    return EventSourceResponse(infer_gen(), headers={"X-Accel-Buffering": "no"})


@app.get("/api/index-status")
async def index_status():
    data_dir = Path("./data")
    chunk_count = 0
    if (data_dir / "chunks").exists():
        for f in (data_dir / "chunks").glob("*.jsonl"):
            try:
                chunk_count += sum(1 for _ in open(f) if _.strip())
            except Exception:
                pass
    return {
        "gretil_texts":    len(state.gretil_corpus),
        "gretil_chars":    state.total_gretil_chars,
        "chunks_built":    chunk_count,
        "index_ready":     state.index_ready,
        "vector_docs":     state.searcher.total_documents if state.searcher else 0,
    }


# ── Auth Endpoints ────────────────────────────────────────────────────────

@app.get("/api/user/profile")
async def get_user_profile(user: dict = Depends(require_auth)):
    return user

@app.put("/api/user/profile")
async def update_user_profile(data: dict, user: dict = Depends(require_auth)):
    update_profile(user["id"], data)
    return {"success": True}

@app.get("/api/user/usage")
async def get_user_usage(user: dict = Depends(require_auth)):
    from backend.db_client import get_profile
    is_byok = bool(custom_keys_var.get())
    profile = get_profile(user["id"]) or {}
    
    msg_allowed, msg_rem = check_rate_limit(user["id"], user.get("role", "free"), is_byok=is_byok)
    res_allowed, res_rem = check_research_limit(user["id"], user.get("role", "free"), is_byok=is_byok)
    
    return {
        "role": user.get("role", "free"),
        "is_byok": is_byok,
        "messages": {
            "used": profile.get("daily_message_count", 0),
            "remaining": msg_rem,
            "limit": profile.get("daily_message_count", 0) + msg_rem if msg_rem != 999999 else "Unlimited"
        },
        "research": {
            "used": profile.get("deep_research_count", 0),
            "remaining": res_rem,
            "limit": profile.get("deep_research_count", 0) + res_rem if res_rem != 999999 else "Unlimited"
        }
    }

@app.put("/api/user/keys")
async def save_user_keys(data: dict, user: dict = Depends(require_auth)):
    encrypted = encrypt_keys(data.get("keys", {}))
    update_profile(user["id"], {"byok_keys": encrypted})
    return {"success": True}

@app.get("/api/user/keys")
async def get_user_keys(user: dict = Depends(require_auth)):
    keys = decrypt_keys(user.get("byok_keys", ""))
    # Mask keys for security
    masked = {k: f"{v[:4]}...{v[-4:]}" if len(v) > 10 else "***" for k, v in keys.items() if v}
    return {"keys": masked}

@app.get("/api/admin/users")
async def admin_get_users(user: dict = Depends(require_role(["admin"]))):
    return {"users": get_all_users()}

@app.get("/api/admin/stats")
async def admin_get_stats(user: dict = Depends(require_role(["admin"]))):
    return get_admin_stats()


# ── Billing Endpoints ──────────────────────────────────────────────────────

from backend.billing import (
    create_stripe_checkout,
    create_razorpay_order,
    verify_razorpay_payment,
    activate_user_subscription,
    STRIPE_WEBHOOK_SECRET,
    is_stripe_configured,
    is_razorpay_configured
)
import stripe

class CheckoutRequest(BaseModel):
    plan: str
    provider: str
    success_url: str
    cancel_url: str

class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan: str

@app.post("/api/billing/checkout")
async def billing_checkout(request: CheckoutRequest, user: dict = Depends(require_auth)):
    try:
        user_id = user["id"]
        if request.provider == "stripe":
            res = create_stripe_checkout(user_id, request.plan, request.success_url, request.cancel_url)
            return res
        elif request.provider == "razorpay":
            res = create_razorpay_order(user_id, request.plan)
            return res
        else:
            raise HTTPException(400, f"Unsupported billing provider: {request.provider}")
    except Exception as e:
        logger.error(f"Billing checkout error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/billing/razorpay/verify")
async def razorpay_verify(request: RazorpayVerifyRequest, user: dict = Depends(require_auth)):
    user_id = user["id"]
    verified = verify_razorpay_payment(
        request.razorpay_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature
    )
    if not verified:
        raise HTTPException(400, "Payment verification failed")
        
    success = activate_user_subscription(
        user_id=user_id,
        plan=request.plan,
        provider="razorpay",
        external_sub_id=request.razorpay_payment_id
    )
    if not success:
        raise HTTPException(500, "Failed to update subscription profile")
        
    return {"success": True}

@app.post("/api/billing/stripe/webhook")
async def stripe_webhook(req: Request):
    payload = await req.body()
    sig_header = req.headers.get("stripe-signature")
    
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET is not configured. Cannot verify webhook.")
        raise HTTPException(400, "Webhook secret not configured")
        
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(400, "Invalid signature")
        
    event_type = event["type"]
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        if not user_id and session.get("metadata"):
            user_id = session["metadata"].get("user_id")
            
        plan = "pro"
        if session.get("metadata") and session["metadata"].get("plan"):
            plan = session["metadata"]["plan"]
            
        if user_id:
            activate_user_subscription(
                user_id=user_id,
                plan=plan,
                provider="stripe",
                external_sub_id=session.get("subscription") or session.get("id")
            )
            
    return {"status": "success"}

@app.post("/api/billing/revenuecat/webhook")
async def revenuecat_webhook(req: Request):
    try:
        # RevenueCat sends JSON webhooks for lifecycle events
        # We can configure an Authorization header in the RevenueCat dashboard for security
        auth_header = req.headers.get("Authorization")
        expected_auth = os.getenv("REVENUECAT_WEBHOOK_AUTH", "")
        if expected_auth and auth_header != expected_auth:
            raise HTTPException(401, "Unauthorized webhook source")

        payload = await req.json()
        event = payload.get("event", {})
        event_type = event.get("type")
        
        # app_user_id maps to our Supabase user_id
        user_id = event.get("app_user_id")
        entitlement = event.get("entitlement_id") # e.g. 'pro', 'scholar'
        
        if event_type in ["INITIAL_PURCHASE", "RENEWAL"]:
            if user_id and entitlement:
                from backend.billing import activate_user_subscription
                activate_user_subscription(
                    user_id=user_id,
                    plan=entitlement,
                    provider="revenuecat",
                    external_sub_id=event.get("transaction_id")
                )
        elif event_type in ["EXPIRATION", "CANCELLATION"]:
            # Handle downgrade logic
            if user_id:
                update_profile(user_id, {
                    "role": "free",
                    "subscription_status": "canceled",
                })
                
        return {"status": "success"}
    except Exception as e:
        logger.error(f"RevenueCat webhook error: {e}")
        raise HTTPException(500, "Internal Server Error")

@app.post("/api/billing/dev-simulate-upgrade")
async def dev_simulate_upgrade(data: dict, user: dict = Depends(require_auth)):
    user_id = user["id"]
    plan = data.get("plan", "pro")
    if plan not in ["free", "pro", "scholar"]:
        raise HTTPException(400, "Invalid plan")
        
    success = activate_user_subscription(
        user_id=user_id,
        plan=plan,
        provider="simulated",
        external_sub_id=f"sim_{user_id}_{plan}"
    )
    if not success:
        raise HTTPException(500, "Failed to update subscription profile")
        
    return {"success": True, "new_role": plan}

# ── Library Endpoints ──────────────────────────────────────────────────────

@app.get("/api/library/texts")
async def get_library_texts():
    texts = []
    if GRETIL_DIR.exists():
        for text_dir in GRETIL_DIR.iterdir():
            if text_dir.is_dir():
                prov_file = text_dir / "provenance.json"
                if prov_file.exists():
                    try:
                        with open(prov_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                            texts.append(metadata)
                    except Exception as e:
                        logger.error(f"Error loading provenance {prov_file}: {e}")
    return {"texts": texts}

@app.get("/api/library/texts/{text_id}")
async def get_library_text_content(text_id: str):
    text_file_path = None
    if GRETIL_DIR.exists():
        for text_dir in GRETIL_DIR.iterdir():
            if text_dir.is_dir():
                prov_file = text_dir / "provenance.json"
                if prov_file.exists():
                    try:
                        with open(prov_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                            if metadata.get("id") == text_id:
                                file_name = metadata.get("file")
                                if file_name:
                                    text_file_path = text_dir / file_name
                                break
                    except Exception as e:
                        logger.error(f"Error loading provenance {prov_file}: {e}")
    
    if not text_file_path or not text_file_path.exists():
        raise HTTPException(404, "Text not found")
        
    return FileResponse(path=str(text_file_path), media_type="text/plain", filename=text_file_path.name)
