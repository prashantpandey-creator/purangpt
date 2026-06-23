"""Tests-first for predicate DISCOVERY (Rule 0 precond A).

The graph must NOT hardcode a semantic predicate vocabulary — the Puranas have
580+ distinct relationship verbs and 343 appear exactly once. So normalization
is purely MECHANICAL:
  1. syntactic canonicalization (whitespace/punctuation/copula stripping) so
     "father of" / "father_of" / "is father of" collapse — NOT because we
     "know" what father means, but because they're the same string modulo noise
  2. inverse detection (the "_by" / "X of Y" passive pattern) so killed_by is
     recognized as the reverse of killed — again mechanical, pattern-based
No hand-maintained map of "these 30 verbs mean lineage". Semantic grouping is a
QUERY-TIME concern (embeddings over predicate strings), not a build-time schema.

Run: venv/bin/python -m tools.read_pass.test_predicate   (exit 0)
"""
from __future__ import annotations

from tools.read_pass import predicate as P


def test_syntactic_canonicalization_collapses_noise():
    # same predicate, different surface noise -> same canonical key
    forms = ["father_of", "father of", "father-of", "  father  of ",
             "is father of", "is_father_of"]
    keys = {P.canonical(f)[0] for f in forms}
    assert len(keys) == 1, f"should collapse to 1 key, got {keys}"


def test_does_not_overcollapse_distinct_verbs():
    # mechanically distinct verbs must stay distinct (no semantic merging)
    assert P.canonical("teaches")[0] != P.canonical("instructs")[0]
    assert P.canonical("killed")[0] != P.canonical("cursed")[0]
    # "served as calf for" is a real once-seen verb — must survive as itself
    assert P.canonical("served as calf for")[0] == "served_as_calf_for"


def test_inverse_detection_by_suffix():
    # killed_by is the inverse of killed -> same root, reverse=True
    root_fwd, rev_fwd = P.canonical("killed")
    root_inv, rev_inv = P.canonical("killed_by")
    assert root_fwd == root_inv
    assert rev_fwd is False and rev_inv is True


def test_inverse_detection_x_of_y_genitive():
    # "son of" is the inverse of "father of"? NO — different roots.
    # But "cursed by" IS inverse of "cursed".
    assert P.canonical("cursed by")[1] is True
    assert P.canonical("cursed")[1] is False
    # genitive "son of" should be recognized as a reversed-direction relation
    # of its own root (child->parent), reverse=True, root "son"
    root, rev = P.canonical("son of")
    assert rev is True


def test_unknown_verb_passes_through_untouched():
    # a verb we've never seen and has no inverse marker survives verbatim
    root, rev = P.canonical("presides over")
    assert root == "presides_over"
    assert rev is False


def test_discover_vocabulary_returns_full_distribution():
    edges = [{"rel": "father of"}, {"rel": "father_of"}, {"rel": "killed"},
             {"rel": "killed_by"}, {"rel": "served as calf for"}]
    vocab = P.discover(edges)
    # father of + father_of collapse; killed + killed_by collapse (inverse)
    assert vocab["n_raw"] == 5
    assert vocab["n_canonical"] <= 3
    assert "father" in str(vocab["canonical_counts"]).lower()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
