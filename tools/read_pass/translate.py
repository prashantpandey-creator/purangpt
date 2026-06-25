"""translate — publication-grade RU→EN translation of Sharma's Russian works.

Daddy: "translate the works with a good model and keep them in reference / some
official way." Model = gemini-2.5-flash (excellent literary RU→EN, large context,
cheap ~$0.3-0.5 for 1.86M chars, billed separately from DeepSeek). Output: clean
English markdown under tools/read_pass/translations/ — the OFFICIAL English
reference for the Russian-only material (Mossin biography, Gita RU).

Windows are translated CONCURRENTLY but reassembled in strict source order
(assemble() keys by index, never by completion time) so the prose reads straight
through. Failed windows are recorded in the envelope, never silently dropped, and
a [[TRANSLATION GAP n]] marker is left in place so nothing is lost.

JSON contract (Rule 0, precond B):
  run(src_path, key, out_path) -> {success, data:{n_windows,...}, metadata, errors}
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any, Callable, Dict, List, Optional


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


_PROMPT = (
    "You are a professional literary translator. Translate the following Russian "
    "text into fluent, publication-grade English. This is spiritual/yogic prose "
    "from the Kriya Yoga tradition (a biography of and commentary by Guru "
    "Shailendra Sharma). Preserve:\n"
    "- the contemplative, dignified register\n"
    "- all Sanskrit/Hindi terms, transliterated (e.g. Kriya, Kutastha, Shivalingam, "
    "Babaji, samadhi, prana) — do not over-anglicize them\n"
    "- proper names of people, deities, and places exactly\n"
    "- paragraph structure\n"
    "Do NOT summarize, omit, or add commentary. Return ONLY the English translation.\n\n"
    "RUSSIAN TEXT:\n"
)


def make_windows(text: str, max_chars: int = 12000) -> List[str]:
    """Split on paragraph boundaries with full coverage, order preserved."""
    paras = re.split(r"\n\s*\n", text)
    if len(paras) < 2:
        paras = text.split("\n")
    windows, cur, cur_len = [], [], 0
    for p in paras:
        plen = len(p) + 2
        if cur and cur_len + plen > max_chars:
            windows.append("\n\n".join(cur))
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += plen
    if cur:
        windows.append("\n\n".join(cur))
    return windows or [text]


def _gemini_translate(text: str, model: str, api_key: str,
                      timeout: int = 180) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    body = json.dumps({
        "contents": [{"parts": [{"text": _PROMPT + text}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    cand = resp["candidates"][0]
    parts = cand.get("content", {}).get("parts")
    if not parts:
        raise RuntimeError(f"no parts (finishReason={cand.get('finishReason')})")
    return "".join(p.get("text", "") for p in parts)


def _openai_http(url, headers, body, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def _openai_translate(text: str, model: str, api_key: str,
                      base_url: str = "https://api.deepseek.com/v1",
                      timeout: int = 180, http=None) -> str:
    """OpenAI-protocol translation — works for DeepSeek, OpenAI, any compatible endpoint."""
    fn = http or _openai_http
    body = {
        "model": model,
        "messages": [{"role": "user", "content": _PROMPT + text}],
        "temperature": 0.3, "max_tokens": 8192,
    }
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {api_key}"}
    resp = fn(f"{base_url}/chat/completions", headers, body)
    return resp["choices"][0]["message"]["content"]


def make_openai_caller(base_url: str = "https://api.deepseek.com/v1", http=None):
    """Build a caller with the (text, model, api_key) signature translate_window
    expects, binding ONLY base_url/http — NOT model. Binding model here collides
    with translate_window's positional fn(text, model, api_key) call ("multiple
    values for 'model'"), which silently gapped all DeepSeek windows once."""
    def _caller(text: str, model: str, api_key: str) -> str:
        return _openai_translate(text, model, api_key, base_url=base_url, http=http)
    return _caller


def translate_window(text: str, api_key: str,
                     model: str = "gemini-2.5-flash",
                     caller: Optional[Callable[..., str]] = None) -> str:
    fn = caller or _gemini_translate
    return fn(text, model, api_key)


def _cyrillic_ratio(s: str) -> float:
    cyr = len(re.findall(r"[а-яёА-ЯЁ]", s))
    lat = len(re.findall(r"[a-zA-Z]", s))
    return cyr / max(cyr + lat, 1)


