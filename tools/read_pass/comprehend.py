"""comprehend — read one chapter window through the Sharma lens, emit the record.

Pipeline per chapter:
  window (from group.py) ──select_lens──> prompt ──LLM──> JSON ──validate──> record

The only non-deterministic step is the LLM call. Everything else (lens
selection, prompt assembly, response parsing, the resumable loop) is pure and
tested. JSON contract (Rule 0, precondition B).

Supports two providers:
  - deepseek (DEFAULT, 19x cheaper): DEEPSEEK_API_KEY, model deepseek-chat
  - gemini (fallback):               GEMINI_API_KEY,  model gemini-3.5-flash
Provider selected via --provider flag on run.py or auto-detected from env keys.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from tools.read_pass import schema

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_PROVIDER = "deepseek"
_LENS_PATH = "data/chunks/sharma_texts.jsonl"


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _strip_diacritics(s: str) -> str:
    """Lowercase + remove combining diacritics so 'kṛṣṇa' matches 'krsna'."""
    import unicodedata
    nf = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nf if not unicodedata.combining(c)).lower()


# ── lens (Shailendra Sharma commentary) ────────────────────────────────────
def load_lens(path: str = _LENS_PATH) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def select_lens(window: Dict[str, Any], lens: List[Dict[str, Any]],
                max_chars: int = 6000) -> str:
    """Pick the Sharma commentary most relevant to this chapter.

    Lens is currently Gita-only, so relevance is keyword overlap between the
    chapter summary words and the commentary text. Returns concatenated
    commentary text capped at max_chars, or "" when nothing relevant (the
    read-pass then falls back to a faithful generic comprehension).
    """
    if not lens:
        return ""
    # source is transliterated Sanskrit WITH diacritics (kṛṣṇa, ātman, bhagavān).
    # Normalize diacritics before matching, else ASCII signals never fire.
    raw = (window.get("chapter_label", "") + " " + window.get("text", ""))
    hay = _strip_diacritics(raw[:4000])
    # cheap signal: yoga/gita vocabulary that means the Sharma lens applies.
    # Each is the diacritic-stripped form so it matches the normalized haystack.
    signals = ("yoga", "karma", "dhyana", "atman", "atma", "brahman", "krsna",
               "krishna", "vasudeva", "arjuna", "guna", "moksha", "mukti",
               "bhakti", "dhyan", "samadhi", "jnana", "self", "consciousness",
               "param", "purusa", "purusha", "isvara", "bhagavan")
    if not any(s in hay for s in signals):
        return ""
    picked, total = [], 0
    for rec in lens:
        t = rec.get("text", "")
        if not t:
            continue
        picked.append(t)
        total += len(t)
        if total >= max_chars:
            break
    return "\n---\n".join(picked)[:max_chars]


# ── prompt ─────────────────────────────────────────────────────────────────
def build_prompt(window: Dict[str, Any], lens_text: str) -> str:
    lens_block = (
        f"\n## Interpretive lens — Shailendra Sharma's Kriya-Yoga commentary\n"
        f"Read the chapter THROUGH this lens. Where a teaching echoes it, say what\n"
        f"it means in Sharma's framework (use the teaching.lens_note field).\n"
        f"<<<\n{lens_text}\n>>>\n"
        if lens_text else
        "\n## No specific lens passage applies — comprehend faithfully and plainly.\n"
    )
    return f"""You are a scholar of the Puranas performing a deep comprehension read.
Read this chapter and extract its full structure as JSON matching the schema.

