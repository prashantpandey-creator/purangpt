"""One-shot experiment: compare Gemini models on the same chapter windows.

Measures per model: latency, JSON compliance, schema validity, extraction
richness (entity/relationship/teaching counts), and grounding rate via verify.py.

Usage:
  GEMINI_API_KEY=... venv/bin/python -m tools.read_pass.experiment_gemini

NOT a permanent tool — this is a one-off experiment per Rule 0's carve-out.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

from tools.read_pass import comprehend, group, schema
from tools.read_pass.verify import verify_record

MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",       # current default
    "gemini-2.5-pro",
]

WINDOW_SPECS = [
    {"label": "short",  "seq_start": 11333},  # Chapter 2, ~6k chars
    {"label": "medium", "seq_start": 9878},    # Chapter 3, ~8k chars
    {"label": "long",   "seq_start": 19951},   # Chapter 17, ~10k chars
]


def run_one(window: Dict[str, Any], model: str, api_key: str,
            lens: list) -> Dict[str, Any]:
    """Run comprehension on one window with one model. Return stats."""
    t0 = time.time()
    env = comprehend.comprehend_window(window, lens, api_key, model=model)
    elapsed = round(time.time() - t0, 2)

    result: Dict[str, Any] = {
        "model": model,
        "chapter": window.get("chapter_label"),
        "text_chars": len(window.get("text", "")),
        "elapsed_sec": elapsed,
        "success": env["success"],
    }

    if not env["success"]:
        result["error"] = env["errors"][0]["message"][:200] if env["errors"] else "unknown"
        result["entities"] = 0
        result["relationships"] = 0
        result["teachings"] = 0
        result["grounded_rate"] = 0.0
        return result

    rec = env["data"]
    result["entities"] = len(rec.get("entities", []))
    result["relationships"] = len(rec.get("relationships", []))
    result["teachings"] = len(rec.get("teachings", []))
    result["has_story"] = bool(rec.get("story", {}).get("arc"))
    result["schema_problems"] = schema.validate(rec)

    v = verify_record(rec, window["text"])
    vd = v["data"]
    result["total_nodes"] = vd["total_nodes"]
    result["grounded_nodes"] = vd["grounded_nodes"]
    result["grounded_rate"] = vd["grounded_rate"]
    result["flagged_count"] = len(vd["flagged"])

    return result


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GEMINI_API_KEY", file=sys.stderr)
        sys.exit(2)

    print("Loading chapter windows...", file=sys.stderr)
    g = group.run("data/chunks/bhagavata.jsonl")
    if not g["success"]:
        print(f"ERROR: grouper failed: {g['errors']}", file=sys.stderr)
        sys.exit(2)

    by_seq = {w["seq_start"]: w for w in g["data"]["windows"]}
    windows = []
    for spec in WINDOW_SPECS:
        w = by_seq.get(spec["seq_start"])
        if w:
            windows.append((spec["label"], w))
        else:
            print(f"WARN: window seq_start={spec['seq_start']} not found", file=sys.stderr)

    lens = comprehend.load_lens()
    print(f"Lens: {len(lens)} passages loaded", file=sys.stderr)

    results: List[Dict[str, Any]] = []
    for model in MODELS:
        for label, window in windows:
            tag = f"{model} × {label} ({window['chapter_label']})"
            print(f"  Running {tag}...", file=sys.stderr, end=" ", flush=True)
            r = run_one(window, model, api_key, lens)
            r["size_label"] = label
            results.append(r)
            status = "OK" if r["success"] else f"FAIL: {r.get('error','')[:60]}"
            print(f"{r['elapsed_sec']}s — {status}", file=sys.stderr)

    # summary table
    print("\n" + "=" * 100, file=sys.stderr)
    fmt = "{:<22} {:<8} {:>6} {:>5} {:>5} {:>5} {:>8} {:>7}"
    hdr = fmt.format("model", "chapter", "time", "ent", "rel", "teach", "grnd%", "flagged")
    print(hdr, file=sys.stderr)
    print("-" * 100, file=sys.stderr)
    for r in results:
        if r["success"]:
            print(fmt.format(
                r["model"][:22], r["size_label"],
                f"{r['elapsed_sec']}s",
                r["entities"], r["relationships"], r["teachings"],
                f"{r['grounded_rate']:.0%}",
                r["flagged_count"],
            ), file=sys.stderr)
        else:
            print(f"{r['model']:<22} {r['size_label']:<8} FAILED: {r.get('error','')[:50]}", file=sys.stderr)

    # JSON output for programmatic consumption
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
