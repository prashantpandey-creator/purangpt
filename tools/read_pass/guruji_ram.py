"""guruji_ram — distill Sharma's COMPLETE worldview into a structured reference.

Daddy's correction: the identity model was built on one grepped paragraph. This
reads the ENTIRE Sharma corpus and produces the "Guruji RAM" — the decryption
framework the whole pipeline sits on. Everything (extraction lens, identity
model, teaching synthesis, insights) should reference THIS, not ad-hoc snippets.

The corpus (data/raw_texts/sharma/):
  yogeshwari_gita_full.txt  — 79K words, the Gita commentary (the core lens)
  shiv_sutra.txt            — Kashmir Shaivism: Consciousness=soul, Knowledge=bondage
  yoga_alchemy.txt          — prana=mercury, apana=sulfur (rasayana)
  gorakh_bodh.txt           — Nath yoga dialogue
  khechari_vidya.txt        — khechari mudra
  ojas_amrita.txt           — ojas/amrita

The RAM is a structured worldview (not a summary):
  decryption_keys  — symbol → yogic meaning (Kurukshetra→body, Krishna→Kutastha)
  core_principles  — load-bearing metaphysical claims
  identity_doctrine— how Sharma treats names/forms/the One-and-many (drives identity.py)
  cosmology        — his time/creation model (drives timeline.py)
  practice_axes    — the inner-yoga dimensions he reads everything through

This is legitimate reasoner work (Rule 0 "NO" branch): judgment over unstructured
prose, not a decision tree.

JSON contract (Rule 0, precond B):
  run(corpus_dir, key) -> {success, data:{framework, ...}, metadata, errors}
"""
from __future__ import annotations

import glob
import json
import os
import re
import urllib.request
from typing import Any, Callable, Dict, List, Optional


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


FRAMEWORK_SCHEMA = {
    "type": "object",
    "properties": {
        "decryption_keys": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string",
                               "description": "The Puranic/Vedic symbol, name, place, or object"},
                    "meaning": {"type": "string",
                                "description": "Its decoded yogic/inner meaning per Sharma"},
                },
                "required": ["symbol", "meaning"],
            },
        },
        "core_principles": {
            "type": "array", "items": {"type": "string"},
            "description": "The load-bearing metaphysical claims Sharma makes",
        },
        "identity_doctrine": {
            "type": "string",
            "description": "How Sharma treats names, forms, the One and the many",
        },
        "cosmology": {
            "type": "string",
            "description": "Sharma's model of time, creation, dissolution",
        },
        "practice_axes": {
            "type": "array", "items": {"type": "string"},
            "description": "The inner-yoga dimensions Sharma reads texts through",
        },
    },
    "required": ["decryption_keys", "core_principles", "identity_doctrine",
                 "cosmology", "practice_axes"],
}


def _empty_framework() -> Dict[str, Any]:
    return {"decryption_keys": [], "core_principles": [], "identity_doctrine": "",
            "cosmology": "", "practice_axes": []}


_DEFAULT_RAM_PATH = "tools/read_pass/out/guruji_ram.json"


def load(ram_path: str = _DEFAULT_RAM_PATH) -> Dict[str, Any]:
    """LIVE ACCESSOR — the built RAM as the framework dict other stages consult.

    This is what makes the RAM an ongoing input instead of a dead doc:
    comprehend.py (lens), graph.py (identity doctrine), and the valence stage
    all call guruji_ram.load() and read Sharma's framework. Re-reading Guruji
    (new books → rebuild the json) automatically updates everything downstream.
    Returns an empty framework if the RAM hasn't been built yet (never crashes).
    """
    try:
        env = json.load(open(ram_path, encoding="utf-8"))
        fw = (env.get("data") or {}).get("framework")
        if not fw:
            return _empty_framework()
        # ensure all keys present
        base = _empty_framework()
        base.update({k: fw.get(k, base[k]) for k in base})
        return base
    except (OSError, json.JSONDecodeError):
        return _empty_framework()


