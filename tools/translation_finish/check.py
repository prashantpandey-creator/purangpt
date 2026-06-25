"""translation_finish — fill the holes in a batch-translated book and assemble it.

The bio (`mossin_awakener_ru.txt`) was re-translated as parallel agent batches
that wrote `{window_index, english}` rows into
`tools/read_pass/translations/agent_batches/*_OUT.json`. Two batches died on the
old `model`-collision bug, leaving 24 windows (10-19, 80-89) un-translated; the
Gita was never batched at all. Re-running the WHOLE file would waste the 96 good
windows.

This tool is the decision-tree that finishes the job (Rule 0):
  gather good windows by index  →  diff against the source's full window set  →
  translate ONLY the missing indices (verified caller, retries on echo/truncation)
  →  splice all windows in strict order  →  assemble .md  →  gate on EN/RU ratio.

`success` is True only when ZERO gaps remain AND the assembled ratio is healthy.
A window that can't be honestly translated is recorded as a remaining gap in
`errors[]`, never written as garbage (the validate guard from translate.py).

Input contract:
  run(src_path, out_dir, out_md, caller=None, api_key=None, model=..., max_chars=...,
      min_ratio=0.4) -> envelope
Output (envelope.data on success):
  { out_md, n_windows_total, missing_indices, n_translated_now, gaps_remaining,
    ratio, src_chars, out_chars }

See tools/sse_contract_check/ for the canonical shape; tests in test_check.py.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

# reuse the verified RU→EN machinery (windowing, per-window validate+retry)
from tools.read_pass import translate


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _gather_good_windows(out_dir: str) -> Dict[int, str]:
    """Read every agent_batches/*_OUT.json → {window_index: english}.

    Skips any row whose english is a recorded gap placeholder. Last writer wins
    if an index appears twice (real data has no dupes; this is just defensive).
    """
    good: Dict[int, str] = {}
    pattern = os.path.join(out_dir, "agent_batches", "*_OUT.json")
    for f in sorted(glob.glob(pattern)):
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for r in doc.get("results", []):
            idx = r.get("window_index")
            en = r.get("english", "")
            if idx is None or not isinstance(en, str):
                continue
            if "[[GAP" in en or "[[TRANSLATION GAP" in en or not en.strip():
                continue
            good[int(idx)] = en
    return good


def run(src_path: str, out_dir: str, out_md: str,
        caller: Optional[Callable[..., str]] = None,
        api_key: str = "",
        model: str = "deepseek-chat",
        max_chars: int = 12000,
        min_ratio: float = 0.4,
        title: str = "") -> Dict[str, Any]:
    metadata = {"src_path": src_path, "out_dir": out_dir, "model": model}

    # 1. window the source (same boundaries the batches used)
    try:
        ru_text = open(src_path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return _envelope(False, None, metadata,
                         [{"code": "read_error", "message": str(e)}])
    if not ru_text.strip():
        return _envelope(False, None, metadata,
                         [{"code": "empty_source", "message": "source has no text"}])

    windows = translate.make_windows(ru_text, max_chars=max_chars)
    n_total = len(windows)

    # 2. gather what we already have, diff to find holes
    good = _gather_good_windows(out_dir)
    good = {i: v for i, v in good.items() if 0 <= i < n_total}  # ignore stray indices
    missing = [i for i in range(n_total) if i not in good]

    # 3. translate ONLY the holes, via the verified path (echo/truncation guard)
    errors: List[Dict[str, str]] = []
    filled: Dict[int, str] = {}
    for i in missing:
        try:
            filled[i] = translate.translate_window_verified(
                windows[i], api_key, model=model, caller=caller)
        except Exception as e:
            errors.append({"code": "window_failed",
                           "message": f"win {i}: {str(e)[:150]}"})

    # 4. splice everything in strict index order
    merged: Dict[int, str] = dict(good)
    merged.update(filled)
    body = translate.assemble(merged, n_total)  # leaves [[TRANSLATION GAP i]] for any still-missing
    gaps_remaining = n_total - len(merged)

    # 5. assemble the .md and write it
    header = (f"# {title}\n\n" if title else "")
    header += ("> Official English translation (RU→EN), assembled by "
               "`tools/translation_finish`.\n"
               f"> Source: `{os.path.basename(src_path)}`. "
               "Faithful full translation, not a summary.\n\n---\n\n")
    try:
        os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
        open(out_md, "w", encoding="utf-8").write(header + body)
    except OSError as e:
        return _envelope(False, None, metadata,
                         [{"code": "write_error", "message": str(e)}])

    # 6. the ratio gate — the gut-check that caught the 0.19 broken original
    ratio = len(body) / max(len(ru_text), 1)
    if ratio < min_ratio:
        errors.append({"code": "ratio_too_low",
                       "message": f"assembled ratio {ratio:.3f} < {min_ratio} "
                                  "— assembly still looks gutted, NOT swapping"})

    data = {
        "out_md": out_md,
        "n_windows_total": n_total,
        "missing_indices": missing,
        "n_translated_now": len(filled),
        "gaps_remaining": gaps_remaining,
        "ratio": round(ratio, 3),
        "src_chars": len(ru_text),
        "out_chars": len(body),
    }
    # success ONLY if no holes left AND ratio healthy
    success = gaps_remaining == 0 and ratio >= min_ratio and not any(
        e["code"] == "window_failed" for e in errors)
    return _envelope(success, data, metadata, errors)


# --- CLI ----------------------------------------------------------------------
def _load_deepseek_key() -> str:
    import pathlib
    k = os.environ.get("DEEPSEEK_API_KEY", "")
    if not k:
        envf = pathlib.Path(".env")
        if envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("DEEPSEEK_API_KEY"):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
    return k


def main(argv: List[str]) -> int:
    as_json = "--json" in argv

    def _arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    src = _arg("--src", "data/raw_texts/sharma_ru/mossin_awakener_ru.txt")
    out_dir = _arg("--out-dir", "tools/read_pass/translations")
    out_md = _arg("--out-md", "tools/read_pass/translations/the_awakener_EN_v2.md")
    title = _arg("--title", "")
    model = _arg("--model", "deepseek-chat")

    key = _load_deepseek_key()
    caller = translate.make_openai_caller(base_url="https://api.deepseek.com/v1") if key else None

    env = run(src_path=src, out_dir=out_dir, out_md=out_md,
              caller=caller, api_key=key, model=model, title=title)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        d = env.get("data") or {}
        if env["success"]:
            print(f"OK: {d['out_md']}")
            print(f"  windows: {d['n_windows_total']} total, "
                  f"{d['n_translated_now']} freshly translated, "
                  f"{d['gaps_remaining']} gaps remaining")
            print(f"  ratio: {d['ratio']} | {d['out_chars']:,} EN / {d['src_chars']:,} RU")
        else:
            print("INCOMPLETE / FAILED:")
            for e in env["errors"]:
                print(f"  - [{e['code']}] {e['message']}")
            if d:
                print(f"  (got {d.get('n_translated_now',0)} new, "
                      f"{d.get('gaps_remaining','?')} gaps remain, "
                      f"ratio {d.get('ratio','?')})")
    return 0 if env["success"] else (1 if env.get("data") else 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
