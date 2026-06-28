"""Tests for the retrieval-ranking fix (WOUND #4 — off-topic SOURCES panel).

Run:  venv/bin/python test_search_ranking.py   (must exit 0)

Reproduces the bug a narrow named-entity query hit in production: "Krishna and
Sudharma" returned Yoga Vāsiṣṭha and other unrelated texts in the sources panel.
Root cause was the scripture floor injecting off-topic chunks at PARITY score and
MMR's diversity preference then PROMOTING them. These tests pin the two pure
helpers that fix it — _floor_keep (relevance gate) and _mmr_select (diversity that
can't beat genuine relevance) — without needing a live DB.
"""
from indexer.search import _mmr_select, _floor_keep, SearchResult


def _r(purana: str, score: float) -> SearchResult:
    return SearchResult(chunk={"purana": purana, "id": f"{purana}-{score}", "text": "x"}, score=score)


# ── Floor relevance gate ────────────────────────────────────────────────────
# RRF scores live around 0.016–0.033. A narrow query's best genuine hit ~0.033;
# an off-topic pool's best hit for that query is far weaker. The gate keeps a
# genuinely cross-relevant hit and drops the noise — but never gates when there
# is no genuine result to measure against (the floor is then all we have).
assert _floor_keep(0.012, top_score=0.033) is False, "weak off-topic floor hit must be DROPPED"
assert _floor_keep(0.026, top_score=0.033) is True,  "strong cross-text floor hit must be KEPT"
assert _floor_keep(0.005, top_score=0.0)   is True,  "no genuine results → don't gate"
assert _floor_keep(0.033, top_score=0.033) is True,  "parity-or-better is kept"

# ── MMR no longer promotes a weak 'diverse' text over a strong on-topic one ──
# Post floor-fix the off-topic chunk carries its TRUE low score (not parity).
# A narrow Krishna query's panel must stay Bhāgavata, Bhāgavata — Yoga Vāsiṣṭha
# must NOT leapfrog the second genuine verse just for being a new source.
narrow = [_r("Bhagavata Purana", 0.033), _r("Bhagavata Purana", 0.030), _r("Yoga Vasistha", 0.011)]
top2 = [s.purana for s in _mmr_select(narrow, top_k=2)]
assert top2 == ["Bhagavata Purana", "Bhagavata Purana"], f"narrow-query panel polluted: {top2}"

# ── Regression guard: the OLD parity behaviour WOULD have surfaced the noise ──
# If the floor still injected at parity (0.033), MMR's zero-overlap bonus would
# put Yoga Vāsiṣṭha second. Proving the floor fix (true score) is what matters.
parity_bug = [_r("Bhagavata Purana", 0.033), _r("Yoga Vasistha", 0.033), _r("Bhagavata Purana", 0.030)]
top2_bug = [s.purana for s in _mmr_select(parity_bug, top_k=2)]
assert top2_bug[1] == "Yoga Vasistha", "sanity: parity injection is exactly what surfaces the off-topic text"

# ── Genuine breadth is preserved when scores are actually comparable ─────────
# A broad thematic query: several texts score near the top → MMR should fan out.
broad = [_r("Bhagavata Purana", 0.033), _r("Bhagavata Purana", 0.032),
         _r("Shiva Purana", 0.031), _r("Devi Bhagavata", 0.030)]
picks = [s.purana for s in _mmr_select(broad, top_k=3)]
assert len(set(picks)) >= 2, f"broad query lost its breadth: {picks}"
assert ("Shiva Purana" in picks or "Devi Bhagavata" in picks), f"diversity not surfaced: {picks}"

print("✓ all retrieval-ranking tests passed")
