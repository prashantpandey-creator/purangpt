"""run — the resumable read-pass orchestrator.

Groups a chunk file into chapter windows, comprehends each through the Sharma
lens via DeepSeek (default, 19x cheaper) or Gemini, and appends outputs:
  out/<tag>.records.jsonl  — full per-chapter records (graph+story+teachings)
  out/<tag>.progress.jsonl — one line per attempted window (for resume + audit)

Resumable: a window whose seq_start is already in progress.jsonl is skipped, so
a run can be killed and re-launched. Scope by --start/--limit (canto slice) or
run the whole file. JSON contract on the summary.

Provider is auto-detected from env (DEEPSEEK_API_KEY first, then GEMINI_API_KEY),
or forced via --provider deepseek|gemini.

Usage:
  venv/bin/python -m tools.read_pass.run \
      --input data/chunks/bhagavata.jsonl --tag bhagavata_full --json
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

from tools.read_pass import comprehend, group

OUT_DIR = "tools/read_pass/out"


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _done_seqs(progress_path: str) -> set:
    done = set()
    if os.path.isfile(progress_path):
        with open(progress_path) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["seq_start"])
                except Exception:  # noqa
                    pass
    return done


def run(input_path: str, tag: str, api_key: str,
        start: int = 0, limit: int = 0,
        model: str = "", provider: str = "") -> Dict[str, Any]:
    # auto-detect provider if not explicit
    if not provider or not api_key:
        p, k, m = comprehend.resolve_provider()
        provider = provider or p
        api_key = api_key or k
        model = model or m
    if not model:
        model = comprehend._MODELS.get(provider, comprehend.DEFAULT_MODEL)
    md = {"input": input_path, "tag": tag, "model": model,
          "provider": provider, "start": start, "limit": limit}

    if not api_key:
        return _envelope(False, None, md,
                         [{"code": "no_key", "message": "No LLM key found (set DEEPSEEK_API_KEY or GEMINI_API_KEY)"}])

    g = group.run(input_path)
    if not g["success"]:
        return _envelope(False, None, md, g["errors"])

    windows = g["data"]["windows"]
    # slice by global sequence range (canto-style scoping)
    if start:
        windows = [w for w in windows if w["seq_end"] >= start]
    if limit:
        windows = windows[:limit]

    os.makedirs(OUT_DIR, exist_ok=True)
    records_path = os.path.join(OUT_DIR, f"{tag}.records.jsonl")
    progress_path = os.path.join(OUT_DIR, f"{tag}.progress.jsonl")
    done = _done_seqs(progress_path)

    lens = comprehend.load_lens()
    md["lens_chunks_loaded"] = len(lens)

    n_ok = n_fail = n_skip = 0
    lens_hits = 0
    errors: List[Dict[str, str]] = []

    for w in windows:
        if w["seq_start"] in done:
            n_skip += 1
            continue
        env = comprehend.comprehend_window(w, lens, api_key, model=model, provider=provider)
        prog = {"seq_start": w["seq_start"], "chapter_label": w["chapter_label"],
                "success": env["success"], "lens": env["metadata"].get("lens_applied")}
        if env["success"]:
            n_ok += 1
            if env["metadata"].get("lens_applied"):
                lens_hits += 1
            with open(records_path, "a") as f:
                f.write(json.dumps(env["data"], ensure_ascii=False) + "\n")
        else:
            n_fail += 1
            prog["error"] = env["errors"][0] if env["errors"] else None
            if len(errors) < 10:
                errors.append({"code": env["errors"][0]["code"],
                               "message": f"{w['chapter_label']}: "
                                          f"{env['errors'][0]['message'][:120]}"})
        with open(progress_path, "a") as f:
            f.write(json.dumps(prog, ensure_ascii=False) + "\n")

    data = {"windows_in_scope": len(windows),
            "comprehended": n_ok, "failed": n_fail, "skipped_resume": n_skip,
            "lens_applied_count": lens_hits,
            "records_file": records_path, "progress_file": progress_path}
    # success unless we attempted work and everything failed
    attempted = n_ok + n_fail
    success = not (attempted > 0 and n_ok == 0)
    return _envelope(success, data, md, errors)


def main(argv: List[str]) -> int:
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    input_path = arg("--input", "data/chunks/bhagavata.jsonl")
    tag = arg("--tag", "untagged")
    start = int(arg("--start", "0"))
    limit = int(arg("--limit", "0"))
    provider = arg("--provider", "")
    model = arg("--model", "")
    # auto-detect key from env (deepseek first)
    p, k, m = comprehend.resolve_provider()
    api_key = k

    env = run(input_path, tag, api_key, start=start, limit=limit,
              model=model, provider=provider or p)

    if "--json" in argv:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    elif not env["success"]:
        print(f"ERROR: {env['errors'][0]['message'] if env['errors'] else 'failed'}")
        return 2
    else:
        d = env["data"]
        print(f"OK: {d['comprehended']} comprehended, {d['failed']} failed, "
              f"{d['skipped_resume']} skipped (resume), "
              f"{d['lens_applied_count']} with Sharma lens")
        print(f"    records -> {d['records_file']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