def validate_translation(ru_in: str, en_out: str) -> tuple:
    """Catch the silent-failure modes that gutted the first run.

    Returns (ok, reason). A translation is bad if:
      - output still mostly Cyrillic (model ECHOED the Russian)
      - output far too short vs input (TRUNCATED / partial)
      - output empty
    """
    if not en_out or not en_out.strip():
        return False, "empty output"
    cyr = _cyrillic_ratio(en_out)
    if cyr > 0.15:
        return False, f"russian echo ({cyr*100:.0f}% cyrillic in output)"
    # RU→EN length ratio: English chars usually 0.5-1.2x the Russian source.
    # Anything under 0.25x means most content was dropped/truncated.
    ratio = len(en_out) / max(len(ru_in), 1)
    if ratio < 0.25:
        return False, f"too short / truncated (ratio {ratio:.2f})"
    return True, "ok"


def translate_window_verified(text: str, api_key: str,
                              model: str = "gemini-2.5-flash",
                              caller: Optional[Callable[..., str]] = None,
                              max_retries: int = 2) -> str:
    """Translate one window, validate, and retry on echo/truncation.

    Raises RuntimeError if all attempts fail validation (so the caller records
    a real gap instead of silently writing garbage).
    """
    last_reason = "no attempt"
    last_out = ""
    for attempt in range(max_retries + 1):
        out = translate_window(text, api_key, model=model, caller=caller)
        ok, reason = validate_translation(text, out)
        if ok:
            return out
        last_reason, last_out = reason, out
    raise RuntimeError(f"validation failed after {max_retries+1} tries: {last_reason}")


def assemble(translated: Dict[int, str], n_windows: int) -> str:
    """Reassemble translated windows in strict source order (by index)."""
    out = []
    for i in range(n_windows):
        out.append(translated.get(i, f"\n\n[[TRANSLATION GAP {i}]]\n\n"))
    return "\n\n".join(out)


def run(src_path: str, api_key: str, out_path: str,
        model: str = "gemini-2.5-flash",
        max_chars: int = 12000,
        max_workers: int = 8,
        title: str = "",
        caller: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    """Translate a Russian text file → English markdown reference."""
    try:
        text = open(src_path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return _envelope(False, None, {}, [{"code": "read_error", "message": str(e)}])
    if not text.strip():
        return _envelope(False, None, {}, [{"code": "empty", "message": "no text"}])

    windows = make_windows(text, max_chars=max_chars)
    translated: Dict[int, str] = {}
    errors = []

    def _do(w):
        # verified path: validates output + retries on echo/truncation
        return translate_window_verified(w, api_key, model=model, caller=caller)

    if caller is not None:
        for i, w in enumerate(windows):
            try:
                translated[i] = _do(w)
            except Exception as e:
                errors.append({"code": "window_failed",
                               "message": f"win {i}: {str(e)[:150]}"})
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_do, w): i for i, w in enumerate(windows)}
            for f in as_completed(futs):
                idx = futs[f]
                try:
                    translated[idx] = f.result(timeout=300)
                except Exception as e:
                    errors.append({"code": "window_failed",
                                   "message": f"win {idx}: {str(e)[:150]}"})

    body = assemble(translated, len(windows))
    header = (f"# {title}\n\n" if title else "")
    header += ("> Official English translation (RU→EN) via "
               f"`{model}`, by `tools/read_pass/translate.py`.\n"
               f"> Source: `{os.path.basename(src_path)}`. "
               "Faithful full translation, not a summary.\n\n---\n\n")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(header + body)

    data = {
        "out_path": out_path,
        "n_windows": len(windows),
        "n_translated": len(translated),
        "n_failed": len(errors),
        "src_chars": len(text),
        "out_chars": len(body),
    }
    return _envelope(len(errors) == 0, data, {"model": model}, errors)


if __name__ == "__main__":
    import sys
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: set GEMINI_API_KEY"); raise SystemExit(2)
    # default: translate the biography
    src = "data/raw_texts/sharma_ru/mossin_awakener_ru.txt"
    out = "tools/read_pass/translations/the_awakener_EN.md"
    title = "The Awakener — Biography of Shailendra Sharma (Katya Mossin)"
    if "--gita" in sys.argv:
        src = "data/raw_texts/sharma_ru/gita_ru.txt"
        out = "tools/read_pass/translations/yogeshwari_gita_RU2EN.md"
        title = "Yogeshwari Shrimad Bhagavad Gita — Sharma Commentary (RU→EN)"
    env = run(src, api_key, out, title=title)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        d = env.get("data") or {}
        print(f"success={env['success']} windows={d.get('n_windows')} "
              f"translated={d.get('n_translated')} failed={d.get('n_failed')}")
        print(f"  → {d.get('out_path')} ({d.get('out_chars',0):,} chars EN)")
        if env.get("errors"):
            print(f"  errors: {env['errors'][:3]}")
