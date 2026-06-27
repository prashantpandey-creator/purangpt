"""Tests-first (Rule 0, precondition A) for the chapter grouper.

Run: venv/bin/python -m tools.read_pass.test_group   (must exit 0)

These assert the grouper turns raw verse-chunks into correct chapter WINDOWS,
using a REAL captured fixture (fixture_bhagavata_head.jsonl) so we test
real-input -> envelope-out without re-reading the whole corpus. The bug this
guards against: grouping by `chapter` value (which collides across cantos)
instead of by CONTIGUOUS RUN in global-seq order.
"""
from __future__ import annotations
import json
import os

from tools.read_pass import group

HERE = os.path.dirname(__file__)
FIXTURE = os.path.join(HERE, "fixture_bhagavata_head.jsonl")


def _load_fixture():
    with open(FIXTURE) as f:
        return [json.loads(line) for line in f]


def test_envelope_shape():
    env = group.run(FIXTURE)
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}, env.keys()
    assert env["success"] is True, env["errors"]
    assert "windows" in env["data"]
    assert isinstance(env["data"]["windows"], list)


def test_groups_into_contiguous_runs_not_value_buckets():
    # The fixture covers the first 4 contiguous chapter-runs. Grouping by
    # contiguous run must yield exactly those windows in order.
    env = group.run(FIXTURE)
    windows = env["data"]["windows"]
    # fixture was captured as first 4 runs (the 4th may be partial / cut)
    assert len(windows) >= 3, f"expected >=3 windows, got {len(windows)}"
    # windows must be ordered by global sequence (monotonic, non-overlapping)
    last_seq = -1
    for w in windows:
        assert w["seq_start"] > last_seq, "windows overlap or out of order"
        assert w["seq_end"] >= w["seq_start"]
        last_seq = w["seq_end"]


def test_window_carries_concatenated_text_and_verse_provenance():
    env = group.run(FIXTURE)
    w = env["data"]["windows"][0]
    assert w["purana"] == "Bhagavata Purana"
    assert w["chapter_label"]  # human-readable chapter id
    assert isinstance(w["text"], str) and len(w["text"]) > 50
    # provenance: every window knows which verse_ranges + chunk ids it spans
    assert isinstance(w["verse_ranges"], list) and len(w["verse_ranges"]) >= 1
    assert isinstance(w["chunk_ids"], list) and len(w["chunk_ids"]) >= 1
    assert w["n_chunks"] == len(w["chunk_ids"])


def test_text_is_in_verse_order_within_window():
    # Concatenated chapter text must follow global-seq order so the LLM reads
    # the story in narrative sequence, not shuffled.
    raw = _load_fixture()
    env = group.run(FIXTURE)
    w0 = env["data"]["windows"][0]
    # first chunk's text must appear before second chunk's text in the window
    first_two = [r for r in raw if r["id"] in w0["chunk_ids"]][:2]
    if len(first_two) == 2:
        i0 = w0["text"].find(first_two[0]["text"][:30])
        i1 = w0["text"].find(first_two[1]["text"][:30])
        assert i0 != -1 and i1 != -1 and i0 < i1, "window text not in verse order"


def test_missing_file_returns_false_envelope_not_raise():
    env = group.run("/no/such/file.jsonl")
    assert env["success"] is False
    assert env["data"] in (None, {}, [])
    assert env["errors"] and env["errors"][0]["code"]


def test_metadata_reports_counts():
    env = group.run(FIXTURE)
    md = env["metadata"]
    assert md["n_windows"] == len(env["data"]["windows"])
    assert md["n_chunks_in"] >= md["n_windows"]


def test_mega_windows_get_subwindowed():
    # Most Puranas have chapter=0 for all chunks (mono-chapter).
    # The grouper must sub-window these by stride so no single window
    # exceeds MAX_WINDOW_CHUNKS, rather than creating one 55K-chunk monster.
    import tempfile
    mono = [{"id": f"test-0-{i}", "purana": "TestPurana", "chapter": 0,
             "text": f"verse {i} " * 10, "verse_range": f"v{i}"}
            for i in range(1, 201)]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for c in mono: f.write(json.dumps(c) + "\n")
        fpath = f.name
    try:
        env = group.run(fpath)
        assert env["success"]
        ws = env["data"]["windows"]
        # with 200 mono-chapter chunks and MAX ~100, we should get >=2 windows
        assert len(ws) >= 2, f"200 mono-chapter chunks should sub-window, got {len(ws)} windows"
        for w in ws:
            assert w["n_chunks"] <= group.MAX_WINDOW_CHUNKS, \
                f"window too big: {w['n_chunks']} > {group.MAX_WINDOW_CHUNKS}"
        # all chunks accounted for
        total = sum(w["n_chunks"] for w in ws)
        assert total == 200, f"lost chunks: {total} != 200"
        # still in order
        for i in range(len(ws)-1):
            assert ws[i]["seq_end"] < ws[i+1]["seq_start"]
    finally:
        os.unlink(fpath)


def test_max_chunks_param_makes_finer_windows():
    # Dense texts (Upanishads/sutras) decode richer at a smaller window. A small
    # max_chunks must split a mono-chapter run into more, smaller windows than the
    # default — without losing or reordering chunks.
    import tempfile
    mono = [{"id": f"t-0-{i}", "purana": "T", "chapter": 0,
             "text": f"v{i} " * 5, "verse_range": f"v{i}"} for i in range(1, 61)]  # 60 chunks
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for c in mono: f.write(json.dumps(c) + "\n")
        fp = f.name
    try:
        big = group.run(fp)                     # default 80 -> 1 window (60 < 80)
        small = group.run(fp, max_chunks=15)    # 15 -> 4 windows
        assert len(big["data"]["windows"]) == 1, len(big["data"]["windows"])
        assert len(small["data"]["windows"]) >= 4, len(small["data"]["windows"])
        assert all(w["n_chunks"] <= 15 for w in small["data"]["windows"])
        assert sum(w["n_chunks"] for w in small["data"]["windows"]) == 60, "lost chunks"
        assert small["metadata"]["max_chunks"] == 15
        # order preserved
        ws = small["data"]["windows"]
        for i in range(len(ws) - 1):
            assert ws[i]["seq_end"] < ws[i + 1]["seq_start"]
    finally:
        os.unlink(fp)


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
