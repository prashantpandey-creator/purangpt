"""Tests for source_reality_check — Rule-0 precondition A (tests-first, real
fixtures). Run: venv/bin/python -m tools.source_reality_check.test_check (exit 0).

Fixtures are REAL captured upstream output committed beside the tool:
  fixtures/junk_html.jsonl     — first 3 chunks of the corrupt yoga_vasistha.jsonl
                                 (saved archive.org HTML page) → must be html_garbage
  fixtures/real_bhagavata.jsonl— first 3 chunks of bhagavata.jsonl (GRETIL IAST,
                                 bhp_ markers) → must be real_sanskrit
"""
from __future__ import annotations

import json
import os
import tempfile

from tools.source_reality_check import check

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIX = os.path.join(_HERE, "fixtures")


def _write(tmp: str, name: str, text: str) -> str:
    p = os.path.join(tmp, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def test_junk_html_fixture_is_garbage() -> None:
    env = check.run([os.path.join(_FIX, "junk_html.jsonl")])
    assert env["success"] is True
    row = env["data"]["files"][0]
    assert row["status"] == "html_garbage", row
    assert row["html_hits"] > 0, row
    assert row["iast"] == 0 and row["devanagari"] == 0, row
    assert row["markers"] == 0, row


def test_real_bhagavata_fixture_is_real() -> None:
    env = check.run([os.path.join(_FIX, "real_bhagavata.jsonl")])
    assert env["success"] is True
    row = env["data"]["files"][0]
    assert row["status"] == "real_sanskrit", row
    assert row["iast"] > 50, row
    assert row["markers"] > 0, row          # bhp_01.01.001 style
    assert row["html_hits"] == 0, row


def test_raw_html_string_is_garbage() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = _write(tmp, "page.txt",
                   '<!DOCTYPE html>\n<html lang="en"><head data-release=abc>'
                   '<script>window.sentry=1;</script></head><body><div class="x">'
                   'Yoga Vasistha details</div></body></html>')
        env = check.run([p])
        assert env["data"]["files"][0]["status"] == "html_garbage"


def test_raw_iast_string_with_marker_is_real() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # real Moksopaya-shaped lines (IAST + prefixed marker, danda separators)
        body = "\n".join(
            f"divi bhūmau tathākāśe bahir antaś ca me vibhuḥ / "
            f"yo 'vabhāty avabhāsātmā tasmai viśvātmane namaḥ // MU_3,{i}.15 //"
            for i in range(10, 30)
        )
        p = _write(tmp, "moksopaya.txt", body)
        env = check.run([p])
        row = env["data"]["files"][0]
        assert row["status"] == "real_sanskrit", row
        assert row["iast"] > 50 and row["markers"] > 0 and row["html_hits"] == 0


def test_entity_encoded_real_text_is_still_real() -> None:
    """Regression for the 2026-06-28 baseline finding: the real bhagavata corpus
    carries 390 `&amp;` HTML entities (the corpus is entity-encoded). Entities are
    NOISE, not garbage — a real IAST file full of them must stay real_sanskrit."""
    with tempfile.TemporaryDirectory() as tmp:
        body = "\n".join(
            f"dharmaḥ projjhitakaitavo 'tra paramo nirmatsarāṇāṃ satāṃ &amp; "
            f"vedyaṃ &#7779;ivadaṃ tāpatrayonmūlanam // bhp_01.{i:02d}.001 //"
            for i in range(1, 40)
        )
        p = _write(tmp, "entity.jsonl",
                   "\n".join(json.dumps({"text": ln}, ensure_ascii=False)
                             for ln in body.splitlines()))
        row = check.run([p])["data"]["files"][0]
        assert row["status"] == "real_sanskrit", row
        assert row["markers"] > 0 and row["iast"] > 50, row


def test_marker_grammar_matches_both_forms() -> None:
    assert check._MARKER_RE.findall("foo // MU_1,26.13 // bar") == ["MU_1,26.13"]
    assert check._MARKER_RE.findall("x bhp_01.01.001 y") == ["bhp_01.01.001"]
    assert check._MARKER_RE.findall("verse 1.1.1 end") == ["1.1.1"]
    # bare 2-component (1.1) is NOT a verse marker for our purposes (too noisy)
    assert check._MARKER_RE.findall("see 1.1 only") == []


def test_full_file_scan_defeats_head_sample_scope_trap() -> None:
    """The decisive guard: a real file whose FIRST chunks carry no surviving
    marker (short markers dropped by the chunker) but whose later chunks do —
    must still classify real_sanskrit. A head-only sampler would miss this."""
    with tempfile.TemporaryDirectory() as tmp:
        head = [json.dumps({"text": "śrīrāma uvāca bhagavan munivara śṛṇu me "
                                     "vacanaṃ paramaṃ śubham"}, ensure_ascii=False)
                for _ in range(40)]                      # IAST, NO markers
        tail = [json.dumps({"text": f"tattvajñānaṃ paraṃ guhyaṃ // MU_6,{i}.20 //"},
                           ensure_ascii=False)
                for i in range(120, 160)]                # IAST + markers
        p = os.path.join(tmp, "big.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(head + tail) + "\n")
        row = check.run([p])["data"]["files"][0]
        assert row["status"] == "real_sanskrit", row
        assert row["markers"] > 0, row


def test_missing_file_is_a_row_not_a_run_failure() -> None:
    env = check.run([os.path.join(_FIX, "does_not_exist.jsonl")])
    assert env["success"] is True
    assert env["data"]["files"][0]["status"] == "missing"
    assert env["data"]["n_other"] == 1


def test_empty_file_list_is_misuse() -> None:
    env = check.run([])
    assert env["success"] is False
    assert env["errors"][0]["code"] == "no_files"
    assert env["data"] is None


def test_empty_content_is_empty_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = _write(tmp, "blank.txt", "")
        assert check.run([p])["data"]["files"][0]["status"] == "empty"


def test_envelope_and_output_schema_shape() -> None:
    env = check.run([os.path.join(_FIX, "real_bhagavata.jsonl")])
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    for k in ("files", "real_sanskrit", "html_garbage", "suspect", "other",
              "n_files", "n_real", "n_garbage", "n_suspect", "n_other"):
        assert k in env["data"], k
    row = env["data"]["files"][0]
    for k in ("file", "status", "chars", "iast", "devanagari", "markers",
              "html_hits", "sample_markers"):
        assert k in row, k


def _run_all() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa
            failed += 1
            print(f"  ERR  {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(_run_all())