Rules:
- Use the verse markers in the text (e.g. bhp_01.01.001) to fill verse_ranges.
- Capture cross-references: when a being is an avatar/alias of another, record it.
- entities.kind one of: deity, sage, king, demon, concept, place, practice, text.
- Be faithful to the text; do not invent events not present.
{lens_block}
## Chapter: {window.get('purana')} — {window.get('chapter_label')}
<<<
{window.get('text', '')}
>>>"""


# ── LLM calls (the one non-deterministic step) ────────────────────────────
def _call_deepseek(prompt: str, model: str, api_key: str, timeout: int = 120) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 8192,  # deepseek-chat ceiling; dense genealogy chapters can
                             # still truncate — parse_response salvages partial JSON
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    return resp["choices"][0]["message"]["content"]


def _call_gemini(prompt: str, model: str, api_key: str, timeout: int = 120) -> str:
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema.RESPONSE_SCHEMA,
            "temperature": 0.2,
        },
    }).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    return resp["candidates"][0]["content"]["parts"][0]["text"]


_CALLERS = {"deepseek": _call_deepseek, "gemini": _call_gemini}
_MODELS = {"deepseek": "deepseek-chat", "gemini": "gemini-3.5-flash"}


def resolve_provider() -> tuple:
    """Auto-detect provider from env. Returns (provider, api_key, model)."""
    dk = os.environ.get("DEEPSEEK_API_KEY", "")
    if dk:
        return "deepseek", dk, _MODELS["deepseek"]
    gk = os.environ.get("GEMINI_API_KEY", "")
    if gk:
        return "gemini", gk, _MODELS["gemini"]
    return "", "", ""


def parse_response(raw: str) -> Dict[str, Any]:
    """Parse the LLM text into a record. Tolerates ```json fences AND salvages
    truncated JSON (dense chapters overflow the output cap mid-array)."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return _salvage_truncated(s)


def _salvage_truncated(s: str) -> Dict[str, Any]:
    """Best-effort recovery of a truncated JSON object: walk the string, track
    nesting, and close any open arrays/objects at the last point where the
    structure was valid (i.e. after the last complete element). Drops the
    half-written trailing element rather than failing the whole chapter.

    Raises JSONDecodeError only if even the salvage can't produce valid JSON,
    so the caller's bad_json path still works for true garbage.
    """
    # find the last position where brackets balance after a complete element:
    # scan for the last ',' or matching close at depth, truncate there, re-close.
    depth = 0
    in_str = False
    esc = False
    last_safe = -1  # index just after a completed top-level array/obj element
    stack = []
    for i, ch in enumerate(s):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
            depth += 1
        elif ch in "}]":
            if stack:
                stack.pop()
            depth -= 1
            # a complete element just closed at depth>=1 (inside an array/obj)
            if depth >= 1:
                last_safe = i + 1
        elif ch == "," and depth >= 1:
            last_safe = i  # safe to truncate before this comma
    if last_safe == -1:
        raise json.JSONDecodeError("unsalvageable", s, 0)
    head = s[:last_safe]
    # close the still-open containers in reverse order
    # recompute remaining open stack on the truncated head
    d2 = 0
    st2 = []
    in_s = False
    es = False
    for ch in head:
        if es:
            es = False
            continue
        if ch == "\\" and in_s:
            es = True
            continue
        if ch == '"':
            in_s = not in_s
            continue
        if in_s:
            continue
        if ch in "{[":
            st2.append(ch)
        elif ch in "}]":
            if st2:
                st2.pop()
    closers = "".join("}" if c == "{" else "]" for c in reversed(st2))
    return json.loads(head + closers)


# ── node-level validity (mirror of schema.validate's per-node rules) ───────
def _node_problems(field: str, n: Dict[str, Any]) -> bool:
    """True if this single node is malformed (would fail schema.validate)."""
    if not isinstance(n, dict):
        return True
    if "verse_ranges" not in n:
        return True
    if field == "entities" and not n.get("name"):
        return True
    if field == "relationships" and not (n.get("src") and n.get("rel") and n.get("dst")):
        return True
    if field == "teachings" and not n.get("teaching"):
        return True
    return False


# ── one chapter ────────────────────────────────────────────────────────────
def comprehend_window(window: Dict[str, Any],
                      lens: List[Dict[str, Any]],
                      api_key: str,
                      model: str = DEFAULT_MODEL,
                      provider: str = DEFAULT_PROVIDER,
                      caller: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    """window -> envelope with data=the record. `caller` injectable for tests."""
    md = {"chapter_label": window.get("chapter_label"),
          "seq_start": window.get("seq_start"), "model": model, "provider": provider}
    lens_text = select_lens(window, lens)
    md["lens_applied"] = bool(lens_text)
    prompt = build_prompt(window, lens_text)
    # DeepSeek doesn't enforce schema server-side, so embed it in the prompt
    if provider == "deepseek" and not caller:
        prompt = prompt + "\n\nReturn ONLY valid JSON matching this schema:\n" + json.dumps(schema.RESPONSE_SCHEMA, indent=1)
    fn = caller or _CALLERS.get(provider, _call_deepseek)
    try:
        raw = fn(prompt, model, api_key)
    except urllib.error.HTTPError as e:
        return _envelope(False, None, md,
                         [{"code": "http_error",
                           "message": f"{e.code}: {e.read().decode()[:200]}"}])
    except Exception as e:  # noqa
        return _envelope(False, None, md,
                         [{"code": "call_failed", "message": str(e)[:200]}])
    try:
        record = parse_response(raw)
    except json.JSONDecodeError as e:
        return _envelope(False, None, md,
                         [{"code": "bad_json", "message": str(e)[:200]}])
    # backfill keys a salvaged-truncated record may be missing, so partial
    # comprehension still lands (we keep what was extracted before the cutoff)
    record.setdefault("chapter_summary", "")
    record.setdefault("entities", [])
    record.setdefault("relationships", [])
    record.setdefault("teachings", [])
    record.setdefault("story", {"title": window.get("chapter_label", ""),
                                "arc": record.get("chapter_summary", "")})
    if not record["story"].get("arc"):
        record["story"]["arc"] = record.get("chapter_summary") or "(truncated)"
    md["salvaged"] = bool(raw and not raw.rstrip().endswith(("}", "```")))
    problems = schema.validate(record)
    if problems:
        # drop the malformed nodes (usually the truncated trailing element) and
        # re-validate — keep the good 99% rather than failing the whole chapter.
        for field in ("entities", "relationships", "teachings"):
            record[field] = [n for n in record.get(field, []) if not _node_problems(field, n)]
        md["pruned_invalid_nodes"] = True
        problems = schema.validate(record)
    if problems:
        return _envelope(False, None, md,
                         [{"code": "schema_invalid", "message": "; ".join(problems[:5])}])
    # stamp provenance so the record traces back to source independent of LLM
    record["_provenance"] = {
        "purana": window.get("purana"),
        "chapter_label": window.get("chapter_label"),
        "seq_start": window.get("seq_start"),
        "seq_end": window.get("seq_end"),
        "chunk_ids": window.get("chunk_ids", []),
        # who/what produced this record — makes every chapter auditable
        "provider": provider,
        "model": model,
        "lens_applied": md["lens_applied"],
        "salvaged": md.get("salvaged", False),
        "pruned_invalid_nodes": md.get("pruned_invalid_nodes", False),
    }
    return _envelope(True, record, md, [])
