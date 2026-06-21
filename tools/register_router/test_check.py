"""Tests-first for register_router.check (Rule 0, precondition A).

Run: venv/bin/python -m tools.register_router.test_check
Must exit 0. No pytest in this repo — explicit asserts.

The decision boundary we are pinning down:
  - Explicit scholarly intent ('cite', 'sources', 'exact verse', 'according to
    the text', 'compare X and Y') => scholar layout.
  - Genuine complexity (multi-part questions, "explain how/why ... and ...",
    analytical verbs over a long query) => scholar layout.
  - Simple / personal / short / devotional asks => guru (flowing) voice.
The point of scripting it: the choice is deterministic and testable, not left
to the model's whim (which silently regressed the old research-mode layout).
"""
from __future__ import annotations

from tools.register_router.check import run, ENVELOPE_KEYS


def _ok(env):
    # Envelope shape (precondition B) holds on every call.
    assert set(env.keys()) == ENVELOPE_KEYS, env.keys()
    assert env["success"] is True, env["errors"]
    d = env["data"]
    assert d["register"] in ("scholar", "guru"), d
    assert isinstance(d["score"], (int, float)), d
    assert isinstance(d["signals"], list), d
    return d


# ── Scholar: explicit citation/source intent ────────────────────────────────
SCHOLAR_EXPLICIT = [
    "Cite the verse where Krishna speaks of the gunas.",
    "What is the exact source for the story of Markandeya?",
    "Give me the references for Shiva's role in the Linga Purana.",
    "According to the text, what does the Vishnu Purana say about pralaya?",
    "What exactly does the Gita say in chapter 2 about the soul?",
    "Quote the original Sanskrit shloka on ahimsa.",
]

# ── Scholar: complexity, no explicit keyword ────────────────────────────────
SCHOLAR_COMPLEX = [
    "Explain how the concept of dharma differs between the Mahabharata and the "
    "Manusmriti, and why that difference matters for a householder today.",
    "Compare the Samkhya account of prakriti with the Vedantic view of maya.",
    "Analyse the relationship between karma, rebirth, and moksha across the "
    "Upanishads and the Puranas.",
    "What are the differences between the three gunas and how do they each "
    "shape the mind, and which one dominates in deep meditation?",
]

# ── Guru: simple / personal / short / devotional ────────────────────────────
GURU_SIMPLE = [
    "Who is Hanuman?",
    "I feel lost. What should I do?",
    "What is dharma?",
    "Tell me about Krishna.",
    "How do I find peace?",
    "namaste guruji",
    "Is anger a sin?",
    "What happens after death?",
]


def test_explicit_scholar():
    for q in SCHOLAR_EXPLICIT:
        d = _ok(run(q))
        assert d["register"] == "scholar", f"expected scholar: {q!r} -> {d}"
        assert any(s.startswith("explicit:") for s in d["signals"]), d


def test_complex_scholar():
    for q in SCHOLAR_COMPLEX:
        d = _ok(run(q))
        assert d["register"] == "scholar", f"expected scholar (complex): {q!r} -> {d}"


def test_simple_guru():
    for q in GURU_SIMPLE:
        d = _ok(run(q))
        assert d["register"] == "guru", f"expected guru: {q!r} -> {d}"


def test_empty_and_garbage():
    # Empty query => guru default, never crash.
    d = _ok(run(""))
    assert d["register"] == "guru", d
    d = _ok(run("   "))
    assert d["register"] == "guru", d


def test_directive_present_only_for_scholar():
    # The injected directive text is non-empty for scholar, empty for guru,
    # so the caller can unconditionally append data["directive"].
    scholar = run(SCHOLAR_EXPLICIT[0])["data"]
    guru = run(GURU_SIMPLE[0])["data"]
    assert scholar["directive"].strip(), "scholar must carry a directive"
    assert guru["directive"] == "", "guru must carry empty directive"
    # The directive must actually instruct the structured layout.
    assert "Summary" in scholar["directive"] or "summary" in scholar["directive"]


def test_score_monotonic():
    # A heavily-scholarly query should outscore a plainly-simple one.
    hi = run(SCHOLAR_COMPLEX[0])["data"]["score"]
    lo = run(GURU_SIMPLE[0])["data"]["score"]
    assert hi > lo, (hi, lo)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\nAll {len(fns)} register_router tests passed.")
