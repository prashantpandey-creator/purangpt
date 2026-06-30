"""ladder — run a list of embedding models through embed_eval.check and assemble the
quality-vs-cost curve. The scientific decision instrument: pick the smallest model on
the Pareto frontier that clears the product bar. NOT the tested core (that's check.py);
this is the driver that produces the curve.

Usage: venv/bin/python -m tools.embed_eval.ladder <corpus.json> [model_id ...]
"""
import json
import sys
from tools.embed_eval.check import run

DEFAULT_MODELS = [
    "intfloat/multilingual-e5-small",                  # 384  — current
    "intfloat/multilingual-e5-base",                   # 768  — capacity rung
    "intfloat/multilingual-e5-large",                  # 1024 — capacity rung
    "BAAI/bge-m3",                                      # 1024 — same class, diff training
    "l3cube-pune/indic-sentence-similarity-sbert",     # 768  — Indic-COVERAGE rung (MuRIL)
]

PARAMS_HINT = {  # rough param counts for the cost axis
    "intfloat/multilingual-e5-small": "118M",
    "intfloat/multilingual-e5-base": "278M",
    "intfloat/multilingual-e5-large": "560M",
    "BAAI/bge-m3": "568M",
    "l3cube-pune/indic-sentence-similarity-sbert": "238M",
}


def main():
    if len(sys.argv) < 2:
        print("usage: ladder.py <corpus.json> [model ...]"); sys.exit(2)
    corpus = sys.argv[1]
    models = sys.argv[2:] or DEFAULT_MODELS
    rows = []
    for mid in models:
        print(f"\n### {mid}", flush=True)
        env = run(mid, corpus)
        if not env["success"]:
            print("  FAILED:", env["errors"], flush=True)
            rows.append({"model": mid, "failed": env["errors"]})
            continue
        d = env["data"]; m = d["metrics"]
        d["params_hint"] = PARAMS_HINT.get(mid, "?")
        rows.append(d)
        print(f"  dim={d['dim']} hit@5={m['hit@5']} CI={m['hit@5_ci95']} "
              f"hit@10={m['hit@10']} MRR={m['mrr']} meanRank={m['mean_rank_found']} "
              f"({d['cost']['embed_sec']}s)", flush=True)

    ok = [r for r in rows if "metrics" in r]
    ok.sort(key=lambda r: r["metrics"]["hit@5"], reverse=True)
    print("\n================ QUALITY vs COST LADDER ================", flush=True)
    hdr = f"{'model':<46}{'params':>7}{'dim':>6}{'hit@5':>8}{'hit@5 CI':>16}{'hit@10':>8}{'MRR':>7}{'mRank':>8}{'embed_s':>9}"
    print(hdr); print("-" * len(hdr))
    for r in ok:
        m = r["metrics"]; c = r["cost"]
        ci = f"[{m['hit@5_ci95'][0]:.2f},{m['hit@5_ci95'][1]:.2f}]"
        print(f"{r['model']:<46}{r.get('params_hint','?'):>7}{r['dim']:>6}"
              f"{m['hit@5']:>8.3f}{ci:>16}{m['hit@10']:>8.3f}{m['mrr']:>7.3f}"
              f"{str(m['mean_rank_found']):>8}{c['embed_sec']:>9}")
    for r in rows:
        if "failed" in r:
            print(f"{r['model']:<46}  FAILED: {r['failed']}")
    out = "/private/tmp/claude-501/-Users-badenath-projects-vedic-puran/6ced072f-5673-4183-81ee-b40a7eee0256/scratchpad/ladder_results.json"
    json.dump(rows, open(out, "w"), ensure_ascii=False, indent=2, default=str)
    print(f"\nwrote {out}\nDONE", flush=True)


if __name__ == "__main__":
    main()
