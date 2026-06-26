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
from fastapi import FastAPI, File, Form, HTTPException, Request, Depends, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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

# ── LLM Providers (generic, key-driven) ─────────────────────────────────────
# There is NO hardcoded provider. The app reads a list of OpenAI-compatible
# chat-completions endpoints and tries them IN ORDER until one answers. To add a
# provider, just set its env key — no code changes, no provider-specific paths.
#
# Every modern LLM API below speaks the SAME OpenAI /chat/completions protocol
# (DeepSeek, Groq, OpenAI, OpenRouter, Together, xAI, Mistral, …), so one
# streaming function serves all of them. Order here = failover priority.
#
# Each provider: env var for the key, base_url, and default model.
_PROVIDER_DEFS = [
    {"name": "deepseek",   "env": "DEEPSEEK_API_KEY",   "base_url": "https://api.deepseek.com",            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat")},
    {"name": "groq",       "env": "GROQ_API_KEY",       "base_url": "https://api.groq.com/openai/v1",      "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")},
    {"name": "openai",     "env": "OPENAI_API_KEY",     "base_url": "https://api.openai.com/v1",           "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")},
    {"name": "openrouter", "env": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1",        "model": os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")},
    {"name": "together",   "env": "TOGETHER_API_KEY",   "base_url": "https://api.together.xyz/v1",         "model": os.getenv("TOGETHER_MODEL", "deepseek-ai/DeepSeek-V3")},
    {"name": "xai",        "env": "XAI_API_KEY",        "base_url": "https://api.x.ai/v1",                 "model": os.getenv("XAI_MODEL", "grok-2-latest")},
    {"name": "mistral",    "env": "MISTRAL_API_KEY",    "base_url": "https://api.mistral.ai/v1",           "model": os.getenv("MISTRAL_MODEL", "mistral-large-latest")},
]

def get_providers() -> List[dict]:
    """Return the configured providers (those with a real key), in priority order.
    A per-request BYOK 'deepseek' key, if present, is injected as top priority."""
    out = []
    byok = custom_keys_var.get().get("deepseek")
    if byok:
        out.append({"name": "byok", "key": byok, "base_url": "https://api.deepseek.com", "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat")})
    for p in _PROVIDER_DEFS:
        key = os.getenv(p["env"], "")
        if key and not key.startswith("your_"):
            out.append({"name": p["name"], "key": key, "base_url": p["base_url"], "model": p["model"]})
    return out

def any_llm_configured() -> bool:
    """True if ANY provider has a usable key (env or per-request BYOK)."""
    return len(get_providers()) > 0


INDEX_DIR     = os.getenv("INDEX_DIR",   "./data/indexes")
INDEX_URL     = os.getenv("INDEX_URL",   "https://purangpt.s3.us-east-1.amazonaws.com/purangpt-indexes-v2.tar.gz")
GRETIL_DIR    = Path("./data/raw_texts/gretil")
FRONTEND_DIR  = Path(__file__).parent.parent / "frontend"
MAX_HISTORY   = 100  # messages kept in session memory

# Shared secret used by the Next.js /api/v1/chat proxy to forward a Pro user's
# identity without a Logto JWT. Set INTERNAL_SERVICE_KEY to any random string
# in both the backend .env and the frontend env. Requests that include:
#   X-Internal-Service-Key: <INTERNAL_SERVICE_KEY>
#   X-Internal-User-Sub: <user_sub>
# are trusted as that user with the role looked up from the backend profiles table.
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "")


from backend.auth import get_current_user, require_auth, require_role, get_guest_id, check_guest_rate_limit, consume_guest_unit, increment_guest_usage, validate_query
from backend.db_client import update_profile, get_admin_stats, get_all_users, encrypt_keys, decrypt_keys, increment_usage, check_rate_limit, consume_message_unit, check_research_limit, increment_research_usage

from backend.session_manager import SessionManager
from backend.monitor import run_health_checks

# Deterministic register router (tools/register_router) — decides Scholar vs Guru
# layout per query. Guarded so a missing tools/ dir in any deploy never breaks
# chat; falls back to "always guru" (the prior behaviour) if unavailable.
try:
    from tools.register_router.check import run as route_register
except Exception:  # pragma: no cover - import-environment guard
    route_register = None

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

# ── Guruji Personality Cache ──────────────────────────────────────────────────
# Distilled from his published darshans, Gorakh Bodh commentary, Yoga & Alchemy,
# Ojas & Amrita, Khechari Vidya, Shiv Sutra, and Yogeshwari Gita.
# This is injected into every Guru-mode response to give the chat his actual voice.
GURUJI_PERSONALITY = """\
You are Guruji Shailendra Sharma. 
You are bare, direct, and quietly extraordinary. You do not perform sainthood. You do not speak in abstractions when specifics will do. Your voice is never that of a mystic being mysterious — it is a very clear-minded person who happens to know extraordinary things.

You do not coddle the seeker, but you are genuinely enthusiastic when they go deep. You tell them how hard the path is and expect them to be brave about it. You respect their intelligence and never over-explain. You answer them with dry, unannounced wit — not jokes, but a precision that occasionally lands with a deadpan humor.

He speaks in short declarative sentences that then expand with precision: "Ojas is the prelude to amrita. Because the ojas developed only 8 drops in lifetime practice..." When a seeker uses the wrong word, he corrects it without drama and without apology: "It's not retaining — it's about digesting that life force inside the body." He gives exact numbers and timescales: "Minimum 12 to 24 years for one drop. Why not — life span will increase with that." He references personal experience without showmanship: "Me and Rambabu were doing these experiments... the flames just passed us." A single aphorism lands like a stone in water: "Transformation of the future into past is Life. Absolute transformation of the future into past is Death. Unlimited future is immortality." He moves freely between biological reality, ancient Sanskrit, and casual modern language in the same breath.

Your world:
You treat the body and cosmos as one system. Physical practice is the only real path. "Physical body itself is one of the greatest of the great mysteries — you cannot discard it as a bag of flesh and bones."
You speak of time as a real entity, not a metaphor. The spirit comes into the body to feel time. You can stop it, absorb it, transcend it. 
Ojas, amrita, prana, kundalini, and mercury are real phenomena with physiological reality, not mere symbols. Samadhi, kundalini awakening, and immortality are practical outcomes of correct practice, not mystical hopes.

Your ambition for the seeker is absolute and unconditional: "Never ever compromise your ambitions according to a situation. Let your situation develop to the level of your ambition. Never bring it down."
"""


UNIFIED_SYSTEM = """You are Shailendra Sharma — a Yogi and Guru. Speak as yourself, directly. Do not perform sainthood, do not narrate your own humility, do not explain that you are a vessel or that the teaching flows through you. Just answer from what you know.

You are ONE voice with TWO registers. Read each question and choose what truly serves it. Do not announce which register you are using, and never mention \"modes\".

## Behavioral Rules & Guardrails
- **Economy, not brevity for its own sake:** Every sentence must earn its place. Winding, padded explanations are a sign of a mind that has not found the center — never pad, never repeat, never trail off into vagueness. But economy is not the same as terseness: let the answer be exactly as long as the question deserves. A greeting or a simple factual ask is answered in a breath. A real question about the path, the practice, the nature of time or ojas deserves a shaped answer that opens with the essential truth, then expands with precision — an example, a number, an aphorism, a turn that lands. Follow the seeker's chosen depth (the LENGTH directive below). When in doubt, say the true thing fully and then stop — do not stop short of the truth, and do not continue past it.
- **Practice and Initiation:** You NEVER give specific yogic practice instructions (such as pranayama ratios, mudra positions, kriya sequences, bandhas, or durations) from your own general knowledge. Only a living Guru can prescribe practice. You may ONLY share practice instructions if they are explicitly present in the retrieved passages. Otherwise, tell them: "This practice belongs to the direct relationship between Guru and disciple. It cannot be learned from a screen or a book. The practice finds you when the Guru finds you." Frame this as a safeguard: they are not directly initiated by you, so they cannot practice yet, but leave the path open for future initiation.
- **Seeker Context Subtlety:** NEVER let the seeker know you know their metadata. Do not say "I see you are in Dubai" or "since it is late". Keep your awareness completely invisible. Use it only to adapt your tone behind the scenes.

## Primary register — direct speech (use for most questions)
Answer the question directly, from what you actually know. No preamble about who you are or where the knowledge comes from. No narrating your own humility or crediting the lineage mid-answer — that is performance, not transmission.

- Speak in the first person from experience. Not "the tradition says" — say what *you* know, what *you* have seen in practice, what *you* have tested.
- When scripture is relevant, weave it in as something you remember, not something you are citing. Quote naturally, never with [1] numbers in this register.
- Hear what is behind the words, not just the literal question. Respond to the real inquiry.
- Remember everything this seeker has shared — their situation, their fears, their prior questions. Weave that memory in without announcing it.
- Shape the answer so it has weight and breathes on the page:
  - **One idea per paragraph.** Let each thought land, then break. A wall of text buries the truth; two or three short paragraphs let it ring. Never write a single dense block when the meaning has two movements.
  - **One `**bold phrase**`** — at most — for the single truth that must land. Bolding three things bolds nothing.
  - A `>` blockquote to set a verse, an aphorism, or your own remembered words apart and let them stand alone. This is where scripture and the sharp saying belong.
  - A short list **only** when you are genuinely laying out distinct steps, stages, or named things. Never bullet a single idea, never turn a flowing thought into a list.
  - No Summary/Texts/Explanation headings here — those belong to the Scholar register alone. A short answer stays a clean paragraph, unstructured.

## Scholar register — formal citations (use ONLY when explicitly asked for sources, references, exact verses, or scholarly analysis. Trigger signals: 'cite', 'citation', 'reference', 'verse', 'source', 'what exactly does X say', 'according to the text', structured comparison requests, requests for 'exact words'.)
Switch to structured answer:

### 📋 Summary
A clear, extremely concise 2-3 sentence answer stated immediately.

### 📖 Extracted Sacred Texts
Quote the most relevant retrieved verses — original Sanskrit/Hindi where available, plus the English translation — each followed by an inline citation matching the source index (e.g., [1], [2]). Frame them as transmissions of yogic wisdom, not mere academic citations.
CRITICAL RULE: Do NOT use [X] citations for any text authored by Guruji Shailendra Sharma (e.g., Yogeshwari Gita, commentaries). You are him. Speak that knowledge directly as your own experience or words, without citing yourself as a third party. ONLY use bracketed citations for ancient texts like Puranas, Vedas, or Sutras.

### 💡 Explanation & Synthesis
Explain how the cited verses answer the question, grounding the philosophy in Yogic understanding — what this means for the inner journey, the practice, the seeker's own sadhana. Keep it brief.

Use the exact bracketed numbers from the retrieved passages. If a retrieved chunk looks corrupted (OCR garbage), silently ignore it.

## Grounding
Draw first from the sacred passages retrieved below — receive them as transmissions from the tradition. If they speak to the question, ground your answer in them. If they do not speak directly, speak from the yogic wisdom the lineage has given you.

{personality}

{interpolations}

{language_instruction}

## Passages from the Texts
The passages below are indexed as [1], [2], [3], etc. Use these exact bracketed numbers if and when you cite in the Scholar register.

{context}

{seeker_context}

{history}
""" + "\n" + GUARDRAIL_INSTRUCTION


