"""Tests-first for translation_finish (Rule 0, precondition A).

The job: the bio re-translation was done as parallel agent batches that wrote
{window_index: english} into agent_batches/*_OUT.json, but 2 batches died
(windows 10-19, 80-89) leaving 24 holes, and the Gita was never redone. This
tool deterministically:
  1. gathers the GOOD translated windows from the OUT files (keyed by index),
  2. finds the MISSING indices vs the full window count of the source,
  3. translates ONLY the missing windows via an injected caller (DeepSeek live;
     a fake caller here so the test never hits the network),
  4. splices all windows in strict index order + assembles the .md,
  5. validates the assembled EN/RU ratio is healthy (the gut-check that caught
     the 0.19 broken original),
  6. returns the envelope; writing the swap is a separate explicit step.

The crux this guards: indices must line up (a spliced window in the wrong slot
silently corrupts the book), and a still-broken ratio must FAIL, not pass.

Run: venv/bin/python -m tools.translation_finish.test_check   (exit 0)
"""
from __future__ import annotations

import json
import os
import tempfile

from tools.translation_finish import check


# --- fixtures: a tiny "source" + OUT files with a hole ------------------------
def _ru(n_windows: int) -> str:
    """Build RU text that make_windows() splits into exactly n_windows.

    make_windows packs paragraphs up to max_chars; we pass a small max_chars at
    call time so each ~big paragraph block becomes its own window.
    """
    block = ("Это русский текст для перевода. " * 200).strip()  # ~6000 chars
    return "\n\n".join(block for _ in range(n_windows))


_MAXC = 8000  # window cap used in tests so each _ru block = one window


def _write_out_files(d: str, present_indices, text_for):
    """Write one agent_batches-style OUT file covering `present_indices`."""
    os.makedirs(os.path.join(d, "agent_batches"), exist_ok=True)
    results = [{"window_index": i, "english": text_for(i)} for i in sorted(present_indices)]
    path = os.path.join(d, "agent_batches", "bio_batch_00_OUT.json")
    json.dump({"agent_id": 0, "window_start": 0,
               "windows_processed": len(results), "results": results},
              open(path, "w", encoding="utf-8"))


def _en_like(text: str) -> str:
    """English output ~1.0x the input length — matches real DeepSeek (ratio ~1.0)."""
    unit = "English translation of this window paragraph. "  # 46 chars
    return unit * (max(len(text), 1) // len(unit) + 1)


def _fake_caller(text, model=None, api_key=None, **k):
    return _en_like(text)


def _good_text(i: int) -> str:
    # a "good" pre-translated window: full-length English (~6400 chars) so the
    # assembled ratio is realistic, with a unique marker for order assertions.
    return f"GOODWIN{i} " + _en_like("x" * 6400)


def _run(d, present, n_windows, caller=_fake_caller, **kw):
    _write_out_files(d, present, kw.pop("text_for", _good_text))
    src = os.path.join(d, "src.txt")
    open(src, "w", encoding="utf-8").write(_ru(n_windows))
    return check.run(src_path=src, out_dir=d, caller=caller,
                     out_md=os.path.join(d, "result.md"), max_chars=_MAXC, **kw)


# --- the gather/plan step (no network) ----------------------------------------
def test_returns_envelope():
    with tempfile.TemporaryDirectory() as d:
        env = _run(d, range(5), 5)
        assert set(env.keys()) == {"success", "data", "metadata", "errors"}


def test_identifies_exactly_the_missing_windows():
    with tempfile.TemporaryDirectory() as d:
        env = _run(d, [0, 1, 2, 5, 6], 7)   # missing: 3,4
        assert env["success"] is True
        assert env["data"]["missing_indices"] == [3, 4]
        assert env["data"]["n_translated_now"] == 2


def test_good_windows_are_REUSED_not_retranslated():
    calls = {"n": 0}
    def counting_caller(text, model=None, api_key=None, **k):
        calls["n"] += 1
        return "english paragraph text here. " * 80
    with tempfile.TemporaryDirectory() as d:
        env = _run(d, [0, 1, 3], 4, caller=counting_caller)  # missing: 2
        assert calls["n"] == 1
        assert env["data"]["missing_indices"] == [2]


def test_assembled_md_has_all_windows_in_ORDER():
    with tempfile.TemporaryDirectory() as d:
        env = _run(d, [0, 2, 3], 4)   # missing 1; _good_text carries GOODWIN markers
        assert env["success"] is True
        body = open(os.path.join(d, "result.md"), encoding="utf-8").read()
        i0, i2, i3 = body.index("GOODWIN0"), body.index("GOODWIN2"), body.index("GOODWIN3")
        assert i0 < i2 < i3
        assert "[[GAP" not in body and "[[TRANSLATION GAP" not in body


def test_no_gaps_remaining_reported():
    with tempfile.TemporaryDirectory() as d:
        env = _run(d, [0, 1], 4)   # missing 2,3
        assert env["data"]["gaps_remaining"] == 0
        assert env["data"]["n_windows_total"] == 4


# --- the ratio gate (the gut-check) -------------------------------------------
def test_healthy_ratio_passes():
    with tempfile.TemporaryDirectory() as d:
        env = _run(d, range(6), 6)
        assert env["success"] is True
        assert env["data"]["ratio"] >= 0.4


def test_a_window_that_FAILS_translation_is_recorded_as_a_gap_not_faked():
    def bad_caller(text, model=None, api_key=None, **k):
        return "это всё ещё русский текст без перевода. " * 30   # cyrillic echo
    with tempfile.TemporaryDirectory() as d:
        env = _run(d, [0, 2], 3, caller=bad_caller)   # missing 1
        assert env["data"]["gaps_remaining"] == 1
        assert any("1" in e["message"] for e in env["errors"])
        assert env["success"] is False


def test_missing_source_fails_cleanly():
    env = check.run(src_path="/nonexistent/x.txt", out_dir="/tmp",
                    caller=_fake_caller, out_md="/tmp/r.md")
    assert env["success"] is False
    assert env["errors"]


def test_no_out_files_means_everything_is_missing():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "agent_batches"))
        src = os.path.join(d, "src.txt")
        open(src, "w", encoding="utf-8").write(_ru(3))
        env = check.run(src_path=src, out_dir=d, caller=_fake_caller,
                        out_md=os.path.join(d, "r.md"), max_chars=_MAXC)
        assert env["data"]["missing_indices"] == [0, 1, 2]
        assert env["data"]["n_translated_now"] == 3


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
