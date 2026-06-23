"""biography — distill Sharma's life/lineage from the Russian biography.

Mossin's "The Awakener" (Пробуждающий) — the authorized 1,121-page biography of
Shailendra Sharma, 5th Guru of the Kriya Yoga lineage. Russian. The LLM reads it
directly (translate + structure in one pass) and emits an English lineage
framework that connects the abstract graph entities to Sharma's LIVED encounters
with the Puranic cosmos (gods, avatars, Babaji, the Nath siddhas, alchemy).

This complements guruji_ram.py: that distills his DECRYPTION framework (how he
reads texts); this distills his BIOGRAPHY (who he is, the lineage, what he
experienced). Both feed the brain.

  lineage_chain     — the guru-parampara up to Sharma (Babaji → … → Sharma)
  biographical_arc  — key life events / realizations, ordered
  entity_encounters — graph entities Sharma personally encountered + how
  places            — sacred sites tied to his life (Govardhan, Gaya, …)

JSON contract (Rule 0, precond B):
  run(text_path, key) -> {success, data:{biography, ...}, metadata, errors}
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Callable, Dict, List, Optional


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


BIOGRAPHY_SCHEMA = {
    "type": "object",
    "properties": {
        "lineage_chain": {
            "type": "array", "items": {"type": "string"},
            "description": "Guru-parampara: who taught whom, ordered, ending at Sharma",
        },
        "biographical_arc": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "event": {"type": "string"},
                    "order": {"type": "integer"},
                },
                "required": ["event"],
            },
            "description": "Key life events / realizations in this passage",
        },
        "entity_encounters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string",
                               "description": "A god/avatar/guru/being from the Puranic cosmos"},
                    "encounter": {"type": "string",
                                  "description": "How Sharma encountered/related to them"},
                },
                "required": ["entity", "encounter"],
            },
        },
        "places": {
            "type": "array", "items": {"type": "string"},
            "description": "Sacred sites tied to Sharma's life",
        },
    },
    "required": ["lineage_chain", "biographical_arc", "entity_encounters", "places"],
}


def make_windows(text: str, max_chars: int = 16000) -> List[str]:
    """Split on paragraph/newline boundaries with full coverage."""
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


def _empty():
    return {"lineage_chain": [], "biographical_arc": [],
            "entity_encounters": [], "places": []}


def merge_biographies(parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Union partial biography frameworks, preserving lineage order + dedup."""
    merged = _empty()
    seen_lineage = set()
    seen_places = set()
    seen_enc = set()
    for fw in parts:
        if not fw:
            continue
        for g in (fw.get("lineage_chain") or []):
            gk = g.strip().lower()
            if g.strip() and gk not in seen_lineage:
                seen_lineage.add(gk)
                merged["lineage_chain"].append(g.strip())
        for ev in (fw.get("biographical_arc") or []):
            if ev and ev.get("event"):
                merged["biographical_arc"].append(ev)
        for enc in (fw.get("entity_encounters") or []):
            ek = (enc.get("entity", "") + "|" + enc.get("encounter", "")[:40]).lower()
            if enc.get("entity") and ek not in seen_enc:
                seen_enc.add(ek)
                merged["entity_encounters"].append(enc)
        for pl in (fw.get("places") or []):
            pk = pl.strip().lower()
            if pl.strip() and pk not in seen_places:
                seen_places.add(pk)
                merged["places"].append(pl.strip())
    return merged


def _call_reasoner(prompt: str, model: str, api_key: str,
                   timeout: int = 180) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    return resp["choices"][0]["message"]["content"]