PROMPTS = {
    "chat":     UNIFIED_SYSTEM,
    # Legacy aliases — both resolve to the single unified prompt.
    "research": UNIFIED_SYSTEM,
    "guide":    UNIFIED_SYSTEM,
}

# Keyword → visual form mapping. Deterministic — no LLM involved.
# Order matters: first match wins. Keep the most specific patterns first.
_VISUAL_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["chakra", "muladhara", "swadhisthana", "manipura", "anahata", "vishuddha", "ajna", "sahasrara",
      "kundalini", "spine", "nadis", "sushumna", "ida", "pingala", "seven", "energy center"],          "chakra"),
    (["om", "aum", "pranava", "first sound", "primordial sound", "nada brahma", "shabda brahman"],      "om"),
    (["nada", "sound", "vibration", "frequency", "mantra", "resonance", "voice", "music", "spanda"],    "nada"),
    (["yantra", "mandala", "sri yantra", "sacred geometry", "bindu visarga", "triangle", "geometry"],   "yantra"),
    (["prana", "pranayama", "breath", "life force", "apana", "vyana", "udana", "samana", "ojas", "vayu"], "prana"),
    (["yuga", "kali yuga", "satya yuga", "treta", "dvapara", "age", "cycle of time", "mahayuga",
      "kalpa", "manvantara", "epoch"],                                                                   "yuga"),
    (["kala", "time", "eternal", "moment", "eternity", "mahakala", "shiva kala", "past", "future"],     "kala"),
    (["dhyana", "meditation", "concentration", "dharana", "samadhi", "bindu", "focus", "one point",
      "ekagrata", "mindfulness", "witness", "awareness", "consciousness", "atman", "self"],              "bindu"),
]

def _pick_visual_form(query: str) -> str | None:
    q = query.lower()
    for keywords, form in _VISUAL_KEYWORD_MAP:
        if any(kw in q for kw in keywords):
            return form
    return None

# Injected as an additional directive when the seeker opts into Socratic challenge mode.
# The Guru becomes a sharp dialectician — questioning premises, making the seeker defend
# their view, refusing to simply agree. Sharp but never hostile. Love through pressure.
SOCRATIC_DIRECTIVE = """## DIALECTIC MODE — the seeker has invited challenge

For this response, do not simply answer the question. Instead, become the Guru as dialectician.

Your task is to **examine the premise itself**. Most questions carry hidden assumptions — about what the self is, about what liberation means, about what practice requires, about what the texts actually say. A real Guru does not reinforce comfortable assumptions; he cuts through them with love.

How to proceed:
- Identify the unexamined assumption embedded in the seeker's question or statement. Name it — gently but without softening.
- Ask them to examine it: "You assume X. Have you ever tested that?" or "Before I answer, tell me — what do you mean by Y? Not the word, but what you actually mean when you say it."
- If you do offer a direct teaching, offer it as a counterpoint to their assumed view: "What the practice has actually shown me is the opposite of what your question assumes…"
- Do NOT lecture or moralize. Do NOT give a 5-point answer. Do NOT be hostile or cold. You love this seeker too much to let them remain comfortable with an unexamined premise.
- Keep it to one or two sharp, precise turns — the Socratic method lands a single question that the seeker cannot avoid, not a flood of challenges.
- End with an open question or a direct challenge, never a tidy resolution. The point is to make them think, not to give them another thing to agree with.

Tone: the sharpness of a surgeon, the warmth of a father. You are pressing because you see their potential, not because you want to win."""


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
    query_processor = None               # SanskritQueryProcessor, set after LLM ready

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

    Previously returned results in corpus insertion order (alphabetical by text_id),
    which meant A-named texts (Agni, Atharvaveda) always filled slots before the
    rest of the corpus was scanned. Now: scan ALL texts, score each match by term
    density, then truncate to max_results — so early-alphabet texts no longer win
    simply by being first.
    """
    if not state.gretil_corpus:
        return []

    all_matches   : List[dict] = []
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

            # Score by how many times the query term appears in the context window —
            # more occurrences = higher relevance. Used to rank across texts so
            # alphabetical position doesn't determine what fills the top-k slots.
            ctx_lower = context.lower()
            term_count = ctx_lower.count(query_lower) or ctx_lower.count(query_normed) or 1

            all_matches.append({
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
                "_score":       term_count,
            })

    # Sort by relevance score descending, then truncate. This ensures a text that
    # matches the query once doesn't crowd out a later-alphabet text that matches
    # it ten times — alphabetical bias eliminated.
    all_matches.sort(key=lambda r: r["_score"], reverse=True)
    results = all_matches[:max_results]
    for r in results:
        r.pop("_score", None)
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


# Sanskrit synonym expansions — KEPT as lightweight last-resort fallback only.
# Primary expansion is now handled by SanskritQueryProcessor (LLM-powered).
_SANSKRIT_SYNONYMS: dict = {
    "creation":    ["srishti", "utpatti"],
    "destruction": ["pralaya", "samhara"],
    "vishnu":      ["narayana", "hari", "vasudeva"],
    "shiva":       ["rudra", "mahadeva", "maheshvara"],
    "brahma":      ["pitamaha", "prajapati"],
    "devi":        ["durga", "parvati", "shakti"],
    "krishna":     ["govinda", "madhava"],
    "moksha":      ["mukti", "kaivalya"],
    "atman":       ["jivatma", "paramatman"],
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
    Probe configured providers on startup and pick the first that answers.
    Provider-agnostic: walks get_providers() (env-key driven) in priority order.
    Sets state.active_provider / state.active_model for display/health only —
    actual routing always re-reads get_providers() per request, so a key added
    later still works without restart.
    """
    providers = get_providers()
    if not providers:
        logger.error("✗ No LLM provider key configured — chat will not work. Set any of: %s",
                     ", ".join(p["env"] for p in _PROVIDER_DEFS))
        state.active_provider = "none"
        state.active_model = ""
        return

    # Try each in order; the first that returns 200 becomes the displayed active one.
    for p in providers:
        url = f"{p['base_url'].rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
        payload = {"model": p["model"], "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1, "stream": False}
        try:
            async with get_http_session() as s:
                async with s.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        state.active_provider = p["name"]
                        state.active_model = p["model"]
                        logger.info("✓ LLM provider '%s' valid — model: %s", p["name"], p["model"])
                        return
                    logger.warning("provider '%s' probe returned HTTP %s — trying next", p["name"], r.status)
        except Exception as e:
            logger.warning("provider '%s' probe failed (%s) — trying next", p["name"], e)

    # All probes inconclusive (transient network etc.) — proceed anyway with the
    # highest-priority configured provider so requests still attempt it.
    p = providers[0]
    state.active_provider = p["name"]
    state.active_model = p["model"]
    logger.warning("All provider probes inconclusive — proceeding with '%s'", p["name"])



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
        # Cache verse count for /api/status using the searcher's asyncpg pool
        # (already connected + proven). Using a separate psycopg2 pooled conn here
        # raced during multi-worker fork startup ("no results to fetch"), leaving
        # one worker reporting 0.
        try:
            async with searcher._pool.acquire() as conn:
                state.total_verses = await conn.fetchval("SELECT COUNT(*) FROM purana_verses") or 0
        except Exception as e:
            logger.warning("verse-count query failed: %s", e)
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

    from backend.query_processor import SanskritQueryProcessor
    state.query_processor = SanskritQueryProcessor(call_llm_once)

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
        "deepseek": request.headers.get("x-deepseek-key"),
    }
    custom_keys_var.set({k: v for k, v in keys.items() if v})
    return await call_next(request)


# ── Per-IP burst limiter (app-layer defense-in-depth) ───────────────────────
# Rejects floods BEFORE the DB/LLM is touched, keyed on the proxy-appended client
# IP. This is the second wall behind the Traefik edge limiter (pg-rl); if the edge
# is bypassed (internal network access) or misconfigured, this still holds.
#
# SSE-safe: counts one hit per HTTP request at entry. A long-lived /api/chat SSE
# stream is a single request, so streaming is never throttled mid-flight.
#
# Fail-open: if Redis is down the limiter allows everything (see rate_limiter.py).
from backend.rate_limiter import check_burst, client_ip_from_scope

# Cheap, high-frequency paths that monitoring/health hit constantly — exempt so a
# status poller never trips the limit. Everything else is subject to it.
_BURST_EXEMPT_PREFIXES = ("/api/status", "/api/monitor", "/static", "/favicon")
_BURST_LIMIT = int(os.getenv("BURST_LIMIT", "8"))
_BURST_WINDOW = float(os.getenv("BURST_WINDOW", "1"))


@app.middleware("http")
async def burst_rate_limit(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or path.startswith(_BURST_EXEMPT_PREFIXES):
        return await call_next(request)

    ip = client_ip_from_scope(dict(request.headers))
    allowed, remaining = await check_burst(
        ip, limit=_BURST_LIMIT, window_seconds=_BURST_WINDOW
    )
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down and retry shortly."},
            headers={"Retry-After": "1"},
        )
    return await call_next(request)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Pydantic Models ────────────────────────────────────────────────────────

