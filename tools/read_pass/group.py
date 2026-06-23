"""group — turn verse-sized chunks into chapter-sized reading WINDOWS.

The unit of comprehension is a chapter, not a 68-word verse. Chunks are keyed
`<purana>-<chapterField>-<globalSeq>`; the `chapter` field is NOT canto-aware
and collides across cantos, but the trailing global sequence is monotonic. So a
chapter window = a CONTIGUOUS RUN of identical `chapter` value in global-seq
order. Grouping by `chapter` *value* (bucketing) would silently merge unrelated
chapters from different cantos — the scope bug this tool exists to avoid.

JSON contract (Rule 0, precondition B):
  run(jsonl_path) -> {success, data:{windows:[...]}, metadata, errors}
Each window: {purana, chapter_label, seq_start, seq_end, n_chunks, chunk_ids,
              verse_ranges, text}
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

# Mono-chapter texts (Ramayana, Skanda, etc.) dump the entire text into one
# window. Sub-window any run exceeding this many chunks so each piece fits
# the LLM's context (~80 chunks ≈ Bhagavata median chapter, ~5K words).
MAX_WINDOW_CHUNKS = 80


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _seq_of(chunk: Dict[str, Any]) -> int:
    """Global monotonic sequence = trailing integer of the id."""
    try:
        return int(str(chunk["id"]).rsplit("-", 1)[1])
    except (KeyError, ValueError, IndexError):
        return -1


def run(jsonl_path: str) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {"path": jsonl_path}

    if not os.path.isfile(jsonl_path):
        return _envelope(False, None, metadata,
                         [{"code": "no_file", "message": f"not found: {jsonl_path}"}])

    chunks: List[Dict[str, Any]] = []
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as e:
        return _envelope(False, None, metadata,
                         [{"code": "read_error", "message": str(e)}])

    if not chunks:
        return _envelope(False, None, metadata,
                         [{"code": "empty", "message": "no chunks in file"}])

    # Order by the global monotonic sequence so narrative order is preserved.
    chunks.sort(key=_seq_of)

    windows: List[Dict[str, Any]] = []
    cur_chapter = object()  # sentinel that never equals a real chapter value
    win: Dict[str, Any] = {}

    def _flush():
        if win:
            win["n_chunks"] = len(win["chunk_ids"])
            win["text"] = "\n".join(win["_texts"]).strip()
            del win["_texts"]
            windows.append(dict(win))

    for ch in chunks:
        chapter = ch.get("chapter")
        if chapter != cur_chapter:
            _flush()
            cur_chapter = chapter
            win = {
                "purana": ch.get("purana", ""),
                "chapter_label": ch.get("book_section") or f"Chapter {chapter}",
                "seq_start": _seq_of(ch),
                "seq_end": _seq_of(ch),
                "chunk_ids": [],
                "verse_ranges": [],
                "_texts": [],
            }
        win["seq_end"] = _seq_of(ch)
        win["chunk_ids"].append(ch.get("id"))
        vr = ch.get("verse_range")
        if vr is not None:
            win["verse_ranges"].append(vr)
        win["_texts"].append(ch.get("text", ""))
    _flush()

    # Sub-window any mega-windows that exceed MAX_WINDOW_CHUNKS.
    # Preserves narrative order; labels sub-windows "Chapter X (part N)".
    final: List[Dict[str, Any]] = []
    for w in windows:
        if w["n_chunks"] <= MAX_WINDOW_CHUNKS:
            final.append(w)
            continue
        # split into stride-sized pieces
        cids = w["chunk_ids"]
        vrs = w["verse_ranges"]
        texts = w["text"].split("\n")
        purana = w["purana"]
        label = w["chapter_label"]
        part = 0
        for i in range(0, len(cids), MAX_WINDOW_CHUNKS):
            part += 1
            slc = slice(i, i + MAX_WINDOW_CHUNKS)
            sub_cids = cids[slc]
            sub_vrs = vrs[slc] if len(vrs) > i else []
            sub_texts = texts[slc]
            sub = {
                "purana": purana,
                "chapter_label": f"{label} (part {part})",
                "seq_start": int(str(sub_cids[0]).rsplit("-", 1)[1]),
                "seq_end": int(str(sub_cids[-1]).rsplit("-", 1)[1]),
                "chunk_ids": sub_cids,
                "verse_ranges": sub_vrs,
                "n_chunks": len(sub_cids),
                "text": "\n".join(sub_texts).strip(),
            }
            final.append(sub)

    metadata["n_chunks_in"] = len(chunks)
    metadata["n_windows"] = len(final)
    metadata["n_sub_windowed"] = len(final) - len(windows)
    return _envelope(True, {"windows": final}, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    path = ""
    if "--input" in argv:
        path = argv[argv.index("--input") + 1]
    env = run(path)
    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message']}")
        return 2
    else:
        d = env["data"]
        print(f"OK: {len(d['windows'])} chapter windows from "
              f"{env['metadata']['n_chunks_in']} chunks")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
