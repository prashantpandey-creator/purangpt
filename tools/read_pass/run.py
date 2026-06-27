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

from tools.read_pass import comprehend, group, verify

OUT_DIR = "tools/read_pass/out"


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _count_nodes(record: Dict[str, Any]) -> int:
    return sum(len(record.get(fld, []) or []) for fld in verify._NODE_FIELDS)


def gate_record(record: Dict[str, Any], window_text: str) -> Dict[str, Any]:
    """The verify GATE on the write path (the scar cure — memory
    verify-was-bhagavata-only / graph-audit-16-fabricated).

    The decoder narrates: it emits fluent nodes whose cites name real-looking
    markers that are NOT actually in the source window. `comprehend_window`
    returning success only means the JSON parsed — it does not mean the facts are
    grounded. So before a record is persisted we PRUNE every node whose cite does
    not literally appear in `window_text` (verify.prune → verify.check_node →
    _MARKER_RE). Only verse-defensible facts reach the graph.

    Returns the standard envelope; data = {record, kept_nodes, dropped_nodes,
    worth_writing}. `worth_writing` is False when prune emptied the record of all
    node-bearing facts — the caller should skip writing an all-empty husk (it
    would add nothing to the graph and only inflate counts).
    """
    before = _count_nodes(record or {})
    pruned = verify.prune(record or {}, window_text or "")
    kept = _count_nodes(pruned)
    dropped = before - kept
    return _envelope(
        True,
        {"record": pruned, "kept_nodes": kept, "dropped_nodes": dropped,
         "worth_writing": kept > 0},
        {"nodes_before": before},
        [],
    )


def _done_seqs(progress_path: str) -> set:
    done = set()
    if os.path.isfile(progress_path):
        with open(progress_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("success", False):
                        done.add(entry["seq_start"])
                except Exception:  # noqa
                    pass
    return done


def run(input_path: str, tag: str, api_key: str,
        start: int = 0, limit: int = 0,
        model: str = "", provider: str = "",
        window_chunks: int = group.MAX_WINDOW_CHUNKS) -> Dict[str, Any]:
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

    # inhouse decode needs NO key — the populated cache IS the LLM (the Workflow
    # already comprehended each chapter and wrote its JSON). Only the live API
    # providers require a key. (Without this guard the fold pass for a fully
    # decoded inhouse cache bailed 'no_key' and could never reach the graph —
    # found by the BORI smoke 2026-06-26, pinned by test_fold_pass_*.)
    if provider != "inhouse" and not api_key:
        return _envelope(False, None, md,
                         [{"code": "no_key", "message": "No LLM key found (set DEEPSEEK_API_KEY or GEMINI_API_KEY)"}])

    md["window_chunks"] = window_chunks
    g = group.run(input_path, max_chunks=window_chunks)
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

    n_ok = n_fail = n_skip = n_husk = 0
    lens_hits = 0
    nodes_kept = nodes_dropped = 0
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
            # THE VERIFY GATE (memory verify-was-bhagavata-only): the decoder
            # narrates — drop every node whose cite isn't literally in the source
            # window BEFORE it can fold into the graph. Only verse-grounded facts
            # are persisted. A record pruned to nothing (all cites hallucinated)
            # is NOT written (no empty husk), but is still marked done for resume
            # (we attempted it; re-decoding would only re-hallucinate).
            gate = gate_record(env["data"], w["text"])["data"]
            nodes_kept += gate["kept_nodes"]
            nodes_dropped += gate["dropped_nodes"]
            prog["kept"] = gate["kept_nodes"]
            prog["dropped"] = gate["dropped_nodes"]
            if gate["worth_writing"]:
                with open(records_path, "a") as f:
                    f.write(json.dumps(gate["record"], ensure_ascii=False) + "\n")
            else:
                n_husk += 1
                prog["husked"] = True
        else:
            n_fail += 1
            prog["error"] = env["errors"][0] if env["errors"] else None
            if len(errors) < 10:
                errors.append({"code": env["errors"][0]["code"],
                               "message": f"{w['chapter_label']}: "
                                          f"{env['errors'][0]['message'][:120]}"})
        with open(progress_path, "a") as f:
            f.write(json.dumps(prog, ensure_ascii=False) + "\n")

    total_nodes = nodes_kept + nodes_dropped
    grounded_rate = round(nodes_kept / total_nodes, 3) if total_nodes else 0.0
    data = {"windows_in_scope": len(windows),
            "comprehended": n_ok, "failed": n_fail, "skipped_resume": n_skip,
            "husked": n_husk,  # comprehended but pruned to zero grounded facts
            "nodes_kept": nodes_kept, "nodes_dropped": nodes_dropped,
            "grounded_rate": grounded_rate,
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
    window_chunks = int(arg("--window-chunks", str(group.MAX_WINDOW_CHUNKS)))
    # auto-detect key from env (deepseek first)
    p, k, m = comprehend.resolve_provider()
    api_key = k

    env = run(input_path, tag, api_key, start=start, limit=limit,
              model=model, provider=provider or p, window_chunks=window_chunks)

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