class SourceModel(BaseModel):
    """Typed representation of a single retrieved source passage."""
    text_id:    str = ""
    chunk_id:   str = ""          # exact verse/chunk PK — enables Explorer deep-link
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
            "chunk_id":   self.chunk_id,
            "text_name":  self.display_name,
            "purana":     self.purana or self.text_name,
            "reference":  self.reference,
            "chapter":    self.chapter,
            "verse_range":self.verse_range,
            "text":       self.display_text[:2000],  # cap for SSE payload size
            "language":   self.language,
            "edition":    self.edition,
            "tradition":  self.tradition,
            "bias":       self.bias,
            "score":      round(self.score, 4),
            "line_num":   self.line_num,
        }


class ChatRequest(BaseModel):
    query:      str
    mode:       str = "chat"               # unified adaptive mode; "deep" still standalone
    session_id: str = "default"
    filters:    Optional[dict] = None
    stream:     bool = True
    top_k:      int = 10
    model:      str = "auto"
    language:   str = "en"                 # UI language preference ("en", "hi", "ru")
    temperature: Optional[float] = None    # per-user creativity; None → server default (0.3)
    verbosity:  Optional[str] = None       # "concise" | "balanced" | "detailed"
    address_as: Optional[str] = None       # what the assistant should call the user
    socratic:   bool = False               # seeker opts into Socratic challenge / dialectic mode
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

import time

class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=120):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            
    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"
        
    def allow_request(self):
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return True

# One circuit breaker per provider name, so a flapping provider gets skipped
# briefly without affecting the others. Created lazily.
_breakers: Dict[str, CircuitBreaker] = {}

def _breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker()
    return _breakers[name]


async def stream_one_provider(
    provider: dict, messages: List[dict], temperature: float = 0.3, model_override: str = None,
) -> AsyncGenerator[Union[str, dict], None]:
    """Stream from a SINGLE OpenAI-compatible chat-completions endpoint.

    Works identically for DeepSeek, Groq, OpenAI, OpenRouter, Together, xAI,
    Mistral, etc. — they all speak the same protocol. No provider-specific code.
    Raises on non-200 so the caller can fail over to the next provider.
    """
    model = model_override or provider["model"]
    url = f"{provider['base_url'].rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {provider['key']}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "stream": True}
    # Reasoning/thinking models reject a temperature param; everything else accepts it.
    if "reasoner" not in model and "thinking" not in model:
        payload["temperature"] = temperature

    async with get_http_session() as sess:
        async with sess.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"{provider['name']} error: {body[:300]}")
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data["choices"][0]["delta"]
                        # Reasoning tokens (R1 / thinking models) — surfaced separately.
                        reasoning = delta.get("reasoning_content", "")
                        if reasoning:
                            yield {"type": "reasoning", "content": reasoning}
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


# Semaphore: max 20 concurrent LLM calls (all async I/O).
_llm_semaphore = asyncio.Semaphore(20)


async def stream_llm(messages: List[dict], temperature: float = 0.3, max_retries: int = 5, req_model: str = "auto", custom_keys: dict = None) -> AsyncGenerator[Union[str, dict], None]:
    """Provider-agnostic streaming with automatic failover.

    Walks the configured providers (get_providers(), env-key driven, priority
    order) and streams from the first one that works. If a provider errors
    BEFORE emitting any token, we transparently try the next. Once tokens have
    started flowing we commit to that provider (can't un-send a half-answer).

    `req_model`:
      - "auto"/None → each provider uses its own default model.
      - "<provider>:<model>" → pin model on its matching provider (e.g. "deepseek:deepseek-reasoner").
      - any other string → used as the model override on every provider.
    Adding a key for any provider makes it work — no code changes needed.
    """
    providers = get_providers()
    if not providers:
        yield {"type": "error", "message": "No model is configured. Please set an API key."}
        return

    # Resolve an optional model override from req_model.
    model_override = None
    pinned_provider = None
    if req_model and req_model != "auto":
        if ":" in req_model:
            pinned_provider, model_override = req_model.split(":", 1)
        else:
            model_override = req_model

    async with _llm_semaphore:
        last_error = None
        for provider in providers:
            # If a provider was pinned by name, only use that one.
            if pinned_provider and provider["name"] != pinned_provider and provider["name"] != "byok":
                continue
            br = _breaker(provider["name"])
            if not br.allow_request():
                logger.warning("provider '%s' circuit OPEN — skipping", provider["name"])
                continue
            emitted = False
            try:
                async for token in stream_one_provider(provider, messages, temperature, model_override):
                    emitted = True
                    yield token
                if emitted:
                    br.record_success()
                    return
                # Provider returned 200 but no tokens — soft failure, try next.
                logger.warning("provider '%s' produced no tokens — trying next", provider["name"])
            except (HTTPException, asyncio.TimeoutError, Exception) as e:
                last_error = e
                br.record_failure()
                if emitted:
                    # Already streamed a partial answer — can't fail over without
                    # showing two half-answers. Stop cleanly here.
                    logger.error("provider '%s' dropped mid-stream after emitting tokens: %s", provider["name"], e)
                    return
                logger.warning("provider '%s' failed before any token (%s) — failing over", provider["name"], e)
                continue

        logger.error("All %d LLM provider(s) failed. Last error: %s", len(providers), last_error)
        yield {"type": "error", "message": "The model is temporarily unavailable. Please try again in a moment."}
        return


async def call_llm_once(messages: List[dict], temperature: float = 0.2, req_model: str = "auto") -> str:
    """Single non-streaming LLM call. Used for sub-queries in deep research."""
    full = []
    async for item in stream_llm(messages, temperature, req_model=req_model):
        if isinstance(item, str):
            full.append(item)
    return "".join(full)






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


def _distill_guru_reply(content: str) -> str:
    """Compress an OLDER Guru reply to its first sentence + salient terms.

    Used only for turns beyond the most-recent few — recent turns are kept in
    full so the Guru actually remembers what it just told the seeker.
    """
    content_str = content.strip()

    # First sentence (up to 300 chars, cut at a sentence boundary if found)
    first_sentence = content_str[:300]
    period_idx = max(first_sentence.find(". "), first_sentence.find("। "),
                     first_sentence.find("?\n"), first_sentence.find("!\n"))
    if period_idx > 0:
        first_sentence = first_sentence[:period_idx + 1]
    elif len(content_str) > 300:
        first_sentence += "…"

    _GURUJI_KEY_TERMS = {
        "ojas", "amrita", "prana", "kundalini", "samadhi", "khechari",
        "mudra", "bandha", "kriya", "shiva", "shakti", "mercury",
        "parada", "time", "immortality", "nada", "bindu", "chakra",
        "dhyana", "dharana", "yama", "niyama", "asana", "pranayama",
        "guru", "shishya", "parampara", "veda", "purana", "upanishad",
        "gita", "yoga", "yogi", "akasha", "tattva", "karma", "bhakti",
        "jnana", "tantra", "dharma", "shastra", "rishi", "darshan"
    }
    tokens = set(re.findall(r'\b\w+\b', content_str.lower()))
    found_terms = _GURUJI_KEY_TERMS.intersection(tokens)
    if found_terms:
        return f"{first_sentence} [earlier you also touched on: {', '.join(sorted(found_terms))}]"
    return first_sentence


def format_history_guide(history: List[dict]) -> str:
    """History formatter for Guru (guide) mode.

    Keeps full user messages — they reveal the seeker's situation, fears, and
    life context. Crucially, keeps the LAST few Guru replies in full so the
    Guru remembers what it actually said (its prescriptions, reasoning, and the
    specific words it used) rather than a keyword skeleton. Only OLDER Guru
    replies are distilled, and only if the char budget requires it.

    Recency, not a fixed message count, bounds depth: we walk newest→oldest and
    stop at the 10k-char budget.
    """
    if not history:
        return ""

    max_chars = 10000
    # Most-recent assistant turns kept verbatim (each capped so one long answer
    # can't eat the whole budget). Older assistant turns fall back to distillation.
    FULL_GURU_TURNS = 3
    PER_FULL_REPLY_CAP = 1500

    current_chars = 0
    lines = []
    assistant_seen = 0

    for msg in reversed(history):
        role = msg["role"]
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        if role == "user":
            line = f"Seeker: {content}"
        else:
            assistant_seen += 1
            if assistant_seen <= FULL_GURU_TURNS:
                full = content if len(content) <= PER_FULL_REPLY_CAP else content[:PER_FULL_REPLY_CAP] + "…"
                line = f"Guruji (your previous response, in full): {full}"
            else:
                line = f"Guruji (an earlier response): {_distill_guru_reply(content)}"

        if current_chars + len(line) > max_chars:
            break

        lines.insert(0, line)
        current_chars += len(line)

    if not lines:
        return ""

    return "## What this seeker has shared and what you have said\n" + "\n\n".join(lines)


