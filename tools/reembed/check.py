"""reembed — offline pipeline: normalize IAST corpus + re-embed with bge-m3.

Four sequential steps. Run each in order; each step reads the previous step's output.

  # Step 0: open SSH tunnel (keep running in background)
  ssh -i ~/.ssh/purangpt_hetzner -L 5433:localhost:5433 root@204.168.176.229 -N &

  # Step 1: export full corpus (~291K rows, ~5 min)
  venv/bin/python -m tools.reembed.check --step export --out rows.jsonl --json

  # Step 2: normalize IAST→Devanagari (~2 min)
  venv/bin/python -m tools.reembed.check --step normalize --input rows.jsonl --out norm_rows.jsonl --json

  # Step 3: embed with bge-m3 on Mac MPS (~75 min, resumable)
  venv/bin/python -m tools.reembed.check --step embed --input norm_rows.jsonl --out embed_out/ --json

  # Step 4: push vectors to prod DB + build HNSW index (~20 min)
  venv/bin/python -m tools.reembed.check --step import --input embed_out/ --json

Output envelope: {success, data, metadata, errors}
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import traceback
from typing import Any

DB_URL = "postgresql://postgres:postgres@localhost:5433/purangpt"


def _envelope(success: bool, data: Any, metadata: dict, errors: list) -> dict:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _step_export(out_path: str) -> dict:
    import psycopg2
    import psycopg2.extras
    t0 = time.time()
    n = 0
    CHUNK = 10000
    with open(out_path, "w", encoding="utf-8") as f:
        offset = 0
        while True:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id, content, metadata FROM purana_verses "
                "WHERE content IS NOT NULL ORDER BY id "
                "LIMIT %s OFFSET %s",
                (CHUNK, offset),
            )
            rows = cur.fetchall()
            conn.close()
            if not rows:
                break
            for row in rows:
                meta = row["metadata"]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                if not isinstance(meta, dict):
                    meta = {}
                f.write(json.dumps({
                    "id": row["id"],
                    "content": row["content"],
                    "category": meta.get("category") or "",
                    "purana": meta.get("purana") or "",
                }, ensure_ascii=False) + "\n")
            n += len(rows)
            offset += CHUNK
            print(f"  exported {n}…", flush=True)
    return {"n": n, "out": out_path, "sec": round(time.time() - t0, 1)}


def _step_normalize(in_path: str, out_path: str) -> dict:
    from tools.reembed.normalize import normalize_row
    stats: dict[str, int] = {}
    n = 0
    t0 = time.time()
    with open(in_path, encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            result = normalize_row(row["content"], row.get("category", ""), row["id"])
            stats[result["script"]] = stats.get(result["script"], 0) + 1
            fout.write(json.dumps({
                "id": row["id"],
                "embed_text": result["embed_text"],
                "script": result["script"],
            }, ensure_ascii=False) + "\n")
            n += 1
            if n % 50000 == 0:
                print(f"  normalized {n}…  {stats}", flush=True)
    return {"n": n, "stats": stats, "out": out_path, "sec": round(time.time() - t0, 1)}


def _step_embed(in_path: str, out_dir: str) -> dict:
    from tools.reembed.embed import run as embed_run
    return embed_run(in_path, out_dir)


def _step_import(in_dir: str, dry_run: bool = False) -> dict:
    from tools.reembed.import_vectors import run as import_run
    return import_run(in_dir, DB_URL, dry_run)


def main():
    ap = argparse.ArgumentParser(
        description="reembed: 4-step offline pipeline for bge-m3 corpus normalization + re-embedding"
    )
    ap.add_argument("--step", choices=["export", "normalize", "embed", "import"],
                    required=True)
    ap.add_argument("--input", default=None, help="Input file/dir for this step")
    ap.add_argument("--out", default=None, help="Output file/dir for this step")
    ap.add_argument("--dry-run", action="store_true",
                    help="(import step) validate only, no DB writes")
    ap.add_argument("--json", action="store_true", help="Emit JSON envelope to stdout")
    a = ap.parse_args()

    meta = {"step": a.step, "input": a.input, "out": a.out}
    try:
        if a.step == "export":
            out = a.out or "rows.jsonl"
            data = _step_export(out)
        elif a.step == "normalize":
            if not a.input:
                ap.error("--input rows.jsonl required for normalize step")
            out = a.out or "norm_rows.jsonl"
            data = _step_normalize(a.input, out)
        elif a.step == "embed":
            if not a.input:
                ap.error("--input norm_rows.jsonl required for embed step")
            out = a.out or "embed_out"
            data = _step_embed(a.input, out)
        elif a.step == "import":
            if not a.input:
                ap.error("--input embed_out/ required for import step")
            data = _step_import(a.input, a.dry_run)
        env = _envelope(True, data, meta, [])
    except Exception as e:
        env = _envelope(False, None, meta,
                        [{"code": "error", "message": str(e),
                          "trace": traceback.format_exc()}])

    if a.json:
        print(json.dumps(env, ensure_ascii=False, indent=2, default=str))
    else:
        if env["success"]:
            print(json.dumps(env["data"], ensure_ascii=False, indent=2, default=str))
        else:
            print("FAILED:", file=sys.stderr)
            for err in env["errors"]:
                print(f"  {err.get('code')}: {err.get('message')}", file=sys.stderr)
                if err.get("trace"):
                    print(err["trace"], file=sys.stderr)
    sys.exit(0 if env["success"] else 1)


if __name__ == "__main__":
    main()