def keys_for_text(text: str, framework: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Return the RAM decryption_keys whose symbol appears in the given text.

    Used by the extraction lens (comprehend.py): instead of a few hand-picked
    examples, inject ONLY the relevant Sharma keys for THIS chapter — the full
    codex, scoped per-chapter. Diacritic-insensitive match.
    """
    import unicodedata

    def _strip(s):
        nf = unicodedata.normalize("NFKD", str(s))
        return "".join(c for c in nf if not unicodedata.combining(c)).lower()

    if framework is None:
        framework = load()
    htext = _strip(text)
    out = []
    for k in framework.get("decryption_keys", []):
        sym = k.get("symbol", "")
        # match on the first word of the symbol (handles "Krishna as charioteer")
        head = _strip(sym.split("(")[0].split(" as ")[0].strip())
        if len(head) >= 3 and head in htext:
            out.append(k)
    return out


def load_corpus(corpus_dir: str) -> List[Dict[str, str]]:
    """Load every .txt in the Sharma corpus dir, labeled by source."""
    sources = []
    for path in sorted(glob.glob(os.path.join(corpus_dir, "*.txt"))):
        name = os.path.basename(path).replace(".txt", "")
        text = open(path, encoding="utf-8", errors="replace").read()
        if text.strip():
            sources.append({"source": name, "text": text, "path": path})
    return sources


def make_windows(text: str, max_chars: int = 18000) -> List[str]:
    """Split text into windows on paragraph boundaries, each <= max_chars.

    Guarantees full coverage (no silent truncation) — every paragraph lands
    in exactly one window.
    """
    paras = re.split(r"\n\s*\n", text)
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


def merge_frameworks(frameworks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Union partial frameworks from multiple windows into one.

    Lists are deduped-unioned; scalar prose fields take the longest non-empty
    (richest) value. decryption_keys deduped by normalized symbol.
    """
    merged = _empty_framework()
    seen_symbols = {}
    seen_principles = set()
    seen_axes = set()

    for fw in frameworks:
        if not fw:
            continue
        for k in (fw.get("decryption_keys") or []):
            sym = (k.get("symbol") or "").strip()
            key = sym.lower()
            if sym and key not in seen_symbols:
                seen_symbols[key] = k
                merged["decryption_keys"].append(k)
        for p in (fw.get("core_principles") or []):
            pk = p.strip().lower()
            if p.strip() and pk not in seen_principles:
                seen_principles.add(pk)
                merged["core_principles"].append(p.strip())
        for a in (fw.get("practice_axes") or []):
            ak = a.strip().lower()
            if a.strip() and ak not in seen_axes:
                seen_axes.add(ak)
                merged["practice_axes"].append(a.strip())
        for field in ("identity_doctrine", "cosmology"):
            v = (fw.get(field) or "").strip()
            if len(v) > len(merged[field]):
                merged[field] = v
    return merged


def _call_reasoner(prompt: str, model: str, api_key: str,
                   timeout: int = 300) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 16384,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    return resp["choices"][0]["message"]["content"]


def build_prompt(text: str, source: str = "") -> str:
    return f"""You are studying the complete teachings of Sri Sri Shailendra Sharma
(Guruji), a living Kriya-Yoga master in the unbroken lineage. His method: the
Puranas, Gita, and Vedas are ENCRYPTED manuals of inner yogic process. He decodes
their symbols, names, places, and events into their hidden yogic meaning.

Below is a section of his writing{f' (from {source})' if source else ''}. Extract his
DECRYPTION FRAMEWORK from this section — the conceptual machinery, not a summary.

Extract:
1. decryption_keys — every symbol/name/place/object he decodes, with its inner
   yogic meaning. (e.g. Kurukshetra → the physical body; Krishna → Kutastha
   Chaitanya / witnessing consciousness; the conch → ...). Be exhaustive.
2. core_principles — the load-bearing metaphysical claims (e.g. "the One Self
   appears as the many", "the body is the field of yoga", "time is standstill
   but appears divided").
3. identity_doctrine — specifically how he treats NAMES, FORMS, and the
   relationship between the One and the many (this governs how we model entity
   identity in a knowledge graph).
4. cosmology — his model of time, creation, and dissolution.
5. practice_axes — the inner-yoga dimensions he reads everything through
   (pranayama, kundalini, samadhi, the chakras, ojas, khechari, etc.).

If a category has nothing in this section, return it empty. Be precise and
faithful to HIS words — do not import generic Vedanta.

TEXT:
{text}

Return ONLY valid JSON matching this schema:
{json.dumps(FRAMEWORK_SCHEMA, indent=1)}"""


def extract_framework(text: str, api_key: str,
                      model: str = "deepseek-v4-pro",
                      source: str = "",
                      caller: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    """Extract Sharma's framework from one text window."""
    fn = caller or _call_reasoner
    prompt = build_prompt(text, source)
    raw = fn(prompt, model, api_key)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _empty_framework()


def run(corpus_dir: str, api_key: str,
        model: str = "deepseek-v4-pro",
        max_chars: int = 18000,
        caller: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    """Read the full Sharma corpus → distilled framework (the Guruji RAM)."""
    sources = load_corpus(corpus_dir)
    if not sources:
        return _envelope(False, None, {},
                         [{"code": "empty_corpus", "message": f"no .txt in {corpus_dir}"}])

    frameworks = []
    errors = []
    window_log = []
    for src in sources:
        windows = make_windows(src["text"], max_chars=max_chars)
        window_log.append({"source": src["source"], "n_windows": len(windows)})
        for i, w in enumerate(windows):
            try:
                fw = extract_framework(w, api_key, model=model,
                                       source=src["source"], caller=caller)
                frameworks.append(fw)
            except Exception as e:
                errors.append({"code": "window_failed",
                               "message": f"{src['source']}#{i}: {str(e)[:150]}"})

    framework = merge_frameworks(frameworks)
    data = {
        "framework": framework,
        "n_sources": len(sources),
        "n_windows": sum(w["n_windows"] for w in window_log),
        "window_log": window_log,
        "n_decryption_keys": len(framework["decryption_keys"]),
        "n_core_principles": len(framework["core_principles"]),
    }
    return _envelope(len(errors) == 0, data,
                     {"model": model, "corpus_dir": corpus_dir}, errors)


if __name__ == "__main__":
    import sys
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    corpus = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
        else "data/raw_texts/sharma"
    if not api_key:
        print("ERROR: set DEEPSEEK_API_KEY")
        raise SystemExit(2)
    env = run(corpus, api_key)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    elif not env["success"]:
        print(f"PARTIAL/ERROR: {len(env.get('errors',[]))} window failures")
        d = env.get("data") or {}
        if d:
            print(f"  Still extracted {d.get('n_decryption_keys',0)} keys from "
                  f"{d.get('n_windows',0)} windows")
    else:
        d = env["data"]
        fw = d["framework"]
        print(f"GURUJI RAM built from {d['n_sources']} sources, {d['n_windows']} windows")
        print(f"  {d['n_decryption_keys']} decryption keys, {d['n_core_principles']} principles")
        print(f"\n=== IDENTITY DOCTRINE ===\n{fw['identity_doctrine'][:600]}")
        print(f"\n=== COSMOLOGY ===\n{fw['cosmology'][:400]}")
        print(f"\n=== Sample decryption keys ===")
        for k in fw["decryption_keys"][:15]:
            print(f"  {k['symbol']:25s} → {k['meaning'][:70]}")
