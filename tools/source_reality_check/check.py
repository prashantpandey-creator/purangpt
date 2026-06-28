"""source_reality_check — is a corpus file REAL Sanskrit, or web/HTML garbage?

THE PROBLEM (yoga_vasistha incident, 2026-06-28): the raw source under
data/raw_texts/gretil/yoga_vasistha/ was a saved archive.org *details webpage* —
233KB of HTML/JS/sentry boilerplate with ZERO Devanagari and ZERO IAST. The
derived chunks (data/chunks/yoga_vasistha.jsonl) were slices of that same HTML.
A decode against it produced 419 hallucinated records (quarantined). The lesson:
BEFORE re-chunking or decoding, prove the bytes are actually scripture.

This answers a DIFFERENT axis than `chunk_marker_audit`:
  - chunk_marker_audit → "is this DECODE-ready?" (gate's `verify._MARKER_RE`,
    head-sampled). A freshly re-chunked file whose early markers are short
    (e.g. `MU_1,1.1`, dropped by the chunker's <10-char rule) can read 0 markers
    in the first 3 windows and be misjudged — the FINDINGS.md scope trap.
  - source_reality_check → "is this REAL Sanskrit, not HTML?" Scans the WHOLE
    file (never head-only, so the scope trap can't bite), counts IAST diacritics,
    Devanagari, verse markers (prefixed `MU_1,26.13` OR bare `1.1.1`), and HTML
    boilerplate → classifies real_sanskrit / html_garbage / suspect / empty.

Pure Rule-0 decision tree: read file → count signals over everything → branch.
Zero LLM, zero network.

  venv/bin/python -m tools.source_reality_check.check data/chunks/yoga_vasistha.jsonl --json
  venv/bin/python -m tools.source_reality_check.check --input data/raw_texts/gretil/yoga_vasistha/sa_mokSopAya.txt --json

See README.md for the descriptor, failure table, and example.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from typing import Any, Dict, List

CHUNK_DIR = "data/chunks"

# IAST diacritics that mark transliterated Sanskrit (and never appear in plain
# English web boilerplate). Lower + upper.
_IAST_RE = re.compile(
    "[" "āīūṛṝḷḹṅñṭḍṇśṣṁṃḥēōĀĪŪṚṜḶḸṄÑṬḌṆŚṢṀṂḤĒŌ" "]"
)

# Devanagari block.
_DEVA_RE = re.compile(r"[ऀ-ॿ]")

# Verse markers, two faithful forms:
#   prefixed  — MU_1,26.13 · bhp_01.01.001 · katha_1.1.1  (the GRETIL citation style)
#   bare a.b.c — 1.1.1 · 1,26.13  (line-leading numeric reference, ≥3 components)
_MARKER_RE = re.compile(
    r"\b[A-Za-z]{1,6}_\d+[.,]\d+(?:[.,]\d+)*"   # prefixed
    r"|\b\d{1,3}[.,]\d{1,3}[.,]\d{1,3}\b"        # bare a.b.c
)

# Web/HTML/JS boilerplate that is conclusive of a saved web page, never of a
# clean Sanskrit e-text — true tag / script / attribute shapes only.
# Deliberately NOT here: HTML entities (`&amp;`, `&quot;`, `&nbsp;`, `&#1234;`)
# and bare `&`/`<`. The GRETIL corpus is entity-encoded (e.g. bhagavata carries
# 390 real `&amp;`), so entities are NOISE in legitimate text, not garbage — using
# them as a signal mismeasured a known-real file as `suspect` (incident 2026-06-28).
_HTML_RE = re.compile(
    r"<!doctype|<!--|<html|<head|<body|<div|<span|<script|<style|<meta|<link"
    r"|</[a-z]|function\s*\(|window\.|document\.|sentry"
    r"|archive\.org|data-(?:release|node|ia)|class=|href=|<svg",
    re.IGNORECASE,
)

_MAX_SCAN_BYTES = 20_000_000  # safety cap; real corpus files are ≤ a few MB


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _read_text(path: str) -> str:
    """Return the scannable text of a file. For .jsonl chunk files, concatenate
    every chunk's `text` field; for anything else, the raw bytes as UTF-8.
    Scans the WHOLE file (never a head sample) — this is what defeats the
    early-marker-dropped scope trap."""
    if path.endswith(".jsonl"):
        parts: List[str] = []
        size = 0
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    parts.append(line)  # malformed line: scan it raw, don't hide it
                    continue
                t = obj.get("text", "") if isinstance(obj, dict) else str(obj)
                parts.append(t)
                size += len(t)
                if size > _MAX_SCAN_BYTES:
                    break
        return "\n".join(parts)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(_MAX_SCAN_BYTES)


def _classify(html: int, iast: int, deva: int, markers: int, chars: int) -> str:
    """Branch on the signal counts. Order matters: HTML contamination is checked
    before reality so a page with a few stray IAST-looking chars can't pass."""
    if chars == 0:
        return "empty"
    script = iast + deva
    # Conclusive web boilerplate with negligible scripture → garbage.
    if html >= 3 and script < 20:
        return "html_garbage"
    if html >= 1 and script == 0:
        return "html_garbage"
    # Real scripture: plenty of IAST/Devanagari, at least one verse marker, and
    # no more than a trivial number of stray tag artifacts (≤2 tolerates OCR/edit
    # noise; a genuine page has thousands).
    if script >= 50 and markers >= 1 and html <= 2:
        return "real_sanskrit"
    # Anything else — real-looking script but no markers, or mixed signals — is
    # a finding a human must look at, never silently blessed.
    return "suspect"