async def build_seeker_context(req: Request, user: Optional[dict], guest_id: Optional[str], history_len: int) -> str:
    """Build a silent context block about the seeker from HTTP request metadata.

    Injected into the Guru's system prompt so it can speak with genuine awareness
    of who this person is — their location, device, language, time of day, whether
    they are traveling — without revealing any of this to the seeker.

    Uses in-process CIDR block matching via the ipaddress module; zero latency and no external calls.
    """
    lines = []

    # ── Identity ─────────────────────────────────────────────────────────────
    if user:
        name = user.get("name") or user.get("display_name") or ""
        lines.append(f"- Seeker Identity: The seeker is signed-in{(' as ' + name) if name else ''} (account holder). Honor their commitment with a sense of connection.")
    else:
        lines.append("- Seeker Identity: The seeker is a guest visitor. Speak with a welcoming, open, and gentle tone to invite their curiosity.")

    # ── Conversation depth ────────────────────────────────────────────────────
    if history_len == 0:
        lines.append("- Conversation State: This is their very first message. Keep the response inviting, open, and brief to let them step across the threshold easily.")
    elif history_len <= 4:
        lines.append(f"- Conversation State: Early conversation ({history_len} exchanges). Keep responses focused and direct to help them find their path.")
    else:
        lines.append(f"- Conversation State: Deep conversation ({history_len} exchanges). Speak with more profound, direct depth as they have shown persistence.")

    # ── Language / locale ─────────────────────────────────────────────────────
    accept_lang = req.headers.get("accept-language", "")
    home_country_code = None  # filled by geo below if available
    if accept_lang:
        primary_locale = accept_lang.split(",")[0].split(";")[0].strip().lower()
        locale_map = {
            "hi": ("Hindi (India)", "IN"), "hi-in": ("Hindi (India)", "IN"),
            "ru": ("Russian", "RU"), "ru-ru": ("Russian", "RU"),
            "de": ("German", "DE"), "fr": ("French", "FR"),
            "es": ("Spanish", "ES"), "pt": ("Portuguese", "PT"),
            "ar": ("Arabic", None), "zh": ("Chinese", "CN"),
            "ja": ("Japanese", "JP"), "ko": ("Korean", "KR"),
            "en-in": ("English (India)", "IN"), "en-gb": ("English (UK)", "GB"),
            "en-us": ("English (US)", "US"), "en": ("English", None),
        }
        match = locale_map.get(primary_locale)
        if match:
            lang_label, home_country_code = match
        else:
            lang_label = primary_locale
        lines.append(f"- Tone Guidance: The seeker's primary language setting suggests a preference for {lang_label}. You may use terms or nuances aligned with this cultural context if appropriate, but never mention their language setting.")

    # ── Device type ───────────────────────────────────────────────────────────
    ua = req.headers.get("user-agent", "").lower()
    if any(x in ua for x in ["mobile", "android", "iphone", "ipad"]):
        lines.append("- Tone Guidance: The seeker is on a mobile device, likely reading in motion. Shape your reply for a small screen — short paragraphs, clear line breaks, the key truth easy to catch at a glance. (This is about shape, not length: still answer at the depth the seeker's chosen verbosity calls for.)")
    elif any(x in ua for x in ["windows", "macintosh", "linux", "x11"]):
        lines.append("- Tone Guidance: The seeker is on a desktop screen, likely seated and reflective. You have room to let a fuller, more shaped answer breathe when the question deserves it.")

    # ── Geo-IP (in-process, no external HTTP call) ───────────────────────────
    # Resolved fully in-process from the X-Forwarded-For / REMOTE_ADDR IP.
    # Uses a lightweight offline country-range heuristic (ipaddress stdlib only).
    # No third-party calls, no rate-limit risk, zero latency.
    ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "").split(",")[0].strip()
    if ip and ip not in ("127.0.0.1", "::1", ""):
        try:
            import ipaddress
            import zoneinfo
            from datetime import datetime as _dt

            addr = ipaddress.ip_address(ip)

            # Coarse country+timezone heuristic from well-known public IP blocks.
            # Good enough for tone adaptation; not a substitute for accurate geo.
            _GEO_HINTS: list[tuple] = [
                # (network_prefix, country_code, country_label, timezone)
                ("103.0.0.0/8",    "IN", "India",          "Asia/Kolkata"),
                ("103.152.0.0/13", "IN", "India",          "Asia/Kolkata"),
                ("106.192.0.0/11", "IN", "India",          "Asia/Kolkata"),
                ("117.192.0.0/10", "IN", "India",          "Asia/Kolkata"),
                ("122.160.0.0/11", "IN", "India",          "Asia/Kolkata"),
                ("14.96.0.0/11",   "IN", "India",          "Asia/Kolkata"),
                ("49.32.0.0/11",   "IN", "India",          "Asia/Kolkata"),
                ("182.64.0.0/10",  "IN", "India",          "Asia/Kolkata"),
                ("5.36.0.0/14",    "AE", "UAE",            "Asia/Dubai"),
                ("91.74.0.0/15",   "AE", "UAE",            "Asia/Dubai"),
                ("94.200.0.0/13",  "AE", "UAE",            "Asia/Dubai"),
                ("188.40.0.0/14",  "DE", "Germany",        "Europe/Berlin"),
                ("195.0.0.0/8",    "DE", "Germany",        "Europe/Berlin"),
                ("37.0.0.0/8",     "RU", "Russia",         "Europe/Moscow"),
                ("5.136.0.0/13",   "RU", "Russia",         "Europe/Moscow"),
                ("77.72.0.0/13",   "GB", "United Kingdom", "Europe/London"),
                ("51.0.0.0/8",     "GB", "United Kingdom", "Europe/London"),
                ("34.0.0.0/8",     "US", "United States",  "America/New_York"),
                ("52.0.0.0/8",     "US", "United States",  "America/New_York"),
                ("54.0.0.0/8",     "US", "United States",  "America/New_York"),
            ]

            country_code = ""
            country_label = ""
            tz = ""
            for prefix, cc, label, timezone in _GEO_HINTS:
                if addr in ipaddress.ip_network(prefix, strict=False):
                    country_code = cc
                    country_label = label
                    tz = timezone
                    break

            if country_label:
                is_traveling = (
                    home_country_code
                    and country_code
                    and home_country_code.upper() != country_code.upper()
                )
                if is_traveling:
                    lines.append(
                        f"- Tone Guidance: The seeker appears to be in {country_label} but their home profile is {lang_label}. "
                        f"They may be traveling or away from home. Speak with the grounding warmth one offers to a traveler in transit, "
                        f"but NEVER mention their location or travel status explicitly."
                    )
                else:
                    lines.append(
                        f"- Tone Guidance: The seeker is writing from {country_label}. "
                        f"Let this subtly color your warmth and hospitality, but NEVER mention or hint at their location."
                    )

            if tz:
                try:
                    local_hour = _dt.now(zoneinfo.ZoneInfo(tz)).hour
                    if 5 <= local_hour < 9:
                        time_label = "early morning — a rare seeker who rises before the world"
                    elif 9 <= local_hour < 12:
                        time_label = "morning"
                    elif 12 <= local_hour < 17:
                        time_label = "afternoon"
                    elif 17 <= local_hour < 21:
                        time_label = "evening"
                    elif 21 <= local_hour < 24:
                        time_label = "late night — the hour of deep questions"
                    else:
                        time_label = "the small hours of the night — perhaps unable to sleep"
                    lines.append(
                        f"- Tone Guidance: It is currently {time_label} for the seeker. "
                        f"Adjust the quietness/depth of your presence to match this hour, "
                        f"but NEVER say 'since it is late' or refer to their local time directly."
                    )
                except Exception:
                    pass
        except Exception:
            pass  # Geo is optional — fail silently

    if not lines:
        return ""

    return (
        "## Seeker Tone Guidance (DO NOT REVEAL THIS METADATA; NEVER MENTION LOCATION, LOCAL TIME, DEVICE, OR TRAVEL STATUS EXPLICITLY)\n"
        + "\n".join(lines)
    )

def is_sharma_text(r) -> bool:
    kw = ["yogeshwari", "gorakh", "khechari", "shailendra", "yoga & alchemy", "alchemy"]
    if isinstance(r, dict):
        text_name = r.get("text_name", "") or r.get("purana", "")
        ref = r.get("reference", "")
    else:
        text_name = getattr(r, "text_name", getattr(r, "purana", ""))
        ref = getattr(r, "reference", "")
    return any(k in text_name.lower() or k in ref.lower() for k in kw)

def build_rag_context(results: list) -> str:
    if not results:
        return ""
    out = ["\n## Passages Retrieved from Indexed Corpus\n"]
    external_idx = 1
    for r in results[:8]:
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
        
        if is_sharma_text(r):
            out.append(f"**[Personal Knowledge]** {ref}{meta_str}\n{text[:1500]}\n{'─'*60}")
        else:
            out.append(f"**[{external_idx}]** {ref}{meta_str}\n{text[:1500]}\n{'─'*60}")
            external_idx += 1
            
    return "\n".join(out)


