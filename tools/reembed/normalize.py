"""normalize — pure IAST-to-Devanagari corpus normalization logic.

No IO, no model. Called by check.py and unit-tested in test_check.py.

Rule: scripture rows that are IAST-romanized get transliterated to Devanagari
so that bge-m3 (trained on web Devanagari) can retrieve them from Sanskrit queries.
Commentary (GURUJI_CATEGORIES + darshan- prefix) passes through unchanged —
it is English/Russian and already in-distribution for the model.
"""
from __future__ import annotations
import re
from typing import Any

GURUJI_CATEGORIES = {"yogic-commentary", "yogic-discourse", "yoga_commentary"}

_MARK = re.compile(r"[A-Za-z]{1,6}_\d+[,.][\d.,]+")
_DANDA = re.compile(r"[।॥]")
_DEVA = re.compile(r"[ऀ-ॿ]")
_IAST = re.compile(r"[āīūṛṝḷṃṁḥṭḍṇśṣĀĪŪṚṜḶṂṀḤṬḌṆŚṢ]")


def is_guruji(category: str, row_id: str) -> bool:
    return (category or "").lower() in GURUJI_CATEGORIES or str(row_id).startswith("darshan-")


def detect_script(text: str) -> str:
    """Returns 'devanagari', 'iast', or 'latin'."""
    if len(_DEVA.findall(text)) > 5:
        return "devanagari"
    if _IAST.search(text):
        return "iast"
    return "latin"


def clean(text: str) -> str:
    """Strip inline chunk markers and dandas, collapse whitespace. Max 512 chars."""
    t = _MARK.sub(" ", text)
    t = _DANDA.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()[:512]


def transliterate_iast_to_deva(text: str) -> str:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
    try:
        return transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)
    except Exception:
        return text


def normalize_row(content: str, category: str, row_id: str) -> dict[str, Any]:
    """Pure normalize. Returns {embed_text, script, changed}.
    'embed_text' is what should be fed to the embedding model.
    'script' is one of: iast2deva | devanagari | latin | commentary.
    'changed' is True when content was transliterated."""
    if is_guruji(category, row_id):
        return {"embed_text": clean(content), "script": "commentary", "changed": False}
    cleaned = clean(content)
    script = detect_script(cleaned)
    if script == "iast":
        deva = transliterate_iast_to_deva(cleaned)
        return {"embed_text": deva, "script": "iast2deva", "changed": True}
    return {"embed_text": cleaned, "script": script, "changed": False}