def _audit_one(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return {"file": path, "status": "missing", "chars": 0,
                "iast": 0, "devanagari": 0, "markers": 0, "html_hits": 0,
                "sample_markers": []}
    try:
        text = _read_text(path)
    except Exception as e:  # noqa — one unreadable file must not blind the run
        return {"file": path, "status": "read_failed", "chars": 0,
                "iast": 0, "devanagari": 0, "markers": 0, "html_hits": 0,
                "sample_markers": [], "error": f"{type(e).__name__}: {e}"}

    iast = len(_IAST_RE.findall(text))
    deva = len(_DEVA_RE.findall(text))
    marker_hits = _MARKER_RE.findall(text)
    html = len(_HTML_RE.findall(text))
    chars = len(text)

    status = _classify(html, iast, deva, len(marker_hits), chars)
    return {"file": path, "status": status, "chars": chars,
            "iast": iast, "devanagari": deva, "markers": len(marker_hits),
            "html_hits": html, "sample_markers": sorted(set(marker_hits))[:5]}


def run(files: List[str]) -> Dict[str, Any]:
    """Classify each file as real_sanskrit / html_garbage / suspect / empty /
    missing / read_failed. Returns the standard envelope; data carries per-file
    rows plus bucket lists and counts. Empty file list → success:false (misuse).
    A missing/unreadable file is a ROW with that status, never a whole-run
    failure (one bad path can't blind the scan)."""
    md = {"n_files": len(files)}
    if not files:
        return _envelope(False, None, md,
                         [{"code": "no_files", "message": "no files given"}])

    rows = [_audit_one(p) for p in files]
    real = [r["file"] for r in rows if r["status"] == "real_sanskrit"]
    garbage = [r["file"] for r in rows if r["status"] == "html_garbage"]
    suspect = [r["file"] for r in rows if r["status"] == "suspect"]
    other = [r["file"] for r in rows
             if r["status"] in ("empty", "missing", "read_failed")]

    data = {"files": rows,
            "real_sanskrit": real, "html_garbage": garbage,
            "suspect": suspect, "other": other,
            "n_files": len(rows), "n_real": len(real),
            "n_garbage": len(garbage), "n_suspect": len(suspect),
            "n_other": len(other)}
    return _envelope(True, data, md, [])


# ── CLI (--json contract) ─────────────────────────────────────────────────────
def _collect_paths(argv: List[str]) -> List[str]:
    paths: List[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--input":
            if i + 1 < len(argv):
                paths.append(argv[i + 1])
                i += 2
                continue
        elif not a.startswith("--"):
            paths.append(a)
        i += 1
    return paths


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    if "--scan-all" in argv:
        # every per-text chunk file; skip the master concat + backups (mixed content)
        files = sorted(p for p in glob.glob(os.path.join(CHUNK_DIR, "*.jsonl"))
                       if "all_chunks" not in os.path.basename(p))
    else:
        files = _collect_paths(argv)
    env = run(files)

    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR [{env['errors'][0]['code']}]: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"checked {d['n_files']} file(s) — {d['n_real']} real, "
              f"{d['n_garbage']} garbage, {d['n_suspect']} suspect, "
              f"{d['n_other']} other\n")
        for r in d["files"]:
            mark = {"real_sanskrit": "✓", "html_garbage": "✗",
                    "suspect": "?", "empty": "·", "missing": "·",
                    "read_failed": "!"}.get(r["status"], " ")
            print(f"  {mark} {os.path.basename(r['file']):<30} {r['status']:<14} "
                  f"iast={r['iast']:>7} deva={r['devanagari']:>6} "
                  f"mk={r['markers']:>6} html={r['html_hits']:>4}")

    if not env["success"]:
        return 2
    # exit 1 = a finding: any file is not real_sanskrit
    return 1 if (env["data"]["n_garbage"] or env["data"]["n_suspect"]
                 or env["data"]["n_other"]) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
