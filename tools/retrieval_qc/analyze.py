"""retrieval_qc.analyze — PURE analysis over collected search results.

Separated from live DB collection so it is deterministic and fixture-testable
(Rule 0, precondition A): real-search-output-in → metrics-out, no DB required.

Input shape (what `collect.py` produces, and what fixtures capture):
    {
      "queries": [
        {
          "query": "what is dharma",
          "kind": "hybrid" | "gretil",          # which retrieval path
          "results": [
            {"source": "Agni Purana", "score": 0.81, "rank": 0,
             "category": "mahapurana", "id": "agni-123",
             "fts_hit": false},                  # gretil/hybrid: did keyword half fire?
            ...
          ]
        }, ...
      ],
      "corpus": {                                # optional, for coverage/metadata checks
        "sources": [{"name": "Agni Purana", "chunks": 2555, "category": "mahapurana"}, ...]
      }
    }

The analysis answers the 7 QC questions and returns a verdict per check with a
machine-checkable `pass` boolean so the tool can gate "is retrieval healthy?".
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List

# A source "name" that looks like a per-file id rather than a clean text name.
# e.g. "Shailendra Sharma Darshan — darshans202018-2", "compilation6-2", "kali-yuga-2"
_FILE_ID_HINTS = re.compile(
    r"(darshan\w*\d|compilation\d|\b\d{4,}\b|-\d+$|_\d+$|\bpart\s*\d|\bvol\s*\d)",
    re.IGNORECASE,
)

# Thresholds — the pass/fail criteria. Tunable; documented in README.
MAX_SINGLE_SOURCE_PCT = 15.0       # no single source should exceed this share of slots
MIN_DISTINCT_SOURCES = 15          # at least this many distinct sources across the battery
MAX_ALPHA_CORR = 0.30              # |corr(alpha_rank, frequency)| must stay below this
MIN_COVERAGE_PCT = 60.0            # >= this % of corpus sources should be reachable
MIN_FTS_HIT_RATE = 30.0            # keyword half should fire on >= this % of queries (where applicable)


def _spearman(xs: List[float], ys: List[float]) -> float:
    """Spearman rank correlation (no scipy). Returns 0.0 for degenerate input."""
    n = len(xs)
    if n < 3:
        return 0.0

    def ranks(vals: List[float]) -> List[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0  # average rank (1-based) for ties
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def _all_results(payload: Dict[str, Any], kind: str | None = None) -> List[dict]:
    out = []
    for q in payload.get("queries", []):
        if kind and q.get("kind") != kind:
            continue
        out.extend(q.get("results", []))
    return out


def check_distribution(payload: Dict[str, Any], kind: str | None = None) -> Dict[str, Any]:
    """How concentrated are sources? Flags any source over MAX_SINGLE_SOURCE_PCT."""
    results = _all_results(payload, kind)
    total = len(results)
    counts = Counter((r.get("source") or "?") for r in results)
    if total == 0:
        return {"check": "distribution", "pass": False, "total_slots": 0,
                "distinct_sources": 0, "top": [],
                "note": "no results collected"}
    top = [{"source": s, "slots": c, "pct": round(100 * c / total, 1)}
           for s, c in counts.most_common(15)]
    worst_pct = top[0]["pct"] if top else 0.0
    return {
        "check": "distribution",
        "pass": worst_pct <= MAX_SINGLE_SOURCE_PCT and len(counts) >= MIN_DISTINCT_SOURCES,
        "total_slots": total,
        "distinct_sources": len(counts),
        "worst_source_pct": worst_pct,
        "top": top,
        "thresholds": {"max_single_source_pct": MAX_SINGLE_SOURCE_PCT,
                       "min_distinct_sources": MIN_DISTINCT_SOURCES},
    }


def check_alphabetic_bias(payload: Dict[str, Any], kind: str | None = None) -> Dict[str, Any]:
    """Correlation between a source's alphabetical position and how often it is
    retrieved. A strong NEGATIVE correlation = earlier-alphabet sources win =
    positional bias (the Agni Purana symptom)."""
    results = _all_results(payload, kind)
    counts = Counter((r.get("source") or "?") for r in results)
    sources = sorted(counts.keys())
    if len(sources) < 3:
        return {"check": "alphabetic_bias", "pass": True, "correlation": 0.0,
                "note": "too few distinct sources to judge"}
    alpha_rank = list(range(len(sources)))           # 0 = 'A...' first
    freq = [counts[s] for s in sources]
    corr = _spearman([float(a) for a in alpha_rank], [float(f) for f in freq])
    return {
        "check": "alphabetic_bias",
        # Negative corr means earlier letters retrieved MORE. We fail on |corr| high.
        "pass": abs(corr) <= MAX_ALPHA_CORR,
        "correlation": round(corr, 3),
        "interpretation": (
            "earlier-alphabet sources over-retrieved (positional bias)" if corr < -MAX_ALPHA_CORR
            else "later-alphabet sources over-retrieved" if corr > MAX_ALPHA_CORR
            else "no meaningful alphabetic bias"
        ),
        "threshold": MAX_ALPHA_CORR,
    }


def check_metadata_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Audit source names for file-id pollution (defeats MMR diversity)."""
    corpus = payload.get("corpus", {})
    names = [s.get("name", "") for s in corpus.get("sources", [])]
    if not names:
        # Fall back to names seen in results.
        names = sorted({(r.get("source") or "") for r in _all_results(payload)})
    polluted = [n for n in names if _FILE_ID_HINTS.search(n or "")]
    return {
        "check": "metadata_quality",
        "pass": len(polluted) == 0,
        "total_source_names": len(names),
        "polluted_count": len(polluted),
        "polluted_examples": polluted[:15],
        "note": ("source names containing digits/file-id patterns fragment a single "
                 "text into many 'sources', defeating diversity (MMR) ranking"),
    }


