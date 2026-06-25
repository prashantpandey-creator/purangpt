"""schema — the JSON shape the comprehension pass emits per chapter.

ONE chapter window -> ONE record feeding all three of daddy's projects:
  ① consciousness graph : entities[] + relationships[]
  ② story corpus        : story{}
  ③ distilled teachings : teachings[]
Every node carries the verse_ranges it came from (provenance for the Phase-2
cite-later verify pass). This module is pure data: the response schema handed to
Gemini's structured-output mode, plus a validator. No network, fully testable.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Gemini responseSchema (OpenAPI-subset). Keeps the model's JSON on-contract.
RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "chapter_summary": {"type": "string"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string"},  # deity|sage|king|concept|place|practice|text
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "verse_ranges": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "kind", "verse_ranges"],
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "src": {"type": "string"},
                    "rel": {"type": "string"},   # teaches|curses|incarnates_as|father_of|...
                    "dst": {"type": "string"},
                    "verse_ranges": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["src", "rel", "dst", "verse_ranges"],
            },
        },
        "story": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "arc": {"type": "string"},        # what happens, beginning->end
                "characters": {"type": "array", "items": {"type": "string"}},
                "timeline_note": {"type": "string"},  # past/present/future framing
                "comic_potential": {"type": "string"},  # one line: is this filmable?
            },
            "required": ["title", "arc"],
        },
        "teachings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "teaching": {"type": "string"},
                    "lens_note": {"type": "string"},  # what it means in Sharma's frame
                    "verse_ranges": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["teaching", "verse_ranges"],
            },
        },
    },
    "required": ["chapter_summary", "entities", "relationships", "story", "teachings"],
}

_TOP_KEYS = set(RESPONSE_SCHEMA["required"])


def validate(obj: Any) -> List[str]:
    """Return a list of human-readable problems; empty list == valid enough.

    Deliberately lenient on optional fields, strict on the contract spine: the
    five top-level keys, and that every entity/relationship/teaching carries the
    verse_ranges provenance that the cite-later pass depends on.
    """
    problems: List[str] = []
    if not isinstance(obj, dict):
        return ["root is not an object"]
    for k in _TOP_KEYS:
        if k not in obj:
            problems.append(f"missing top-level key: {k}")
    for i, e in enumerate(obj.get("entities", []) or []):
        if not e.get("name"):
            problems.append(f"entity[{i}] has no name")
        if "verse_ranges" not in e:
            problems.append(f"entity[{i}] missing verse_ranges (provenance)")
    for i, r in enumerate(obj.get("relationships", []) or []):
        if not (r.get("src") and r.get("rel") and r.get("dst")):
            problems.append(f"relationship[{i}] incomplete triple")
        if "verse_ranges" not in r:
            problems.append(f"relationship[{i}] missing verse_ranges (provenance)")
    for i, t in enumerate(obj.get("teachings", []) or []):
        if not t.get("teaching"):
            problems.append(f"teaching[{i}] empty")
        if "verse_ranges" not in t:
            problems.append(f"teaching[{i}] missing verse_ranges (provenance)")
    story = obj.get("story")
    if not isinstance(story, dict) or not story.get("arc"):
        problems.append("story missing or has no arc")
    return problems