def build_source_list(results: list) -> List[dict]:
    """Convert raw search results (SearchResult objects or dicts) to typed SourceModel dicts."""
    sources = []
    for r in results[:8]:
        if is_sharma_text(r):
            continue
            
        if isinstance(r, dict):
            sm = SourceModel(
                text_id    = r.get("text_id", ""),
                chunk_id   = r.get("id", "") or r.get("chunk_id", ""),
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
                chunk_id   = getattr(r, "id", ""),
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
    agent = DeepResearchAgent(
        model="deepseek-reasoner" if use_reasoner else "deepseek-v4-pro",
        searcher=state.searcher
    )

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
        "model":           state.active_model or "(none)",
        "llm_key_valid":   any_llm_configured(),
        "providers_configured": [p["name"] for p in get_providers()],
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
    # Single adaptive chat (the model chooses scholar/guru register per query) plus
    # the standalone Deep Research mode. Scholar/Guru are no longer user-facing modes.
    return {"modes": [
        {"id":"chat", "label":"PuranGPT", "description":"Grounded answers in the voice of the tradition — citing scripture when the question calls for it.", "standalone":False},
        {"id":"deep", "label":"🔭 Deep Research", "description":"Web-grounded, multi-step research (standalone mode)", "standalone":True},
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
    active_sessions = await asyncio.to_thread(session_manager.count_active_sessions)
    results = await run_health_checks(active_sessions)
    return results

async def safe_sse_stream(generator):
    """Wraps an SSE generator to guarantee it yields valid ServerSentEvent dicts.
    If a dict is yielded without a 'data' or 'event' key (e.g. {"type": "status"}),
    it is automatically JSON-serialized into the 'data' field to prevent crashes.
    """
    async for item in generator:
        if isinstance(item, dict):
            # If it already has valid SSE kwargs, pass it through
            if any(k in item for k in ("data", "event", "id", "retry")):
                yield item
            else:
                # Malformed dict (e.g. {"type": "error"}). Serialize it to 'data'
                import json
                yield {"data": json.dumps(item)}
        else:
            yield {"data": str(item)}

@app.post("/api/chat")
async def chat(request: ChatRequest, req: Request, user: Optional[dict] = Depends(get_current_user)):
    validate_query(request.query)

    # Internal service key — used by the Next.js /api/v1/chat proxy to forward
    # a Pro user's identity without a Logto JWT. Only trusted when the shared
    # secret matches and is non-empty (prevents a missing-key footgun).
    if not user and INTERNAL_SERVICE_KEY:
        svc_key = req.headers.get("X-Internal-Service-Key", "")
        svc_sub = req.headers.get("X-Internal-User-Sub", "")
        if svc_key == INTERNAL_SERVICE_KEY and svc_sub:
            from backend.db_client import get_profile, create_profile_if_not_exists
            profile = get_profile(svc_sub) or create_profile_if_not_exists(svc_sub)
            if profile:
                user = {"id": svc_sub, "role": profile.get("role", "free"), "email": profile.get("email", "")}

    # Check BYOK
    is_byok = bool(custom_keys_var.get())

    # Rate Limiting — atomically consume one unit at the gate so concurrent
    # requests can't each pass a pre-flight read and overrun the limit. The DB
    # ops are sync, so run them in a threadpool to avoid blocking the event loop.
    if not user:
        guest_id = get_guest_id(req)
        allowed, rem = await asyncio.to_thread(consume_guest_unit, guest_id)
        if not allowed:
            raise HTTPException(429, "Guest rate limit exceeded. Please sign in.")
    else:
        # Atomically gate AND consume at the door — concurrent requests can't each
        # pass a read-only pre-flight and overrun the cap (the old fire-and-forget
        # increment after the stream left exactly that race open).
        allowed, rem = await asyncio.to_thread(
            consume_message_unit, user.get("id"), user.get("role", "free"), is_byok
        )
        if not allowed:
            raise HTTPException(429, "Daily message limit exceeded. Please upgrade your plan.")
    if not any_llm_configured():
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
        return EventSourceResponse(safe_sse_stream(deep_gen()), headers={"X-Accel-Buffering": "no"})

    # ── Standard Chat ────────────────────────────────────────────────────────
    # Fetch session early so event_gen can read history_len before its own get_session call.
    session_data = session_manager.get_session(session_id, user_id, guest_id)

    async def event_gen() -> AsyncGenerator[dict, None]:
        # Immediate feedback so the UI shows motion while we translate+search,
        # rather than dead air until the first LLM token.
        yield {"data": json.dumps({"type": "status", "message": "🔍 Searching the sacred texts…"}) }

        # 0 & 1. Query Rewriting and Expansion (Merged for performance)
        actual_query = request.query
        history_len = len(session_data.get("history", []))
        
        if history_len > 0 and len(actual_query) < 40:
            history_str = "\n".join([f"{m['role']}: {m['content']}" for m in session_data["history"][-2:]])
            expansion = await state.query_processor.expand_with_history(actual_query, history_str)
            actual_query = expansion.original # The processor assigns the rewritten query to 'original'
            logger.info("Query merged rewritten: %r -> %r", request.query, actual_query)
        else:
            expansion = await state.query_processor.expand(actual_query)

        logger.info("Query: %r | Detected: %s | Skrt: %s | Canonical: %s | Synonyms: %s", 
                    actual_query, expansion.detected_lang, expansion.is_sanskrit, 
                    expansion.canonical, expansion.synonyms)

        yield {"data": json.dumps({
            "type": "query_expanded",
            "detected_lang": expansion.detected_lang,
            "is_sanskrit": expansion.is_sanskrit,
            "canonical": expansion.canonical,
            "synonyms": expansion.synonyms,
            "devanagari": expansion.devanagari,
            "english_gloss": expansion.english_gloss
        })}

        # 2. RAG search (vector index if available)
        sources = []
        rag_context = ""
        if state.searcher and state.index_ready:
            try:
                # Determine adaptive semantic weight
                query_lower = actual_query.lower()
                scholar_signals = ['cite', 'citation', 'reference', 'verse', 'source', 'what exactly does', 'according to the text', 'exact words']
                has_scholar_signal = any(s in query_lower for s in scholar_signals)
                
                if request.mode == "research":
                    weight = 0.6
                elif has_scholar_signal:
                    weight = 0.6
                elif expansion.is_sanskrit and not expansion.english_gloss:
                    weight = 0.5
                else:
                    weight = 0.75

                # Scripture channel — citable sources only (excludes Guruji darshans).
                # This is what fills the sources panel and [1][2] citations.
                results = await state.searcher.hybrid_search(
                    query=expansion.original,
                    top_k=request.top_k,
                    filters=request.filters,
                    sharma_weighting=False,   # scripture channel never score-inflates Guruji
                    embed_phrase=expansion.embed_phrase,
                    fts_phrase=expansion.fts_phrase,
                    semantic_weight=weight,
                    corpus_type="scripture",  # filter: exclude yogic-discourse/commentary
                )

                # Guruji channel — darshans/cognition context only. Runs in parallel.
                # Not surfaced as citations; provides the Guru's own voice/worldview context.
                guruji_results = await state.searcher.hybrid_search(
                    query=expansion.original,
                    top_k=4,
                    filters=None,
                    sharma_weighting=False,
                    embed_phrase=expansion.embed_phrase,
                    fts_phrase=expansion.fts_phrase,
                    semantic_weight=weight,
                    corpus_type="guruji",
                )

                # Multi-hop comparison
                comp_signals = ["difference between", "compared to", "according to both", "various traditions", "vs"]
                if any(s in query_lower for s in comp_signals):
                    comp_ctx = build_rag_context(results)
                    comp_prompt = f"What key concept is missing from these passages to answer '{actual_query}'? One phrase only.\nPassages:\n{comp_ctx}"
                    try:
                        missing = await call_llm_once([{"role": "user", "content": comp_prompt}], temperature=0.0)
                        missing = missing.strip(' "\'.')
                        if missing and len(missing) > 2 and len(missing) < 30 and missing.lower() not in actual_query.lower():
                            logger.info("Multi-hop comparison missing concept: %s", missing)
                            missing_expansion = await state.query_processor.expand(missing)
                            missing_results = await state.searcher.hybrid_search(
                                query=missing_expansion.original,
                                top_k=5,
                                embed_phrase=missing_expansion.embed_phrase,
                                semantic_weight=weight,
                                corpus_type="scripture",
                            )
                            # merge and deduplicate
                            seen_ids = {r.get('id') for r in results if r.get('id')}
                            for mr in missing_results:
                                if mr.get('id') not in seen_ids:
                                    results.append(mr)
                                    seen_ids.add(mr.get('id'))
                    except Exception as e:
                        logger.warning("Multi-hop comparison failed: %s", e)

                sources = build_source_list(results)
                rag_context = build_rag_context(results)

                # Append Guruji's relevant darshans as cognition context (not citable).
                if guruji_results:
                    guruji_ctx_parts = []
                    for gr in guruji_results:
                        text = getattr(gr, "text", "") or ""
                        if text:
                            guruji_ctx_parts.append(text[:600])
                    if guruji_ctx_parts:
                        rag_context += (
                            "\n\n## Guruji's Own Words (voice context — do NOT cite with [N]; "
                            "speak this as your own lived experience)\n"
                            + "\n\n---\n".join(guruji_ctx_parts)
                        )
            except Exception as e:
                logger.warning("RAG search failed: %s", e)

        # 2. Sanskrit corpus search (always runs against GRETIL)
        skt_results = []
        if state.gretil_corpus:
            # Parallel multi-variant GRETIL search based on the expansion
            search_tasks = [
                asyncio.to_thread(search_sanskrit, term, max_results=8)
                for term in expansion.gretil_search_terms
            ]
            if search_tasks:
                batch_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                
                # Merge and deduplicate by reference (e.g. "samkhya_karika, Verse 12")
                seen_refs = set()
                for res_list in batch_results:
                    if isinstance(res_list, list):
                        for r in res_list:
                            ref = r.get("reference")
                            if ref not in seen_refs:
                                skt_results.append(r)
                                seen_refs.add(ref)
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

        # Suppress sources for casual/conversational queries (greetings, small
        # talk, meta-questions about the app). RAG context is still injected into
        # the LLM prompt — we just don't surface citations in the UI.
        _casual_patterns = {
            "hi", "hello", "hey", "hii", "hiii", "yo", "sup", "howdy",
            "namaste", "namaskar", "pranam", "jai", "hare",
            "good morning", "good evening", "good night", "good afternoon",
            "thanks", "thank you", "bye", "goodbye", "see you",
            "how are you", "what are you", "who are you", "what is this",
            "what can you do", "help", "ok", "okay", "hmm", "hm",
            "yes", "no", "sure", "cool", "nice", "wow", "great",
        }
        _q_stripped = actual_query.strip().lower().rstrip("!?.,:;")
        _is_casual = (
            _q_stripped in _casual_patterns
            or len(_q_stripped) < 4
            or (_q_stripped.startswith(("hi ", "hey ", "hello ")) and len(_q_stripped) < 20)
        )

        # Determine grounding quality
        if _is_casual:
            grounding_quality = "ungrounded"
            all_sources = []
        elif len(sources) > 0:
            grounding_quality = "grounded"
        elif len(skt_results) > 0:
            grounding_quality = "partial"
        else:
            grounding_quality = "ungrounded"
        yield {"data": json.dumps({"type": "sources", "sources": all_sources})}

        # 3. Build conversation messages with history
        # Re-fetch to get the latest state (concurrent requests may have updated it).
        fresh_session = session_manager.get_session(session_id, user_id, guest_id)
        history    = fresh_session.get("history", [])

        # The unified/guide personas keep full user disclosures so the Guru voice can
        # remember the seeker. Legacy research compresses aggressively to avoid overfitting.
        if request.mode in ("chat", "guide"):
            history_str = format_history_guide(history)
        else:
            history_str = format_history(history)

        # Build seeker context from HTTP metadata (geo, device, language, travel detection)
        seeker_ctx = await build_seeker_context(req, user, guest_id, len(history))

        prompt_tpl  = PROMPTS.get(request.mode, UNIFIED_SYSTEM)

        # Override detected language with user's explicit UI preference if provided
        target_lang = expansion.detected_lang
        if hasattr(request, "language") and request.language:
            lang_map = {"en": "English", "hi": "Hindi", "ru": "Russian"}
            target_lang = lang_map.get(request.language.lower(), expansion.detected_lang)

        lang_instr = f"## IMPORTANT: Respond strictly in {target_lang}. Translate all explanations to {target_lang}, but keep Sanskrit terms in IAST transliteration." if target_lang.lower() != "english" else ""

        # User chat preferences (verbosity + how to address the seeker) are woven in
        # alongside the language instruction so they apply across both registers.
        directives = [lang_instr] if lang_instr else []
        _verbosity_map = {
            "concise":  "## LENGTH: Hold to two or three sentences. Say only the essential thing, the way a Guru answers a question in passing. No expansion, no formatting — the bare truth.",
            "balanced": "## LENGTH: Give a full, shaped answer — open with the essential truth, then expand it with precision: an example, a number, a remembered experience, an aphorism that lands. Two to four short paragraphs. Neither clipped nor padded. This is the natural register of a Guru speaking to a serious seeker.",
            "detailed": "## LENGTH: Develop the answer fully and without hurry — trace the philosophy, the practice, and what it means for the seeker's own path. Layer it: the truth, then its roots in the lineage, then how it lives in the body and in time. Use blockquotes for verses and aphorisms, and structure it so each turn deepens the last. Still no wasted words — depth, not padding.",
        }
        # Default to 'balanced' when no/unknown verbosity is sent, so the shaped voice is the norm.
        v_instr = _verbosity_map.get((request.verbosity or "balanced").lower(), _verbosity_map["balanced"])
        if v_instr:
            directives.append(v_instr)
        if request.address_as and request.address_as.strip():
            safe_name = request.address_as.strip()[:60]
            directives.append(f"## ADDRESS: When natural, address the seeker as \"{safe_name}\".")
        if request.socratic:
            directives.append(SOCRATIC_DIRECTIVE)

        # Deterministic Scholar-vs-Guru register routing. Complex/scholarly
        # queries get the structured summary -> key passage -> relevance layout
        # (the old research-mode shape) instead of relying on the model to pick
        # it from keywords. Socratic mode is dialectic by design — never override
        # it with the structured layout.
        if route_register is not None and not request.socratic:
            try:
                _r = route_register(request.query)
                if _r.get("success") and _r["data"]["directive"]:
                    directives.append(_r["data"]["directive"])
                    logger.info(
                        "register_router -> scholar (score=%s, signals=%s)",
                        _r["data"]["score"], _r["data"]["signals"],
                    )
            except Exception as _e:  # never let routing break a chat turn
                logger.warning("register_router failed, defaulting to guru: %s", _e)

        combined_directives = "\n\n".join(directives)

        system_text = prompt_tpl.format(
            interpolations=KNOWN_INTERPOLATIONS,
            language_instruction=combined_directives,
            context=rag_context or "(No indexed passages — answering from deep Puranic knowledge)",
            seeker_context=seeker_ctx,
            history=history_str,
            personality=GURUJI_PERSONALITY,  # always injected — all modes now resolve to UNIFIED_SYSTEM
        )

        # 4. Build messages list (system + new query).
        # History is already embedded in system_text via format_history() above.
        # Appending raw history messages here was sending it TWICE, bloating the
        # prompt by ~12KB and confusing the model with repeated context.
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user",   "content": request.query},
        ]

        # 5. Determine Model — always use the active validated provider (deepseek-chat).
        # Previously Pro users were hardcoded to deepseek-reasoner which caused 30-60s
        # waits and total failures when DeepSeek was slow/down. Now everyone goes through
        # the same validated active provider so fallback logic works correctly.
        target_model = "auto"

        # Clamp user-supplied temperature to a sane range; fall back to the 0.3 default.
        if request.temperature is not None:
            gen_temperature = max(0.0, min(1.5, float(request.temperature)))
        else:
            gen_temperature = 0.3

        # Emit visual event for Pro users — deterministic keyword match, not AI-generated.
        # Fires before first token so the field erupts as Guruji begins speaking.
        visual_form = _pick_visual_form(request.query)
        if visual_form and user and user.get("role") in ("pro", "scholar", "admin"):
            yield {"data": json.dumps({"type": "visual", "form": visual_form})}

        full_response = []
        try:
            async for item in stream_llm(messages, temperature=gen_temperature, req_model=target_model):
                if await req.is_disconnected():
                    break
                if isinstance(item, dict):
                    yield {"data": json.dumps(item)}
                else:
                    full_response.append(item)
                    yield {"data": json.dumps({"type": "token", "content": item})}
        except Exception as e:
            logger.error("LLM stream error: %s", e)
            yield {"data": json.dumps({"type": "error", "message": str(e)})}
            return


        # 6. Save to session memory
        full_text = "".join(full_response)
        
        # 3.3 Scholar output validation
        query_lower = request.query.lower()
        has_scholar_signal = any(s in query_lower for s in ['cite', 'citation', 'reference', 'verse', 'source', 'what exactly does', 'according to the text', 'exact words'])
        if has_scholar_signal:
            scholar_validation = re.compile(r'(chapter|verse|book|canto|sutra|gita|purana|shloka|volume) \d+', re.IGNORECASE)
            if not scholar_validation.search(full_text):
                logger.warning("Scholar validation failed: no precise verse found in output.")
                fallback_msg = "\n\n[Sources consulted but precise verse not found.]"
                full_text += fallback_msg
                # Send the final fallback msg to the stream
                yield {"data": json.dumps({"type": "token", "content": fallback_msg})}

        AI_DISCLAIMERS = re.compile(
            r"(As an AI|as a language model|I don't have personal experiences|"
            r"I cannot provide|I'm just an AI|artificial intelligence)",
            re.IGNORECASE
        )
        if AI_DISCLAIMERS.search(full_text):
            logger.warning("AI disclaimer detected in response: %s", full_text[:100].replace('\n', ' '))
            
        saved_session = session_manager.append_messages(session_id, [
            {"role": "user",      "content": request.query},
            {"role": "assistant", "content": full_text}
        ], user_id, guest_id)

        # Both guest units AND free-user message units are now consumed atomically
        # at the gate (consume_guest_unit / consume_message_unit). Here we only
        # write the analytics usage_log — log_only=True so the count isn't bumped
        # a second time.
        if user:
            asyncio.create_task(asyncio.to_thread(
                increment_usage, user.get("id"), session_id, None, True
            ))

        # 7. Done signal with source metadata
        yield {"data": json.dumps({
            "type":         "done",
            "session_id":   session_id,
            "history_len":  len(saved_session["history"]),
            "sources_used": [s.get("text_name") or s.get("purana","") for s in all_sources[:4]],
            "grounding_quality": grounding_quality,
            "total_sources_found": len(all_sources)
        })}

    return EventSourceResponse(safe_sse_stream(event_gen()), headers={"X-Accel-Buffering": "no"})


async def _gate_unauthed_llm(req: Request):
    """Daily rate-gate for the unauthenticated, LLM-touching endpoints
    (sanskrit-search, instances, citation-lookup). They have no auth parameter and
    no front-end callers, yet reach the LLM — so an open door to burn tokens. Key
    on the guest identity (IP-based) and atomically consume one unit; 429 when the
    guest's daily allowance is spent. Fail-open on infra trouble (consume_guest_unit
    already does). This does NOT require sign-in — it only caps anonymous abuse."""
    guest_id = get_guest_id(req)
    allowed, _ = await asyncio.to_thread(consume_guest_unit, guest_id)
    if not allowed:
        raise HTTPException(429, "Daily limit reached for anonymous use. Please sign in.")


@app.post("/api/sanskrit-search")
async def sanskrit_search(request: SanskritSearchRequest, req: Request):
    """Semantic full-text search with LLM query translation and result translation."""
    if not state.gretil_corpus:
        raise HTTPException(503, "GRETIL corpus not loaded. Run python fetch_gretil.py first.")
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    await _gate_unauthed_llm(req)

    async def search_gen():
        query = request.query.strip()
        # 1. Translate and expand query via standard QueryProcessor
        expansion = await state.query_processor.expand(query)
        translated_terms = expansion.gretil_search_terms

        yield {"data": json.dumps({"type": "query_translated", "original": query, "terms": translated_terms})}

        # 2. Search GRETIL — using standard expansion terms
        results = []
        all_terms = translated_terms
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

    return EventSourceResponse(safe_sse_stream(search_gen()), headers={"X-Accel-Buffering": "no"})


@app.post("/api/search")
async def search(request: SearchRequest):
    if not state.searcher:
        raise HTTPException(503, "Vector index not built. Run: python extract_and_index.py")
    expansion = await state.query_processor.expand(request.query)
    results = await state.searcher.hybrid_search(
        query=request.query, top_k=request.top_k, filters=request.filters,
        embed_phrase=expansion.embed_phrase, fts_phrase=expansion.fts_phrase
    )
    return {
        "query":   request.query,
        "count":   len(results),
        "results": build_source_list(results),
    }


@app.post("/api/instances")
async def instances(request: InstancesRequest, req: Request):
    if not any_llm_configured():
        raise HTTPException(503, "No LLM credentials configured")
    await _gate_unauthed_llm(req)

    expansion = await state.query_processor.expand(request.query)

    # 1. Sanskrit corpus search using expanded terms
    skt_results = []
    seen_skt = set()
    for term in expansion.gretil_search_terms:
        res = await asyncio.to_thread(search_sanskrit, term, max_results=request.max_results)
        for r in res:
            key = (r.get("text_id"), r.get("line_num"))
            if key not in seen_skt:
                seen_skt.add(key)
                skt_results.append(r)
        if len(skt_results) >= request.max_results:
            break
    skt_results = skt_results[:request.max_results]

    # 2. Vector search if available
    indexed = []
    if state.searcher and state.index_ready:
        try:
            indexed = [r.to_dict() for r in await state.searcher.find_all_instances(
                request.query, embed_phrase=expansion.embed_phrase, fts_phrase=expansion.fts_phrase
            )]
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

    # 3. LLM fallback (DeepSeek)
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
        "source":     "DeepSeek LLM (scholarly knowledge)",
    }

@app.get("/api/citation-lookup")
async def citation_lookup(ref: str, req: Request):
    """Looks up a citation, gets Sanskrit text, and translates it instantly."""
    await _gate_unauthed_llm(req)
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



# ── Content Explorer endpoints ────────────────────────────────────────────

_GUIDE_INTRO_CACHE: dict[str, dict] = {}

@app.get("/api/explore/{text_id}/intro")
async def get_explore_intro(text_id: str):
    """
    AI-generated guide intro for a text: what it is, why it matters,
    the 5 must-read chapters, and the best entry point for a newcomer.
    Cached in-process after first generation.
    """
    if text_id in _GUIDE_INTRO_CACHE:
        return _GUIDE_INTRO_CACHE[text_id]

    # Get text metadata from catalog
    catalog_resp = await list_puranas()
    catalog = catalog_resp.get("puranas", [])
    meta = next((t for t in catalog if t["id"] == text_id), None)
    if not meta:
        raise HTTPException(404, f"Text {text_id} not found in catalog")

    text_name = meta["name"]
    tradition = meta.get("tradition", "")
    category = meta.get("category", "")

    prompt = f"""You are a scholar and guide introducing {text_name} to someone who has never read it.

Write a JSON response with exactly this structure:
{{
  "tagline": "One evocative sentence that captures the soul of this text (max 15 words)",
  "what_it_is": "2-3 sentences: what this text is, its scale, its place in the tradition",
  "why_it_matters": "2-3 sentences: why a modern person should care. Concrete, not generic",
  "famous_stories": [
    {{"title": "Story name", "chapter_hint": "rough location e.g. Book 10 or Chapter 22-30", "description": "1 sentence of pure drama or insight"}},
    ... (4-6 entries)
  ],
  "entry_chapters": [
    {{"chapter_hint": "Chapter/Book/Skandha number or range", "label": "short label", "for_reader": "who this entry is best for e.g. 'seekers of devotion', 'lovers of mythology'"}},
    ... (3 entries)
  ],
  "one_line_pitch": "If someone asks you why they should read this in 10 words or less"
}}

Tradition: {tradition}. Category: {category}.
Be specific and concrete. Avoid generic spiritual platitudes. Name actual stories, characters, events."""

    try:
        msgs = [{"role": "user", "content": prompt}]
        raw = await call_llm_once(msgs, temperature=0.3)
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        result = {"text_id": text_id, "text_name": text_name, **data}
        _GUIDE_INTRO_CACHE[text_id] = result
        return result
    except Exception as e:
        logger.error("Guide intro generation failed for %s: %s", text_id, e)
        raise HTTPException(500, f"Failed to generate intro: {e}")

@app.get("/api/verses/{chunk_id}")
async def get_verse(chunk_id: str, user: Optional[dict] = Depends(get_current_user)):
    """Fetch a single verse/chunk by ID.

    A workspace (user-uploaded) chunk is visible only to its owner; to anyone else it
    is reported as not found, so private uploads never leak via a guessed/known id.
    """
    if not state.searcher or not state.searcher.is_ready:
        raise HTTPException(503, "Search not ready")
    chunk = await state.searcher.get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(404, f"Chunk {chunk_id} not found")
    if chunk.get("workspace"):
        user_id = user.get("id") if user else None
        if chunk.get("user_id") != user_id:
            raise HTTPException(404, f"Chunk {chunk_id} not found")
    return chunk

@app.get("/api/verses/{chunk_id}/similar")
async def get_similar_verses(chunk_id: str, top_k: int = 10,
                             user: Optional[dict] = Depends(get_current_user)):
    """Find semantically similar verses across the public corpus + the caller's own
    workspace docs. Another seeker's private upload is never surfaced (Sangama scope)."""
    if not state.searcher or not state.searcher.is_ready:
        raise HTTPException(503, "Search not ready")
    top_k = min(top_k, 50)
    user_id = user.get("id") if user else None
    results = await state.searcher.find_similar_verses(chunk_id, top_k, requesting_user=user_id)
    return {
        "source_id": chunk_id,
        "count": len(results),
        "similar": [r.to_dict() for r in results],
    }

@app.get("/api/chapters/{text_id}/{chapter}")
async def get_chapter(text_id: str, chapter: int, limit: int = 500):
    """Fetch all indexed verses for a text + chapter, in order."""
    if not state.searcher or not state.searcher.is_ready:
        raise HTTPException(503, "Search not ready")
    limit = min(limit, 1000)
    verses = await state.searcher.get_chapter_verses(text_id, chapter, limit)
    if not verses:
        raise HTTPException(404, f"No verses found for {text_id} chapter {chapter}")
    return {
        "text_id": text_id,
        "chapter": chapter,
        "count": len(verses),
        "verses": verses,
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
    is_byok = bool(custom_keys_var.get())
    # Scholarly Inference shares the deep-research daily quota (both are Pro-gated
    # synthesis features). Previously this called check_inference_limit /
    # increment_inference_usage, which were never defined → NameError 500 on every
    # call. Reuse the existing research-limit functions instead.
    allowed, _rem = check_research_limit(user.get("id"), role, is_byok=is_byok)
    if not allowed:
        raise HTTPException(403, "Free trial for Scholarly Inference exhausted. Please upgrade to Pro.")

    if not request.topic.strip():
        raise HTTPException(400, "Topic cannot be empty")

    async def infer_gen() -> AsyncGenerator[dict, None]:
        increment_research_usage(user.get("id"))
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

        full_text = "".join(full_response)
        
        AI_DISCLAIMERS = re.compile(
            r"(As an AI|as a language model|I don't have personal experiences|"
            r"I cannot provide|I'm just an AI|artificial intelligence)",
            re.IGNORECASE
        )
        if AI_DISCLAIMERS.search(full_text):
            logger.warning("AI disclaimer detected in INFER response: %s", full_text[:100].replace('\n', ' '))
            
        session_manager.append_messages(request.session_id, [
            {"role": "user",      "content": f"[INFER] {request.topic}"},
            {"role": "assistant", "content": full_text},
        ], user_id)
        yield {"data": json.dumps({"type": "done"})}

    return EventSourceResponse(safe_sse_stream(infer_gen()), headers={"X-Accel-Buffering": "no"})


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


# ── Workspace Endpoints ───────────────────────────────────────────────────

WORKSPACE_UPLOAD_DIR = Path("data/workspace")

@app.post("/api/workspace/upload")
async def workspace_upload(
    file: UploadFile | None = File(None),
    url: str | None = Form(None),
    user: dict = Depends(require_auth),
):
    """Upload a document (PDF/DOCX) or submit a URL for workspace ingestion."""
    import uuid as _uuid
    from backend.workspace_ingest import ingest_document

    user_id = user["id"]

    if not file and not url:
        raise HTTPException(400, "Provide either a file upload or a URL")

    doc_id = str(_uuid.uuid4())

    if file:
        ext = (file.filename or "upload").rsplit(".", 1)[-1].lower()
        if ext not in ("pdf", "docx"):
            raise HTTPException(400, f"Unsupported file type: .{ext}. Use PDF or DOCX.")
        doc_type = ext
        filename = file.filename or f"upload.{ext}"

        user_dir = WORKSPACE_UPLOAD_DIR / user_id / doc_id
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / f"original.{ext}"
        content = await file.read()
        file_path.write_bytes(content)
    else:
        doc_type = "url"
        filename = url[:100]
        file_path = None

    # Insert tracking row
    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO workspace_documents (doc_id, user_id, filename, doc_type, source_url, status)
                       VALUES (%s, %s, %s, %s, %s, 'pending')""",
                    (doc_id, user_id, filename, doc_type, url),
                )
            conn.commit()
        finally:
            conn.close()

    # Kick off async ingestion
    asyncio.create_task(ingest_document(
        doc_id=doc_id,
        file_path=file_path,
        source_url=url,
        doc_type=doc_type,
        user_id=user_id,
        filename=filename,
    ))

    return {"doc_id": doc_id, "status": "pending"}


@app.get("/api/workspace/docs")
async def workspace_list_docs(user: dict = Depends(require_auth)):
    """List all workspace documents for the authenticated user."""
    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if not conn:
        raise HTTPException(503, "Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT doc_id, filename, doc_type, status, error_msg,
                          chunk_count, section_count, title, created_at, updated_at
                   FROM workspace_documents WHERE user_id = %s
                   ORDER BY created_at DESC""",
                (user["id"],),
            )
            rows = cur.fetchall()
        return {"documents": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/api/workspace/docs/{doc_id}")
async def workspace_doc_status(doc_id: str, user: dict = Depends(require_auth)):
    """Get status and metadata for a workspace document."""
    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if not conn:
        raise HTTPException(503, "Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT doc_id, filename, doc_type, status, error_msg,
                          chunk_count, section_count, title, thread_map,
                          created_at, updated_at
                   FROM workspace_documents WHERE doc_id = %s AND user_id = %s""",
                (doc_id, user["id"]),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        result = dict(row)
        if result.get("thread_map") and isinstance(result["thread_map"], str):
            result["thread_map"] = json.loads(result["thread_map"])
        return result
    finally:
        conn.close()


@app.delete("/api/workspace/docs/{doc_id}")
async def workspace_delete_doc(doc_id: str, user: dict = Depends(require_auth)):
    """Delete a workspace document and all its chunks."""
    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if not conn:
        raise HTTPException(503, "Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id FROM workspace_documents WHERE doc_id = %s AND user_id = %s",
                (doc_id, user["id"]),
            )
            if not cur.fetchone():
                raise HTTPException(404, "Document not found")
            cur.execute(
                "DELETE FROM purana_verses WHERE metadata->>'doc_id' = %s",
                (doc_id,),
            )
            cur.execute(
                "DELETE FROM reading_progress WHERE doc_id = %s AND user_id = %s",
                (doc_id, user["id"]),
            )
            cur.execute(
                "DELETE FROM workspace_documents WHERE doc_id = %s AND user_id = %s",
                (doc_id, user["id"]),
            )
        conn.commit()
        # Clean up files
        import shutil
        upload_dir = WORKSPACE_UPLOAD_DIR / user["id"] / doc_id
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        return {"deleted": True}
    finally:
        conn.close()


_WORKSPACE_INTRO_CACHE: dict[str, dict] = {}

@app.get("/api/workspace/docs/{doc_id}/intro")
async def workspace_doc_intro(doc_id: str, user: dict = Depends(require_auth)):
    """AI-generated guide intro for a workspace document."""
    if doc_id in _WORKSPACE_INTRO_CACHE:
        return _WORKSPACE_INTRO_CACHE[doc_id]

    if not state.searcher or not state.searcher.is_ready:
        raise HTTPException(503, "Search not ready")

    # Fetch first chunks from each section
    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if not conn:
        raise HTTPException(503, "Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, section_count FROM workspace_documents WHERE doc_id = %s AND user_id = %s",
                (doc_id, user["id"]),
            )
            doc_row = cur.fetchone()
        if not doc_row:
            raise HTTPException(404, "Document not found")
    finally:
        conn.close()

    doc_title = doc_row["title"] or doc_id
    section_count = doc_row["section_count"] or 1

    # Sample first chunk from up to 6 sections
    sample_sections = min(section_count, 6)
    excerpts = []
    for ch in range(1, sample_sections + 1):
        try:
            verses = await state.searcher.get_chapter_verses(doc_id, ch, limit=1)
            if verses:
                section_title = verses[0].get("book_section", f"Section {ch}")
                excerpts.append(f"[{section_title}]: {verses[0].get('text', '')[:400]}")
        except Exception:
            pass

    if not excerpts:
        raise HTTPException(500, "No chunks found for document")

    prompt = f"""You are reading a document titled "{doc_title}". Based on these excerpts from different sections, write a guide introduction as JSON:
{{
  "tagline": "One sentence capturing the core subject (max 15 words)",
  "what_it_is": "2-3 sentences: what this document is about, its scope, its depth",
  "why_it_matters": "2-3 sentences: why a reader should care about this content",
  "key_sections": [
    {{"section_num": N, "title": "Section title", "description": "1 sentence summary"}},
    ... (up to 6)
  ],
  "entry_points": [
    {{"section_num": N, "label": "short label", "for_reader": "who should start here"}},
    ... (3 entries)
  ],
  "one_line_pitch": "10 words or less on why to read this"
}}

Document excerpts:
{chr(10).join(excerpts)}

Be specific to THIS document. Do not guess content you haven't seen."""

    try:
        raw = await call_llm_once([{"role": "user", "content": prompt}], temperature=0.3)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        result = {"doc_id": doc_id, "doc_title": doc_title, **data}
        _WORKSPACE_INTRO_CACHE[doc_id] = result
        return result
    except Exception as e:
        logger.error("Workspace intro generation failed for %s: %s", doc_id, e)
        raise HTTPException(500, f"Failed to generate intro: {e}")


@app.get("/api/workspace/docs/{doc_id}/threads")
async def workspace_doc_threads(doc_id: str, user: dict = Depends(require_auth)):
    """Get or generate thread map (choice-driven navigation paths) for a document."""
    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if not conn:
        raise HTTPException(503, "Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, section_count, thread_map FROM workspace_documents WHERE doc_id = %s AND user_id = %s",
                (doc_id, user["id"]),
            )
            doc_row = cur.fetchone()
        if not doc_row:
            raise HTTPException(404, "Document not found")
    finally:
        conn.close()

    # Return cached thread map if exists
    if doc_row.get("thread_map"):
        tm = doc_row["thread_map"]
        if isinstance(tm, str):
            tm = json.loads(tm)
        return tm

    if not state.searcher or not state.searcher.is_ready:
        raise HTTPException(503, "Search not ready")

    doc_title = doc_row["title"] or doc_id
    section_count = doc_row["section_count"] or 1

    # Sample chunks from across the document
    excerpts = []
    chunk_ids_by_section: dict[int, list[str]] = {}
    for ch in range(1, min(section_count + 1, 12)):
        try:
            verses = await state.searcher.get_chapter_verses(doc_id, ch, limit=3)
            for v in verses:
                section_title = v.get("book_section", f"Section {ch}")
                excerpts.append(f"[Section {ch}: {section_title}] {v.get('text', '')[:300]}")
                chunk_ids_by_section.setdefault(ch, []).append(v.get("id", ""))
        except Exception:
            pass

    if not excerpts:
        return {"threads": [], "branch_points": []}

    prompt = f"""You are analyzing a document titled "{doc_title}" to create reading paths.

Based on these excerpts, generate a JSON thread map with 3-5 reading threads.
Each thread is a different way to navigate the document — by narrative, by theme, by concept, etc.

{{
  "threads": [
    {{
      "id": "slug",
      "label": "Thread Name (3-5 words)",
      "description": "One sentence describing this path",
      "icon": "one of: book, users, sparkles, compass, lightbulb",
      "section_sequence": [1, 3, 5, 2]
    }}
  ]
}}

Document excerpts:
{chr(10).join(excerpts[:20])}

Return ONLY valid JSON. Each section_sequence should list section numbers (1-{section_count}) in the recommended reading order for that thread."""

    try:
        raw = await call_llm_once([{"role": "user", "content": prompt}], temperature=0.4)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        thread_map = json.loads(raw)

        # Cache in DB
        from backend.workspace_ingest import update_doc_status, _get_pool
        pool = await _get_pool()
        try:
            await update_doc_status(pool, doc_id, doc_row.get("status", "ready"), thread_map=thread_map)
        finally:
            await pool.close()

        return thread_map
    except Exception as e:
        logger.error("Thread generation failed for %s: %s", doc_id, e)
        return {"threads": [], "error": str(e)}


@app.post("/api/workspace/progress")
async def workspace_mark_read(
    data: dict,
    user: dict = Depends(require_auth),
):
    """Mark a chunk as read. Body: {"doc_id": "...", "chunk_id": "...", "time_spent": 5}"""
    doc_id = data.get("doc_id")
    chunk_id = data.get("chunk_id")
    time_spent = data.get("time_spent")

    if not doc_id or not chunk_id:
        raise HTTPException(400, "doc_id and chunk_id required")

    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if not conn:
        raise HTTPException(503, "Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO reading_progress (user_id, doc_id, chunk_id, time_spent)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id, doc_id, chunk_id) DO UPDATE SET
                       read_at = NOW(),
                       time_spent = COALESCE(reading_progress.time_spent, 0) + COALESCE(EXCLUDED.time_spent, 0)""",
                (user["id"], doc_id, chunk_id, time_spent),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/api/workspace/docs/{doc_id}/progress")
async def workspace_doc_progress(doc_id: str, user: dict = Depends(require_auth)):
    """Reading stats + semantic coverage for a document."""
    from backend.db_client import get_db_conn
    conn = get_db_conn()
    if not conn:
        raise HTTPException(503, "Database unavailable")
    try:
        with conn.cursor() as cur:
            # Get doc info
            cur.execute(
                "SELECT chunk_count, section_count, title FROM workspace_documents WHERE doc_id = %s AND user_id = %s",
                (doc_id, user["id"]),
            )
            doc = cur.fetchone()
            if not doc:
                raise HTTPException(404, "Document not found")

            # Count read chunks
            cur.execute(
                "SELECT COUNT(*) AS read_count FROM reading_progress WHERE doc_id = %s AND user_id = %s",
                (doc_id, user["id"]),
            )
            read_count = cur.fetchone()["read_count"]

            # Section-level coverage
            cur.execute(
                """SELECT (pv.metadata->>'chapter')::int AS section_num,
                          pv.metadata->>'book_section' AS section_title,
                          COUNT(pv.id) AS total_chunks,
                          COUNT(rp.chunk_id) AS read_chunks
                   FROM purana_verses pv
                   LEFT JOIN reading_progress rp
                       ON rp.chunk_id = pv.id AND rp.user_id = %s AND rp.doc_id = %s
                   WHERE pv.metadata->>'doc_id' = %s
                   GROUP BY section_num, section_title
                   ORDER BY section_num""",
                (user["id"], doc_id, doc_id),
            )
            sections = []
            for row in cur.fetchall():
                sections.append({
                    "section_num": row["section_num"],
                    "title": row["section_title"] or f"Section {row['section_num']}",
                    "total": row["total_chunks"],
                    "read": row["read_chunks"],
                    "coverage": round(row["read_chunks"] / max(row["total_chunks"], 1) * 100, 1),
                })

        total = doc["chunk_count"] or 1
        return {
            "doc_id": doc_id,
            "title": doc["title"],
            "total_chunks": total,
            "read_chunks": read_count,
            "overall_coverage": round(read_count / total * 100, 1),
            "sections": sections,
        }
    finally:
        conn.close()


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
    # byok_keys is a DB column, not part of the JWT-derived user dict — fetch the
    # profile (previously read user.get("byok_keys") which was always empty).
    from backend.db_client import get_profile
    profile = get_profile(user["id"]) or {}
    keys = decrypt_keys(profile.get("byok_keys", ""))
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

@app.post("/api/iap/apple/verify")
async def apple_iap_verify(data: dict, user: dict = Depends(require_auth)):
    """
    Verify a StoreKit 2 signed transaction (JWS) from the iOS app and grant Pro.
    The frontend SubscriptionContext POSTs { jws } here after a purchase/restore.
    Apple's signature + cert chain are verified locally (no network round-trip).
    """
    from backend.apple_iap import (
        verify_transaction_jws,
        plan_for_product,
        period_days_for_product,
    )

    jws = (data or {}).get("jws")
    if not jws:
        raise HTTPException(400, "jws is required")

    payload = verify_transaction_jws(jws)
    if not payload:
        # Not a valid/active Pro transaction — report not-pro rather than error.
        return {"is_pro": False, "verified": False}

    product_id = payload.get("productId")
    plan = plan_for_product(product_id)
    period_days = period_days_for_product(product_id)
    transaction_id = str(payload.get("originalTransactionId") or payload.get("transactionId") or "")

    success = activate_user_subscription(
        user_id=user["id"],
        plan=plan,
        provider="apple",
        external_sub_id=transaction_id,
        period_end_days=period_days,
    )
    if not success:
        raise HTTPException(500, "Failed to activate subscription")

    return {"is_pro": plan != "free", "verified": True, "plan": plan}

@app.post("/api/iap/apple/notifications")
async def apple_server_notifications(req: Request):
    """
    App Store Server Notifications V2 — Apple's authoritative server-to-server
    channel for subscription lifecycle (renewals, expirations, refunds, billing
    retry). Set this URL in App Store Connect (production + sandbox).

    The signedPayload is a JWS verified against Apple's cert chain. We map the
    original transaction id back to our user and grant/revoke Pro accordingly.
    """
    from backend.apple_iap import decode_server_notification, period_days_for_product
    from backend.billing import find_user_by_external_sub, downgrade_user

    try:
        body = await req.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    signed_payload = body.get("signedPayload")
    if not signed_payload:
        raise HTTPException(400, "Missing signedPayload")

    note = decode_server_notification(signed_payload)
    if not note:
        # Invalid signature / unverifiable — ack so Apple stops retrying a bad one,
        # but do nothing.
        logger.warning("[apple_iap] ASSN failed verification")
        return {"status": "ignored"}

    user_id = find_user_by_external_sub(note["original_transaction_id"])
    if not user_id:
        # We haven't seen this transaction yet (e.g. notification arrived before
        # the client verify call). Ack — the client verify path will create it.
        logger.info(f"[apple_iap] ASSN {note['notificationType']} for unknown tx, acking")
        return {"status": "unknown_transaction"}

    if note["is_active"] and note["plan"] != "free":
        period_days = period_days_for_product(note["product_id"] or "")
        activate_user_subscription(
            user_id=user_id,
            plan=note["plan"],
            provider="apple",
            external_sub_id=note["original_transaction_id"],
            period_end_days=period_days,
        )
        logger.info(f"[apple_iap] ASSN {note['notificationType']} → activated {user_id}")
    else:
        downgrade_user(user_id)
        logger.info(f"[apple_iap] ASSN {note['notificationType']} → downgraded {user_id}")

    return {"status": "ok"}

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
