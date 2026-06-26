"""chunk_marker_audit — which chunk files are decodable, which are ungroundable junk.

THE PROBLEM (found via the verify-gate, commit eed9bfa): the gate prunes any decoded
node whose cite isn't literally in its source window. So a decode is only as good as
the chunk file's verse markers. We found decode_audit counts mahabharata.jsonl —
HTML-entity junk with ZERO markers, which the gate would husk 100% — while the clean
BORI critical edition (mahabharata_bori_chunks.jsonl, mbh_PP.CCC.VVV markers in all
1995 chapters) sits right beside it. And it's systemic: garuda/skanda/kurma chunk
files also carry 0 markers.

So BEFORE spending a token on decode, scan chunk files and classify each:
  - decodable          : markers present → the gate will keep real facts
  - needs_normalization: 0 markers → the gate would husk it → fix the chunker first
  - empty / missing     : the file edge cases

Pure Rule-0 decision tree: read file → group into windows → sample the first N →
count markers with verify._MARKER_RE (THE SAME grammar the gate uses, so the audit
can never bless a file the gate then rejects) → branch. Zero LLM, zero network.

  venv/bin/python -m tools.chunk_marker_audit.check --scan-all --json
  venv/bin/python -m tools.chunk_marker_audit.check --input data/chunks/skanda.jsonl --json

See README.md for the descriptor, failure table, and example.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, Dict, List

from tools.read_pass import group, verify

CHUNK_DIR = "data/chunks"


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _audit_one(path: str, sample_windows: int) -> Dict[str, Any]:
    """Classify a single chunk file by sampling its first `sample_windows` windows
    and counting verse markers. Returns one row of the report."""
    if not os.path.isfile(path):
        return {"file": path, "status": "missing", "windows_total": 0,
                "windows_sampled": 0, "markers_found": 0, "sample_markers": []}

    try:
        g = group.run(path)
    except Exception as e:  # noqa — a malformed file must not blind the whole audit
        return {"file": path, "status": "group_failed", "windows_total": 0,
                "windows_sampled": 0, "markers_found": 0, "sample_markers": [],
                "error": f"{type(e).__name__}: {e}"}
    if not g["success"]:
        return {"file": path, "status": "group_failed", "windows_total": 0,
                "windows_sampled": 0, "markers_found": 0, "sample_markers": [],
                "error": (g["errors"][0]["message"] if g["errors"] else "group failed")}

    windows = g["data"]["windows"]
    if not windows:
        return {"file": path, "status": "empty", "windows_total": 0,
                "windows_sampled": 0, "markers_found": 0, "sample_markers": []}

    sampled = windows[:sample_windows]
    markers: List[str] = []
    for w in sampled:
        markers.extend(verify.extract_markers(w.get("text", "")))
    uniq = sorted(set(markers))

    # decision: any real marker in the sample → decodable; none → needs normalization.
    status = "decodable" if uniq else "needs_normalization"
    return {"file": path, "status": status,
            "windows_total": len(windows), "windows_sampled": len(sampled),
            "markers_found": len(uniq), "sample_markers": uniq[:5]}


def run(files: List[str], sample_windows: int = 3) -> Dict[str, Any]:
    """Audit each chunk file's verse-marker coverage and bucket the results.

    Returns the standard envelope; data = {files: [<row>...], decodable: [...],
    needs_normalization: [...], n_files, n_decodable, n_needs_normalization,
    n_missing, n_empty}. Empty file list → success:false (a misuse). A missing or
    unparseable file is NOT a failure of the whole run — it's a row with that status
    (so one bad path doesn't blind the whole audit).
    """
    md = {"sample_windows": sample_windows, "n_files": len(files),
          "chunk_dir": CHUNK_DIR}

    if not files:
        return _envelope(False, None, md,
                         [{"code": "no_files", "message": "no chunk files given"}])

    rows = [_audit_one(p, sample_windows) for p in files]

    decodable = [r["file"] for r in rows if r["status"] == "decodable"]
    needs = [r["file"] for r in rows if r["status"] == "needs_normalization"]
    missing = [r["file"] for r in rows if r["status"] == "missing"]
    empty = [r["file"] for r in rows if r["status"] in ("empty", "group_failed")]

    data = {"files": rows,
            "decodable": decodable, "needs_normalization": needs,
            "n_files": len(rows),
            "n_decodable": len(decodable),
            "n_needs_normalization": len(needs),
            "n_missing": len(missing),
            "n_empty": len(empty)}
    return _envelope(True, data, md, [])


# ── CLI (--json contract) ─────────────────────────────────────────────────────
def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    sample_windows = 3
    if "--sample" in argv:
        sample_windows = int(argv[argv.index("--sample") + 1])

    if "--scan-all" in argv:
        files = sorted(glob.glob(os.path.join(CHUNK_DIR, "*.jsonl")))
    elif "--input" in argv:
        files = [argv[argv.index("--input") + 1]]
    else:
        files = []

    env = run(files, sample_windows=sample_windows)

    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR [{env['errors'][0]['code']}]: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"audited {d['n_files']} files — "
              f"{d['n_decodable']} decodable, "
              f"{d['n_needs_normalization']} need normalization, "
              f"{d['n_missing']} missing, {d['n_empty']} empty\n")
        for r in sorted(d["files"], key=lambda x: (x["status"], x["file"])):
            mark = {"decodable": "✓", "needs_normalization": "✗",
                    "missing": "?", "empty": "·", "group_failed": "!"}.get(r["status"], " ")
            name = os.path.basename(r["file"])
            print(f"  {mark} {name:<34} {r['status']:<20} "
                  f"{r['markers_found']:>4} markers / {r['windows_total']:>4} ch")

    if not env["success"]:
        return 2
    # exit 1 = a finding: at least one file needs normalization
    return 1 if env["data"]["n_needs_normalization"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
