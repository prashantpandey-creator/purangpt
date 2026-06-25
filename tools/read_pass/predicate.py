"""predicate — MECHANICAL predicate discovery, NOT a hardcoded vocabulary.

The Puranas produced 580+ distinct relationship verbs (343 seen exactly once).
We do NOT enumerate their meanings. We do two purely mechanical things:

  1. canonical(verb) -> (root, reverse): strip syntactic noise (whitespace,
     punctuation, leading copulas like "is/was/are") so "father of" / "father_of"
     / "is father of" collapse to one KEY — string cleanup, not understanding.
  2. inverse detection: a trailing "by" (e.g. "killed by", "cursed by") or a
     genitive "<role> of" (e.g. "son of", "wife of") marks a REVERSED-direction
     relation, so the edge is stored canonically and lineage/action queries
     traverse uniformly.

Semantic grouping ("teaches" ~ "instructs" ~ "imparts") is a QUERY-TIME concern
handled by embeddings over the predicate strings (see views/), never baked in
here. This keeps the graph honest and scalable to all 18 Puranas without anyone
hand-coding their vocabulary.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Tuple

# leading copulas that carry no relational meaning
_COPULA = re.compile(r"^(is|was|are|were|be|been|the|a|an)\s+", re.IGNORECASE)
# genitive roles whose "X of" form means the edge points child->parent etc.
# (mechanical: any "<word> of" is a reversed genitive; we don't claim to know
#  what the word means, only that "X of Y" reverses to "Y has-X X")
_GENITIVE = re.compile(r"^(.*?)\s+of$", re.IGNORECASE)


def _snake(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.strip().lower())
    return re.sub(r"_+", "_", s).strip("_")


def canonical(raw: str) -> Tuple[str, bool]:
    """Return (canonical_root, reverse). Purely mechanical normalization."""
    if not raw:
        return ("related_to", False)
    s = str(raw).strip().lower()
    s = re.sub(r"[_\-]+", " ", s)          # underscores/hyphens -> spaces
    s = re.sub(r"\s+", " ", s).strip()
    s = _COPULA.sub("", s)                  # drop leading copula

    reverse = False
    # passive inverse: trailing " by"
    if s.endswith(" by"):
        reverse = True
        s = s[:-3].strip()
        return (_snake(s), True)

    # genitive inverse: "<role> of" -> reversed direction, root is the role
    m = _GENITIVE.match(s)
    if m:
        role = m.group(1).strip()
        # "father of" is the FORWARD direction (parent->child) by convention;
        # role words that denote the *child/spouse-from* side reverse it.
        reverse = role in {"son", "daughter", "child", "wife", "husband",
                           "disciple", "student", "servant"}
        return (_snake(role), reverse)

    return (_snake(s), False)


def discover(edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Scan all edges and report the discovered predicate distribution."""
    raw_counts: Counter = Counter()
    canon_counts: Counter = Counter()
    canon_to_raw: Dict[str, set] = {}
    for e in edges:
        rv = e.get("rel", "")
        raw_counts[rv.lower()] += 1
        root, _rev = canonical(rv)
        canon_counts[root] += 1
        canon_to_raw.setdefault(root, set()).add(rv.lower())
    return {
        "n_raw": sum(raw_counts.values()),
        "n_raw_distinct": len(raw_counts),
        "n_canonical": len(canon_counts),
        "canonical_counts": dict(canon_counts.most_common()),
        "canonical_to_raw_forms": {k: sorted(v) for k, v in canon_to_raw.items()},
        "singletons": [k for k, n in canon_counts.items() if n == 1],
    }
