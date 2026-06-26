"""Tests-first for chunk_marker_audit (Rule 0 precond A).

WHY THIS EXISTS: the verify-gate (commit eed9bfa) prunes any decoded node whose
cite isn't literally in its source window. That makes a decode only as good as the
chunk file's verse markers. We discovered decode_audit counts mahabharata.jsonl
(HTML junk, 0 markers — would husk 100%) while mahabharata_bori_chunks.jsonl (the
BORI critical edition, clean mbh_PP.CCC.VVV markers across all 1995 chapters) sits
right there. And it's systemic: garuda/skanda/kurma chunk files also have 0 markers.

So before spending tokens on ANY decode, this tool scans chunk files and classifies
each: decodable-now (markers present) vs needs-normalization (no markers → the gate
would husk it). Pure Rule-0 decision tree: read file → group → sample windows →
count markers (verify._MARKER_RE, the same grammar the gate uses) → branch.

The test oracle is FROZEN real output (fixtures/known_files.json), captured once:
  BORI first window   → 211 markers  → decodable
  junk first window   →   0 markers  → needs_normalization

Run: venv/bin/python -m tools.chunk_marker_audit.test_check   (exit 0)
"""
from __future__ import annotations
import json
import os

from tools.chunk_marker_audit import check

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures", "known_files.json")
CHUNK_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "data", "chunks")

# the two real files whose ground truth the fixture froze
MARKED = os.path.join(CHUNK_DIR, "mahabharata_bori_chunks.jsonl")
UNMARKED = os.path.join(CHUNK_DIR, "mahabharata.jsonl")


def _fixture():
    with open(FIX) as f:
        return json.load(f)


# ── envelope shape (precond B) ────────────────────────────────────────────────
def test_run_returns_envelope():
    env = check.run([MARKED])
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}, env.keys()
    assert isinstance(env["errors"], list)


# ── the core classification, against frozen real truth ────────────────────────
def test_marked_file_classified_decodable():
    """The BORI critical edition has clean markers → decodable."""
    env = check.run([MARKED])
    assert env["success"]
    files = {f["file"]: f for f in env["data"]["files"]}
    rec = files[MARKED]
    assert rec["status"] == "decodable", rec
    assert rec["windows_sampled"] >= 1
    # it found real markers (matches the frozen oracle ballpark — many, not zero)
    assert rec["markers_found"] > 0
    assert rec["sample_markers"], "should surface example markers for eyeballing"


def test_unmarked_file_classified_needs_normalization():
    """mahabharata.jsonl is HTML junk with 0 markers → would husk → flagged."""
    env = check.run([UNMARKED])
    assert env["success"]
    files = {f["file"]: f for f in env["data"]["files"]}
    rec = files[UNMARKED]
    assert rec["status"] == "needs_normalization", rec
    assert rec["markers_found"] == 0


def test_summary_buckets_decodable_vs_needs_normalization():
    """Running both files, the data must bucket them so a caller sees the split
    at a glance (which texts can be decoded now, which need a marker pass)."""
    env = check.run([MARKED, UNMARKED])
    d = env["data"]
    assert d["n_files"] == 2
    assert d["n_decodable"] == 1
    assert d["n_needs_normalization"] == 1
    # convenience name lists for the orchestrator
    assert MARKED in d["decodable"]
    assert UNMARKED in d["needs_normalization"]


# ── the real failure modes ────────────────────────────────────────────────────
def test_missing_file_is_flagged_not_crash():
    env = check.run([os.path.join(CHUNK_DIR, "does_not_exist.jsonl")])
    # the run as a whole still succeeds; the missing file is recorded as an error row
    assert env["success"] is True
    files = {f["file"]: f for f in env["data"]["files"]}
    rec = next(iter(files.values()))
    assert rec["status"] == "missing"
    assert env["data"]["n_missing"] == 1


def test_empty_file_list_is_clean_failure():
    env = check.run([])
    assert env["success"] is False
    assert env["errors"] and env["errors"][0]["code"] == "no_files"


def test_marker_grammar_matches_the_gate():
    """The audit MUST use the same marker regex the verify-gate uses, or it would
    bless files the gate then husks. Pin that they agree on the real BORI window."""
    from tools.read_pass import verify
    env = check.run([MARKED])
    rec = {f["file"]: f for f in env["data"]["files"]}[MARKED]
    # every surfaced sample marker is a real verify marker
    for m in rec["sample_markers"]:
        assert verify._MARKER_RE.search(m), f"audit surfaced a non-marker: {m!r}"


def test_metadata_reports_sampling_params():
    env = check.run([MARKED], sample_windows=3)
    md = env["metadata"]
    assert md.get("sample_windows") == 3
    assert "n_files" in md


def test_malformed_file_is_isolated_not_fatal():
    """A file whose chunk-ids group.run can't parse must become a single
    'group_failed' row — NOT crash the whole scan. (Found on the real corpus:
    one chunk file's ids lack the -N suffix group.run splits on → IndexError.)
    A healthy file scanned alongside it must still classify fine."""
    bad = os.path.join(CHUNK_DIR, "all_chunks.jsonl")
    env = check.run([bad, MARKED])
    assert env["success"] is True, "one bad file must not fail the whole run"
    files = {f["file"]: f for f in env["data"]["files"]}
    assert files[MARKED]["status"] == "decodable"  # healthy file unaffected
    bad_row = files[bad]
    # whatever the offender's fate, it's a well-formed row, never an exception
    assert bad_row["status"] in (
        "group_failed", "decodable", "needs_normalization", "empty", "missing"), bad_row
    if bad_row["status"] == "group_failed":
        assert bad_row.get("error"), "a group_failed row must explain why"


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
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
