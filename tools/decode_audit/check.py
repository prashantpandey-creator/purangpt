"""decode_audit — the TRUE pending-comprehension report, keyed on chunk_ids.

Hand-counting the read_pass backlog gave three different answers because filename,
chapter_label and seq_start all lie (records are cross-filed; labels collide; seq is
unstable across re-chunking). The one globally-stable, text-namespaced key is
`_provenance.chunk_ids` (e.g. 'bhagavata-1-1'). This tool keys coverage on that and
reports, per source text, how many chapter-windows have NO covered chunk — the real
work an in-house decode fan-out must do.

Pure core (`audit_coverage`, `covered_from_records`) = set arithmetic, fixture-tested.
`run()` wires it to the live out/*.records.jsonl + data/chunks/*.jsonl (needs the repo).

JSON contract (Rule 0, precondition B). Run from purangpt/ repo root:
  venv/bin/python -m tools.decode_audit.check --json
"""
from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Set

OUT_DIR = "tools/read_pass/out"
CHUNK_DIR = "data/chunks"
_SKIP_CHUNKS = {"all_chunks", "sharma_texts"}


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ── pure core (tested against fixtures) ──────────────────────────────────────
def covered_from_records(records: Iterable[Dict[str, Any]]) -> Set[str]:
    """Every chunk_id that appears in any record's _provenance — the set of chunks
    we have ALREADY comprehended, regardless of which file the record sits in."""
    covered: Set[str] = set()
    for r in records:
        for cid in r.get("_provenance", {}).get("chunk_ids", []) or []:
            covered.add(cid)
    return covered


def audit_coverage(covered_chunk_ids: Set[str],
                   windows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Given the covered chunk_id set and a list of chapter windows, count how many
    windows are DONE (≥1 chunk covered) vs PENDING, and list the pending chunk_ids.

    Any-overlap rule: a window is done if ANY of its chunk_ids is covered (records
    are per-chapter; partial overlap from re-chunking still means we read it).
    """
    done = 0
    pending = 0
    pending_chunk_ids: List[str] = []
    for w in windows:
        cids = w.get("chunk_ids", []) or []
        if any(c in covered_chunk_ids for c in cids):
            done += 1
        else:
            pending += 1
            if cids:
                pending_chunk_ids.append(cids[0])  # primary chunk = handoff key
    data = {
        "windows": len(windows),
        "done": done,
        "pending": pending,
        "pending_chunk_ids": pending_chunk_ids,
    }
    return _envelope(True, data, {}, [])


# ── live wiring (reads the repo; not unit-tested — the core is) ───────────────
def _load_all_covered() -> Set[str]:
    covered: Set[str] = set()
    for f in glob.glob(os.path.join(OUT_DIR, "*.records.jsonl")):
        with open(f) as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for cid in rec.get("_provenance", {}).get("chunk_ids", []) or []:
                    covered.add(cid)
    return covered


def run(min_gap: int = 1) -> Dict[str, Any]:
    """Walk every chunk file, group it into windows, and report per-text pending
    counts against the global covered-chunk set. `min_gap`: hide texts with a
    smaller gap (1 = report any gap)."""
    metadata = {"out_dir": OUT_DIR, "chunk_dir": CHUNK_DIR, "min_gap": min_gap}
    try:
        from tools.read_pass import group  # local import: keeps the pure core import-light
    except Exception as e:  # noqa
        return _envelope(False, None, metadata,
                         [{"code": "import_failed", "message": str(e)[:200]}])

    if not os.path.isdir(CHUNK_DIR):
        return _envelope(False, None, metadata,
                         [{"code": "no_chunks", "message": f"{CHUNK_DIR} not found (run from purangpt/ root)"}])

    covered = _load_all_covered()
    metadata["covered_chunks"] = len(covered)

    texts: List[Dict[str, Any]] = []
    total_pending = 0
    pending_by_text: Dict[str, List[str]] = {}
    errors: List[Dict[str, str]] = []
    for chunk in sorted(glob.glob(os.path.join(CHUNK_DIR, "*.jsonl"))):
        name = os.path.basename(chunk).replace(".jsonl", "")
        if name in _SKIP_CHUNKS:
            continue
        g = group.run(chunk)
        if not g.get("success"):
            errors.append({"code": "group_failed", "message": f"{name}: {g.get('errors')}"})
            continue
        windows = [{"chapter_label": w.get("chapter_label"),
                    "chunk_ids": w.get("chunk_ids", [])} for w in g["data"]["windows"]]
        purana = g["data"]["windows"][0].get("purana") if g["data"]["windows"] else name
        res = audit_coverage(covered, windows)["data"]
        if res["pending"] >= min_gap:
            texts.append({"text": name, "purana": purana,
                          "windows": res["windows"], "done": res["done"],
                          "pending": res["pending"]})
            total_pending += res["pending"]
            pending_by_text[name] = res["pending_chunk_ids"]

    texts.sort(key=lambda t: -t["pending"])
    data = {"total_pending": total_pending,
            "texts_with_gaps": len(texts),
            "texts": texts,
            "pending_chunk_ids": pending_by_text}
    return _envelope(True, data, metadata, errors)


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    min_gap = 1
    if "--min-gap" in argv:
        min_gap = int(argv[argv.index("--min-gap") + 1])
    env = run(min_gap=min_gap)
    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"TOTAL PENDING: {d['total_pending']} chapters across {d['texts_with_gaps']} texts")
        print(f"(covered chunks on disk: {env['metadata']['covered_chunks']})\n")
        for t in d["texts"]:
            print(f"  {t['text']:22s} {t['done']:5d}/{t['windows']:<5d} done  →  {t['pending']} pending")
    if not env["success"]:
        return 2
    return 1 if env["data"]["total_pending"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
