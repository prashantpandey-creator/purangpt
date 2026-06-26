"""Tests-first for the verify-GATE on the corpus write path (Rule 0 precond A).

WHY THIS EXISTS — the scar (memory verify-was-bhagavata-only, graph-audit-16-fabricated):
the decoder NARRATES. It produces fluent records whose cites cite real-looking
markers that are NOT actually in the source window — hallucinated story dressed as
fact. run.py:97 writes a record the instant `env["success"]` is true, and
`env["success"]` only means "the model returned parseable JSON" — it says NOTHING
about whether the cites are grounded. So the main corpus-ingest path has been
writing un-verified records straight to disk, where they fold into the graph. That
is exactly how 16 texts became Bhagavata clones.

THE GATE (daddy's call: PRUNE): before a record is written, drop every node whose
cite does not literally appear in its source window. Only verse-defensible facts
reach the graph. This module pins that contract against a REAL record fixture with
a KNOWN-truth window (no LLM call — the fixture's grounding was measured once and
frozen): tools/read_pass/fixtures/gated_write_fixture.json.

  window_full    → 24/24 nodes grounded  (prune removes 0)
  window_partial → 14/24 nodes grounded  (prune removes 10)
  window_empty   →  0/24 nodes grounded  (prune removes ALL, record becomes empty)

Run: venv/bin/python -m tools.read_pass.test_gated_write   (exit 0)
"""
from __future__ import annotations
import json
import os

from tools.read_pass import run as RUN
from tools.read_pass import verify

HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures", "gated_write_fixture.json")


def _fixture():
    with open(FIX) as f:
        return json.load(f)


def _count_nodes(record):
    return sum(len(record.get(fld, []) or []) for fld in verify._NODE_FIELDS)


# ── the gate helper must exist and return the standard shape ──────────────────
def test_gate_record_exists_and_returns_envelope():
    """run.py must expose gate_record(record, window_text) -> envelope.
    This is the seam the write path calls before persisting."""
    assert hasattr(RUN, "gate_record"), "run.gate_record not implemented yet"
    fx = _fixture()
    env = RUN.gate_record(fx["record"], fx["window_full"])
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}, env.keys()
    assert env["success"] is True
    # data carries the pruned record + the drop accounting
    assert "record" in env["data"]
    assert "kept_nodes" in env["data"] and "dropped_nodes" in env["data"]


# ── fully-grounded record passes UNTOUCHED ────────────────────────────────────
def test_fully_grounded_record_is_kept_whole():
    fx = _fixture()
    before = _count_nodes(fx["record"])
    env = RUN.gate_record(fx["record"], fx["window_full"])
    after = _count_nodes(env["data"]["record"])
    assert before == 24, f"fixture drifted: expected 24 nodes, got {before}"
    assert after == before, "a fully-grounded record must lose nothing"
    assert env["data"]["dropped_nodes"] == 0
    assert env["data"]["kept_nodes"] == 24


# ── partially-grounded record: the ungrounded HALF is pruned ──────────────────
def test_partial_record_drops_only_ungrounded_nodes():
    fx = _fixture()
    env = RUN.gate_record(fx["record"], fx["window_partial"])
    rec = env["data"]["record"]
    # 14 of 24 were grounded against window_partial (frozen truth)
    assert env["data"]["kept_nodes"] == 14, env["data"]
    assert env["data"]["dropped_nodes"] == 10
    assert _count_nodes(rec) == 14
    # and EVERY surviving node must actually be grounded (no ungrounded leak)
    present = set(verify.extract_markers(fx["window_partial"]))
    for fld in verify._NODE_FIELDS:
        for n in rec.get(fld, []) or []:
            assert verify.check_node(n, present)["grounded"], \
                f"ungrounded node survived prune: {n.get('name') or n}"


# ── fully-ungrounded record: pruned to empty, and the gate SAYS so ────────────
def test_fully_ungrounded_record_is_emptied_and_flagged():
    """A record whose cites are all hallucinated must NOT reach the graph as
    facts. Prune empties it; the gate reports the record as not-worth-writing so
    the caller can skip it (don't write an all-empty husk)."""
    fx = _fixture()
    env = RUN.gate_record(fx["record"], fx["window_empty"])
    assert env["data"]["kept_nodes"] == 0
    assert env["data"]["dropped_nodes"] == 24
    assert _count_nodes(env["data"]["record"]) == 0
    # the gate signals the record carries no grounded facts
    assert env["data"]["worth_writing"] is False


def test_grounded_record_is_worth_writing():
    fx = _fixture()
    env = RUN.gate_record(fx["record"], fx["window_partial"])
    assert env["data"]["worth_writing"] is True  # 14 real facts survive


# ── the gate preserves provenance + non-node fields (summary, story) ──────────
def test_gate_preserves_provenance_and_prose():
    """Pruning touches ONLY the node lists. Provenance, chapter_summary, story
    must survive — they are how the record joins back to its window and reads."""
    fx = _fixture()
    env = RUN.gate_record(fx["record"], fx["window_partial"])
    rec = env["data"]["record"]
    assert rec.get("_provenance") == fx["record"].get("_provenance")
    for prose_field in ("chapter_summary", "story"):
        if prose_field in fx["record"]:
            assert rec.get(prose_field) == fx["record"][prose_field], \
                f"{prose_field} was mutated by the gate"


# ── the gate must never raise on a malformed record (return clean failure) ────
def test_gate_on_empty_record_is_clean():
    env = RUN.gate_record({}, "some window text mbh_1.1.1")
    assert env["success"] is True
    assert env["data"]["kept_nodes"] == 0
    assert env["data"]["worth_writing"] is False


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
