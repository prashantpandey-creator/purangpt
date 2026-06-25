"""Tests-first for decode_audit (Rule 0 precond A) — run against REAL captured fixtures.

WHY THIS TOOL EXISTS: hand-counting pending comprehension work gave THREE different
answers (1500, 7061, 2585) because every naive key lies:
  - filename (garuda_v1.records.jsonl) — its first record is actually a Bhagavata chapter
  - chapter_label ("Chapter 1") — collides across all 40+ texts
  - seq_start — group.run produces different seq values today than at decode time
The ONLY globally-stable resume key is `_provenance.chunk_ids` (e.g. 'bhagavata-1-1'),
namespaced by source text. This tool keys coverage on chunk_ids and is fixture-tested
so it can't drift back into phantom-gap territory.

Deterministic set arithmetic over JSON — no LLM, no network. So it gets tests.
Run: venv/bin/python -m tools.decode_audit.test_check   (exit 0)
"""
from __future__ import annotations

import json
import os

from tools.decode_audit import check

_FIX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures.json")))


# --- the contract -------------------------------------------------------------
def test_emits_envelope():
    env = check.audit_coverage(covered_chunk_ids=set(), windows=[])
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"] is True


def test_covered_chunk_ids_extracted_from_provenance_not_filename():
    # the garuda_v1 fixture record carries BHAGAVATA chunk_ids — coverage must be
    # keyed on the chunk_ids inside the record, never on which file it sits in.
    recs = _FIX["sample_records"]
    covered = check.covered_from_records(recs)
    assert "bhagavata-1-1" in covered, "must read chunk_ids from _provenance, not the filename"


def test_window_is_pending_iff_no_chunk_id_covered():
    # a window is DONE if ANY of its chunk_ids appears in a record; else PENDING.
    windows = _FIX["sample_windows_gheranda"]  # gheranda is fully UNdecoded
    env = check.audit_coverage(covered_chunk_ids=set(), windows=windows)
    assert env["data"]["pending"] == len(windows)
    assert env["data"]["done"] == 0


def test_window_counts_done_when_its_chunk_is_covered():
    windows = _FIX["sample_windows_gheranda"]
    first_chunk = windows[0]["chunk_ids"][0]
    env = check.audit_coverage(covered_chunk_ids={first_chunk}, windows=windows)
    assert env["data"]["done"] == 1
    assert env["data"]["pending"] == len(windows) - 1


def test_no_phantom_gap_from_label_collision():
    # SCOPE TEST (the FINDINGS.md lesson): two different texts both have "Chapter 1".
    # If coverage keyed on chapter_label, a Bhagavata record would falsely mark a
    # Gheranda window done. chunk_id prefixes (namespaced by text) prevent it.
    gheranda_win = _FIX["sample_windows_gheranda"][0]  # chunk_ids start 'gheranda_samhita-'
    bhagavata_covered = {"bhagavata-1-1", "bhagavata-1-2"}
    env = check.audit_coverage(covered_chunk_ids=bhagavata_covered, windows=[gheranda_win])
    assert env["data"]["pending"] == 1, "bhagavata coverage must NOT mark a gheranda window done"
    assert env["data"]["done"] == 0


def test_partial_window_counts_done_if_any_chunk_covered():
    # a window spans several chunks; covering even one means that chapter was
    # comprehended (records are per-chapter). Any-overlap, not full-overlap.
    win = {"chapter_label": "Chapter 2", "chunk_ids": ["x-2-1", "x-2-2", "x-2-3"]}
    env = check.audit_coverage(covered_chunk_ids={"x-2-2"}, windows=[win])
    assert env["data"]["done"] == 1


def test_empty_inputs_are_success_not_error():
    env = check.audit_coverage(covered_chunk_ids=set(), windows=[])
    assert env["success"] is True
    assert env["data"]["done"] == 0 and env["data"]["pending"] == 0


def test_pending_chunk_ids_listed_for_handoff():
    # the orchestrator needs the ACTUAL pending chunk_ids to fan out decode work.
    windows = _FIX["sample_windows_gheranda"]
    env = check.audit_coverage(covered_chunk_ids=set(), windows=windows)
    pend_ids = env["data"]["pending_chunk_ids"]
    assert windows[0]["chunk_ids"][0] in pend_ids
    assert all(cid.startswith("gheranda_samhita-") for cid in pend_ids)


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
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