def build_prompt(russian_text: str) -> str:
    return f"""This is Russian text from "Пробуждающий" (The Awakener) — Katya Mossin's
authorized biography of Shailendra Sharma, the FIFTH Guru of the Kriya Yoga lineage
(the lineage of Babaji, Lahiri Mahasaya, Yukteshwar, Yogananda).

Read the Russian and extract an English-language LINEAGE & BIOGRAPHY framework:

1. lineage_chain — any guru-to-disciple transmission named, ordered.
   CRITICAL: Sharma's OWN lineage DIVERTS at Lahiri Mahasaya and stays in the
   Lahiri FAMILY: Lahiri Mahasaya → his son Tinkori Lahiri → Lahiri's GRANDSON
   Satyacharan Lahiri → Shailendra Sharma. The Yukteshwar/Yogananda branch is a
   SEPARATE upstream tree, NOT Sharma's direct transmission — do not conflate them.
   If the text states a family relationship (son/grandson), preserve it.
2. biographical_arc — key events/realizations in Sharma's life from this passage.
3. entity_encounters — gods, avatars, gurus, Nath siddhas, spirits, or beings from
   the Puranic/yogic cosmos that Sharma personally encountered, and HOW (this links
   the biography to the knowledge graph of the Puranas). e.g. "Hanuman — performed
   puja to him at Govardhan".
4. places — sacred sites tied to his life (Govardhan, Gaya, Mehandipur, etc.).

Translate faithfully. If a category is empty in this passage, return it empty.

RUSSIAN TEXT:
{russian_text}

Return ONLY valid JSON matching this schema:
{json.dumps(BIOGRAPHY_SCHEMA, indent=1)}"""


def extract_biography(russian_text: str, api_key: str,
                      model: str = "deepseek-chat",
                      caller: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    fn = caller or _call_reasoner
    raw = fn(build_prompt(russian_text), model, api_key)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _empty()


def run(text_path: str, api_key: str,
        model: str = "deepseek-chat",
        max_chars: int = 16000,
        max_workers: int = 8,
        caller: Optional[Callable[..., str]] = None) -> Dict[str, Any]:
    """Read the Russian biography → distilled English lineage framework."""
    try:
        text = open(text_path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return _envelope(False, None, {}, [{"code": "read_error", "message": str(e)}])
    if not text.strip():
        return _envelope(False, None, {}, [{"code": "empty", "message": "no text"}])

    windows = make_windows(text, max_chars=max_chars)
    parts, errors = [], []

    if caller is not None:
        # deterministic path for tests
        for w in windows:
            parts.append(extract_biography(w, api_key, model=model, caller=caller))
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(extract_biography, w, api_key, model): i
                    for i, w in enumerate(windows)}
            for f in as_completed(futs):
                try:
                    parts.append(f.result(timeout=200))
                except Exception as e:
                    errors.append({"code": "window_failed", "message": str(e)[:150]})

    bio = merge_biographies(parts)
    data = {
        "biography": bio,
        "n_windows": len(windows),
        "n_lineage": len(bio["lineage_chain"]),
        "n_events": len(bio["biographical_arc"]),
        "n_encounters": len(bio["entity_encounters"]),
        "n_places": len(bio["places"]),
    }
    return _envelope(len(errors) == 0, data, {"model": model}, errors)


if __name__ == "__main__":
    import sys, os
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
        else "data/raw_texts/sharma_ru/mossin_awakener_ru.txt"
    if not api_key:
        print("ERROR: set DEEPSEEK_API_KEY"); raise SystemExit(2)
    env = run(path, api_key)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        d = env.get("data") or {}
        print(f"success={env['success']} windows={d.get('n_windows')} "
              f"errors={len(env.get('errors',[]))}")
        if d:
            b = d["biography"]
            print(f"  lineage({d['n_lineage']}): {' → '.join(b['lineage_chain'][:8])}")
            print(f"  events: {d['n_events']}, encounters: {d['n_encounters']}, places: {d['n_places']}")
            print(f"\n  Sample entity encounters:")
            for e in b["entity_encounters"][:10]:
                print(f"    {e['entity']:18s} — {e['encounter'][:60]}")
            print(f"\n  Places: {', '.join(b['places'][:20])}")