def check_known_items(payload: Dict[str, Any], expectations: List[dict]) -> Dict[str, Any]:
    """For curated (query → expected source substring) pairs, is the expected
    source present in the top-k results? expectations come from collect/fixture."""
    by_query = {q["query"]: q.get("results", []) for q in payload.get("queries", [])}
    rows = []
    hits = 0
    for exp in expectations:
        q = exp["query"]
        want = exp["expect_source_contains"].lower()
        top_k = exp.get("top_k", 5)
        results = by_query.get(q, [])[:top_k]
        found = any(want in (r.get("source") or "").lower() for r in results)
        rows.append({"query": q, "expect": exp["expect_source_contains"],
                     "found_in_top_k": found,
                     "got": [r.get("source") for r in results[:3]]})
        hits += 1 if found else 0
    total = len(expectations)
    return {
        "check": "known_item_recall",
        "pass": total > 0 and hits == total,
        "hits": hits, "total": total,
        "recall_pct": round(100 * hits / total, 1) if total else 0.0,
        "rows": rows,
    }


def check_hybrid_contribution(payload: Dict[str, Any]) -> Dict[str, Any]:
    """How often does the keyword (FTS) half actually fire? If ~0, 'hybrid' is a lie."""
    qs = payload.get("queries", [])
    judged = [q for q in qs if any("fts_hit" in r for r in q.get("results", []))]
    if not judged:
        return {"check": "hybrid_contribution", "pass": True,
                "note": "no fts_hit data collected — skipped"}
    fired = sum(1 for q in judged
                if any(r.get("fts_hit") for r in q.get("results", [])))
    rate = 100 * fired / len(judged)
    return {
        "check": "hybrid_contribution",
        "pass": rate >= MIN_FTS_HIT_RATE,
        "fts_fire_rate_pct": round(rate, 1),
        "queries_with_fts_hit": fired,
        "queries_judged": len(judged),
        "threshold": MIN_FTS_HIT_RATE,
    }


