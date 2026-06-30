"""Tests for embed_eval — the PURE metric core (no model, no IO), per Rule 0.

Run: venv/bin/python -m tools.embed_eval.test_check   (from purangpt/ repo root)

The slow run() wrapper (model load + embed) is exercised by the ladder driver on
real models; here we lock down compute_metrics — the deterministic core whose
ABSENCE of confidence intervals once let a real 10x gap be dismissed as "noise".
"""
from tools.embed_eval.check import compute_metrics, _prefixes, _is_latin, _clean


def _approx(a, b, eps=1e-9):
    return abs(a - b) < eps


def test_all_rank_one():
    m = compute_metrics([1, 1, 1, 1])
    assert m["hit@1"] == 1.0 and m["hit@5"] == 1.0 and m["hit@10"] == 1.0
    assert m["mrr"] == 1.0
    assert m["mean_rank_found"] == 1.0
    assert m["found"] == 4 and m["n_queries"] == 4


def test_known_mixed_ranks():
    # ranks: 1, 2, 6, miss
    m = compute_metrics([1, 2, 6, None])
    assert m["hit@1"] == 0.25          # only the rank-1
    assert m["hit@3"] == 0.5           # ranks 1,2
    assert m["hit@5"] == 0.5           # ranks 1,2 (6 is out)
    assert m["hit@10"] == 0.75         # ranks 1,2,6
    assert m["mrr"] == round((1 + 0.5 + 1 / 6 + 0) / 4, 4)
    assert m["mean_rank_found"] == 3.0  # (1+2+6)/3
    assert m["found"] == 3 and m["n_queries"] == 4


def test_all_miss():
    m = compute_metrics([None, None, None])
    assert m["hit@1"] == 0.0 and m["hit@5"] == 0.0
    assert m["mrr"] == 0.0
    assert m["mean_rank_found"] is None
    assert m["found"] == 0


def test_empty():
    m = compute_metrics([])
    assert m.get("error") == "empty" and m["n_queries"] == 0


def test_bootstrap_ci_shape_and_bounds():
    m = compute_metrics([1, 2, 6, None, 1, 3, 8, None, 1, 4])
    ci = m["hit@5_ci95"]
    assert isinstance(ci, list) and len(ci) == 2
    lo, hi = ci
    assert 0.0 <= lo <= hi <= 1.0
    assert lo <= m["hit@5"] <= hi      # the point estimate sits inside its own CI


def test_ci_deterministic_with_seed():
    a = compute_metrics([1, 2, 6, None, 1, 3, 8, None, 1, 4])["hit@5_ci95"]
    b = compute_metrics([1, 2, 6, None, 1, 3, 8, None, 1, 4])["hit@5_ci95"]
    assert a == b                       # fixed seed → reproducible CI


def test_prefix_conventions():
    # e5 family MUST get asymmetric query:/passage: prefixes
    assert _prefixes("intfloat/multilingual-e5-large") == ("query: ", "passage: ")
    assert _prefixes("intfloat/multilingual-e5-small") == ("query: ", "passage: ")
    # bge-m3 / gte / qwen MUST get NO prefix (wrong prefix silently corrupts vectors)
    assert _prefixes("BAAI/bge-m3") == ("", "")
    assert _prefixes("Alibaba-NLP/gte-multilingual-base") == ("", "")
    assert _prefixes("Qwen/Qwen3-Embedding-0.6B") == ("", "")


def test_script_detection_and_clean():
    assert _is_latin("dehadṛṣṭivaśāt prauḍhā") is True       # IAST = Latin script
    assert _is_latin("जगत् मिथ्या आत्मा") is False           # Devanagari
    # clean strips inline markers + dandas, collapses whitespace
    assert "MU_6" not in _clean("dehadṛṣṭi MU_6,225.26 । foo")
    assert "।" not in _clean("राम ।। sita ॥")


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn(); passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0)
