"""embed_eval — score an embedding model's retrieval quality on the Sanskrit corpus.

The scientific instrument that replaces guessing about model size. Holds the config
fixed (Devanagari-normalized scripture + bi-query) and varies ONE thing: the model.
Returns hit@k, MRR, mean-rank AND a bootstrap 95% CI on hit@5 — so two models are
only "different" when their intervals separate (the discipline whose absence made an
earlier eval call a real 10x gap "noise").

Two layers, by Rule 0:
  - compute_metrics(): PURE, fast, unit-tested in test_check.py (no model needed).
  - run(): the slow IO wrapper — loads a model, embeds the corpus pool, ranks each
    gold query, calls compute_metrics. Run once per model; the ladder driver
    (ladder.py) calls it per rung and assembles the quality-vs-cost curve.

Input contract:  run(model_id, corpus_path, gold_path=GOLD, device=None) -> dict (envelope)
Output (envelope.data): { model, config, dim, n_queries, metrics{hit@1,hit@3,hit@5,
                          hit@10,mrr,mean_rank_found,found,hit@5_ci95}, cost{dim,
                          embed_sec,pool_size,device}, per_query[] }
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_HERE = Path(__file__).parent
GOLD = str(_HERE / "gold.json")

# Commentary categories — NOT scripture; they are the cross-lingual distractors.
COMMENTARY_CATS = {"yogic-discourse", "yogic-commentary", "yoga_commentary"}

_MARK = re.compile(r"[A-Za-z]{1,6}_\d+[,.][\d.,]+")
_DANDA = re.compile(r"[।॥]")
_DEVA = re.compile(r"[ऀ-ॿ]")
_LAT = re.compile(r"[A-Za-z]")


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ── PURE metric core (unit-tested, no model / no IO) ────────────────────────

def compute_metrics(first_ranks: List[Optional[int]], ks=(1, 3, 5, 10),
                    n_boot: int = 2000, seed: int = 12345) -> Dict[str, Any]:
    """first_ranks: per query, the 1-indexed rank of the FIRST correct-text passage,
    or None if it never appears. Returns hit@k, MRR, mean found-rank, and a bootstrap
    95% CI on hit@5. Pure."""
    import random
    n = len(first_ranks)
    if n == 0:
        return {"error": "empty", "n_queries": 0}
    rng = random.Random(seed)

    def hit_at(k, sample):
        return sum(1 for r in sample if r is not None and r <= k) / len(sample)

    out: Dict[str, Any] = {}
    for k in ks:
        out[f"hit@{k}"] = round(hit_at(k, first_ranks), 4)
    found = [r for r in first_ranks if r is not None]
    out["mrr"] = round(sum(1.0 / r for r in found) / n, 4) if found else 0.0
    out["mean_rank_found"] = round(sum(found) / len(found), 2) if found else None
    out["found"] = len(found)
    out["n_queries"] = n
    boots = []
    for _ in range(n_boot):
        sample = [first_ranks[rng.randrange(n)] for _ in range(n)]
        boots.append(hit_at(5, sample))
    boots.sort()
    out["hit@5_ci95"] = [round(boots[int(0.025 * n_boot)], 4),
                         round(boots[int(0.975 * n_boot)], 4)]
    return out


# ── helpers ─────────────────────────────────────────────────────────────────

def _clean(t: str) -> str:
    t = _MARK.sub(" ", t); t = _DANDA.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()[:512]


def _is_latin(t: str) -> bool:
    return len(_LAT.findall(t)) > len(_DEVA.findall(t))


def _to_deva(t: str) -> str:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
    try:
        return transliterate(t, sanscript.IAST, sanscript.DEVANAGARI)
    except Exception:
        return t


def _prefixes(model_id: str):
    """Per-model query/passage prefix conventions. Wrong prefix silently corrupts the
    comparison — the most common embedding-eval bug, so it is encoded here once."""
    m = model_id.lower()
    if "/e5" in m or "multilingual-e5" in m:        # intfloat multilingual-e5-* (not mistral)
        if "mistral" not in m:
            return ("query: ", "passage: ")
    return ("", "")                                  # bge-m3 / gte / qwen-st / most: none


# ── slow IO wrapper ─────────────────────────────────────────────────────────

def run(model_id: str, corpus_path: str, gold_path: str = GOLD,
        device: Optional[str] = None, max_passages: int = 0) -> Dict[str, Any]:
    """Embed the corpus pool with `model_id` (Devanagari scripture + bi-query), rank
    each gold query, return the metrics envelope. Slow (loads a model)."""
    meta = {"model": model_id, "corpus_path": corpus_path, "gold_path": gold_path,
            "config": "deva_corpus+bi_query"}
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        return _envelope(False, None, meta, [{"code": "import", "message": str(e)}])

    if not os.path.exists(corpus_path):
        return _envelope(False, None, meta, [{"code": "no_corpus", "message": corpus_path}])
    gold = json.load(open(gold_path, encoding="utf-8"))["queries"]
    rows = json.load(open(corpus_path, encoding="utf-8"))
    if max_passages:
        rows = rows[:max_passages]

    pool = []
    for r in rows:
        c = _clean(r.get("content", ""))
        if len(c) < 20:
            continue
        is_scrip = (r.get("category") or "") not in COMMENTARY_CATS
        embed_text = _to_deva(c) if (is_scrip and _is_latin(c)) else c   # normalize scripture
        pool.append({"purana": r.get("purana", ""), "text": embed_text})
    if not pool:
        return _envelope(False, None, meta, [{"code": "empty_pool", "message": "no usable passages"}])

    if device is None:
        try:
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        except Exception:
            device = "cpu"

    qpref, ppref = _prefixes(model_id)
    try:
        model = SentenceTransformer(model_id, device=device, trust_remote_code=True)
    except Exception as e:
        return _envelope(False, None, meta, [{"code": "load", "message": str(e)}])

    t0 = time.time()
    P = model.encode([ppref + p["text"] for p in pool], normalize_embeddings=True,
                     batch_size=64, show_progress_bar=False)
    embed_sec = round(time.time() - t0, 1)
    dim = int(P.shape[1])

    def qvec(text):
        return model.encode([qpref + text], normalize_embeddings=True, show_progress_bar=False)[0]

    first_ranks: List[Optional[int]] = []
    per_query = []
    for g in gold:
        sims = np.maximum(P @ qvec(g["q"]), P @ qvec(g["sa"]))   # bi-query: best-sim per passage
        order = np.argsort(-sims)
        tgt = g["target"].lower()
        fr = None
        for rank, i in enumerate(order):
            if tgt in pool[i]["purana"].lower():
                fr = rank + 1
                break
        first_ranks.append(fr)
        per_query.append({"q": g["q"][:48], "target": g["target"], "rank": fr})

    metrics = compute_metrics(first_ranks)
    data = {"model": model_id, "config": meta["config"], "dim": dim,
            "n_queries": len(gold), "metrics": metrics,
            "cost": {"dim": dim, "embed_sec": embed_sec, "pool_size": len(pool), "device": device},
            "per_query": per_query}
    return _envelope(True, data, meta, [])


def main():
    ap = argparse.ArgumentParser(description="Eval an embedding model on the Sanskrit corpus")
    ap.add_argument("model_id")
    ap.add_argument("--corpus", required=True, help="corpus sample json [{purana,category,content}]")
    ap.add_argument("--gold", default=GOLD)
    ap.add_argument("--device", default=None)
    ap.add_argument("--max-passages", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    env = run(a.model_id, a.corpus, a.gold, a.device, a.max_passages)
    if a.json:
        print(json.dumps(env, ensure_ascii=False))
    else:
        if env["success"]:
            d = env["data"]; m = d["metrics"]
            print(f"{d['model']}  dim={d['dim']}  ({d['cost']['embed_sec']}s, {d['cost']['device']})")
            print(f"  hit@1={m['hit@1']} hit@5={m['hit@5']} hit@10={m['hit@10']} "
                  f"MRR={m['mrr']} meanRank={m['mean_rank_found']} found={m['found']}/{m['n_queries']}")
            print(f"  hit@5 95% CI = {m['hit@5_ci95']}")
        else:
            print("FAILED:", env["errors"])
    sys.exit(0 if env["success"] else 1)


if __name__ == "__main__":
    main()