def check_coverage(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Over the whole query battery, what % of corpus sources EVER appear?"""
    corpus = payload.get("corpus", {})
    corpus_sources = {s.get("name", "") for s in corpus.get("sources", [])}
    if not corpus_sources:
        return {"check": "coverage", "pass": True,
                "note": "no corpus source list provided — skipped"}
    seen = {(r.get("source") or "") for r in _all_results(payload)}
    reached = corpus_sources & seen
    pct = 100 * len(reached) / len(corpus_sources)
    return {
        "check": "coverage",
        "pass": pct >= MIN_COVERAGE_PCT,
        "coverage_pct": round(pct, 1),
        "reached": len(reached),
        "corpus_sources": len(corpus_sources),
        "never_reached_examples": sorted(corpus_sources - seen)[:15],
        "threshold": MIN_COVERAGE_PCT,
    }


def check_corpus_separation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze whether Guruji (Shailendra Sharma) material is tangled with
    scripture — the 'separate DB?' question. Reports volume share vs source-name
    cardinality share. High cardinality share at low volume = fragmentation that
    pollutes ranking and argues for clean separation (flag or separate store)."""
    corpus = payload.get("corpus", {})
    sources = corpus.get("sources", [])
    if not sources:
        return {"check": "corpus_separation", "pass": True,
                "note": "no corpus source list provided — skipped"}

    guru_re = re.compile(r"(shailendra|sharma|yogeshwari|darshan)", re.IGNORECASE)
    guru_cats = {"yogic-discourse", "yogic-commentary", "yoga_commentary", "nath-sampradaya"}

    guru_chunks = guru_names = 0
    total_chunks = total_names = 0
    for s in sources:
        name = s.get("name", "")
        cat = (s.get("category") or "").lower()
        chunks = int(s.get("chunks", 0))
        is_guru = bool(guru_re.search(name)) or cat in guru_cats
        total_chunks += chunks
        total_names += 1
        if is_guru:
            guru_chunks += chunks
            guru_names += 1

    vol_share = 100 * guru_chunks / total_chunks if total_chunks else 0.0
    name_share = 100 * guru_names / total_names if total_names else 0.0
    # Fragmentation index: how over-represented Guruji is in NAME-space vs VOLUME-space.
    frag_index = (name_share / vol_share) if vol_share else 0.0
    return {
        "check": "corpus_separation",
        # This check never "fails" the build — it's advisory analysis.
        "pass": True,
        "guruji_volume_pct": round(vol_share, 1),
        "guruji_sourcename_pct": round(name_share, 1),
        "fragmentation_index": round(frag_index, 1),
        "recommendation": (
            "SEPARATE / FLAG STRONGLY: Guruji material is heavily fragmented in "
            "source-name space relative to its volume — it pollutes diversity ranking "
            "and is used for a different purpose (voice/cognition vs citation). "
            "Either give it a clean corpus_type and query it on a separate channel, "
            "or move it to its own store."
            if frag_index >= 3.0 else
            "Guruji material is reasonably proportioned; a clean corpus_type flag "
            "with filtered queries is likely sufficient (no separate DB required)."
        ),
    }


def analyze(payload: Dict[str, Any], expectations: List[dict] | None = None) -> Dict[str, Any]:
    """Run all checks and return a combined verdict dict (the envelope's `data`)."""
    expectations = expectations or []
    checks = {
        "distribution_hybrid": check_distribution(payload, "hybrid"),
        "distribution_gretil": check_distribution(payload, "gretil"),
        "alphabetic_bias_gretil": check_alphabetic_bias(payload, "gretil"),
        "alphabetic_bias_hybrid": check_alphabetic_bias(payload, "hybrid"),
        "metadata_quality": check_metadata_quality(payload),
        "known_item_recall": check_known_items(payload, expectations),
        "hybrid_contribution": check_hybrid_contribution(payload),
        "coverage": check_coverage(payload),
        "corpus_separation": check_corpus_separation(payload),
    }
    # Gating checks (advisory ones like corpus_separation excluded from the gate).
    gating = [v for k, v in checks.items() if k != "corpus_separation"]
    failed = [v["check"] for v in gating if not v.get("pass", False)]
    return {
        "healthy": len(failed) == 0,
        "failed_checks": failed,
        "checks": checks,
    }
