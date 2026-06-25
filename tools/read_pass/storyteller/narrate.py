"""narrate — the "Tell" half of the storyteller, over read_pass records.

The storyteller is two verbs: Tell (this) + Ask (the router in check.py + recall).
This module turns a corpus's records into an ORDERED list of story BEATS and
serves them one at a time against a Bookmark.

A "beat" = one record's narratable content (title, summary/arc, who's in it). The
live app phrases it in a teller's voice via an LLM; for standalone testing we also
provide `beat_as_text()` — a plain rendering so you can play it with no API key.

Reuse, not fork: this READS `tools/read_pass/out/<corpus>_v*.records.jsonl` — the
same files the comprehension engine produced. No DB, no network. To make the app
fully standalone later, point `RECORDS_DIR` at its own copy — path change, not a
rewrite.

⚠️ Ordering caveat (real, found 2026-06-24): records are ordered by their minimum
chunk-sequence, which on the Ramayana is only APPROXIMATELY story order (the
Valmiki framing chapter sorts late). Good enough to travel the corpus; not a
guaranteed canonical reading order. Flagged in metadata.
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

RECORDS_DIR = "tools/read_pass/out"


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _min_seq(rec: Dict[str, Any]) -> int:
    """Record position = smallest trailing-int of its chunk_ids (the spine)."""
    cids = (rec.get("_provenance", {}) or {}).get("chunk_ids", []) or []
    seqs = []
    for c in cids:
        tail = str(c).rsplit("-", 1)[-1]
        if tail.isdigit():
            seqs.append(int(tail))
    if seqs:
        return min(seqs)
    ss = (rec.get("_provenance", {}) or {}).get("seq_start")
    return ss if isinstance(ss, int) else 1_000_000


@dataclass
class Beat:
    """One narratable unit of story."""
    index: int
    title: str
    summary: str
    arc: str
    characters: List[str]
    chapter_label: str

    def text(self) -> str:
        """Plain teller rendering (no LLM) — for standalone testing."""
        cast = ", ".join(self.characters[:6]) if self.characters else ""
        head = self.title or self.chapter_label or f"Part {self.index + 1}"
        body = self.summary or self.arc or "(no narration text for this beat)"
        out = f"  〜 {head} 〜\n\n{body}"
        if cast:
            out += f"\n\n  (with: {cast})"
        return out


def load_beats(corpus: str, records_dir: str = RECORDS_DIR) -> Dict[str, Any]:
    """Load a corpus's records, ordered, into narratable beats.

    `corpus` matches the records filename stem, e.g. 'ramayana' → ramayana_v*.records.jsonl
    """
    pattern = os.path.join(records_dir, f"{corpus}_v*.records.jsonl")
    matches = sorted(glob.glob(pattern))
    if not matches:
        # also allow an exact filename
        exact = os.path.join(records_dir, f"{corpus}.records.jsonl")
        if os.path.isfile(exact):
            matches = [exact]
    if not matches:
        return _envelope(False, None, {"corpus": corpus, "pattern": pattern},
                         [{"code": "no_records", "message": f"no records file for '{corpus}' in {records_dir}"}])

    path = matches[0]
    try:
        records = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    except (OSError, json.JSONDecodeError) as e:
        return _envelope(False, None, {"path": path},
                         [{"code": "read_error", "message": str(e)[:200]}])
    if not records:
        return _envelope(False, None, {"path": path},
                         [{"code": "empty", "message": "no records"}])

    records.sort(key=_min_seq)
    beats: List[Beat] = []
    for i, r in enumerate(records):
        s = r.get("story", {}) or {}
        beats.append(Beat(
            index=i,
            title=s.get("title", "") or "",
            summary=(r.get("chapter_summary") or "").strip(),
            arc=(s.get("arc") or "").strip(),
            characters=list(s.get("characters", []) or []),
            chapter_label=(r.get("_provenance", {}) or {}).get("chapter_label", "") or "",
        ))

    data = {
        "corpus": corpus,
        "n_beats": len(beats),
        "beats": [b.__dict__ for b in beats],
    }
    meta = {"path": path, "ordering": "approximate (min chunk-seq; not guaranteed canonical)"}
    return _envelope(True, data, meta, [])


def beat_at(beats: List[Dict[str, Any]], index: int) -> Optional[Beat]:
    """Fetch the beat at index (clamped); None if out of range."""
    if not beats:
        return None
    if index < 0 or index >= len(beats):
        return None
    return Beat(**beats[index])


def beat_as_text(beats: List[Dict[str, Any]], index: int) -> str:
    b = beat_at(beats, index)
    return b.text() if b else "(the story is over — no more beats)"


# CLI: load + report a corpus's beats (sanity check)
def main(argv: List[str]) -> int:
    corpus = "ramayana"
    if "--corpus" in argv:
        corpus = argv[argv.index("--corpus") + 1]
    env = load_beats(corpus)
    if "--json" in argv:
        # trim beats for readability unless --full
        if "--full" not in argv and env["success"]:
            env = dict(env)
            env["data"] = dict(env["data"])
            env["data"]["beats"] = env["data"]["beats"][:2]
        print(json.dumps(env, indent=2, ensure_ascii=False))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message']}")
        return 2
    else:
        d = env["data"]
        print(f"OK: {corpus} → {d['n_beats']} beats ({env['metadata']['ordering']})")
        print("\nfirst beat:\n")
        print(beat_as_text(d["beats"], 0))
    return 0 if env["success"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
