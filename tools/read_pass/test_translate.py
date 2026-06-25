"""Tests-first for the RU→EN translation tool (Rule 0 precond A).

Daddy: "translate the works with a good model and keep them as official English
reference." Publication-grade RU→EN of Sharma's Russian works (Mossin biography,
Gita RU). Chosen model: gemini-2.5-flash (excellent translation, huge context,
cheap, billed separately from DeepSeek). Produces clean English markdown saved
under tools/read_pass/translations/ as the official reference.

Run: venv/bin/python -m tools.read_pass.test_translate   (exit 0)
"""
from __future__ import annotations
import json
import os
import tempfile

from tools.read_pass import translate


def test_windows_preserve_order_and_coverage():
    text = "\n\n".join(f"Абзац номер {i}." for i in range(80))
    windows = translate.make_windows(text, max_chars=600)
    assert len(windows) >= 2
    # order preserved + full coverage
    joined = "\n\n".join(windows)
    assert joined.index("Абзац номер 0.") < joined.index("Абзац номер 79.")
    assert "Абзац номер 40." in joined


def test_validate_detects_russian_echo():
    # output that's still mostly Cyrillic = the model echoed instead of translating
    ru_in = "Шарма был великим йогом, и его душа была чиста как родник."
    bad_out = "Шарма был великим йогом, и его душа была чиста."  # echoed RU
    ok, reason = translate.validate_translation(ru_in, bad_out)
    assert not ok
    assert "cyrillic" in reason.lower() or "echo" in reason.lower()


def test_validate_detects_truncation():
    # English but way too short vs input = truncated
    ru_in = "A" * 4000  # large input (stand-in)
    short_out = "He was a yogi."  # tiny output
    ok, reason = translate.validate_translation(ru_in, short_out)
    assert not ok
    assert "short" in reason.lower() or "truncat" in reason.lower()


def test_validate_accepts_good_translation():
    ru_in = "Шарма был великим йогом." * 20
    good_out = "Sharma was a great yogi, devoted to his practice and lineage." * 18
    ok, reason = translate.validate_translation(ru_in, good_out)
    assert ok, reason


def test_translate_window_retries_on_bad_output():
    calls = {"n": 0}
    def flaky(text, model, key):
        calls["n"] += 1
        if calls["n"] == 1:
            return "Шарма был йогом."  # first attempt echoes RU
        return "Sharma was a yogi devoted to the path of Kriya and his lineage forever."
    out = translate.translate_window_verified(
        "Шарма был великим йогом и преданным практиком." * 5,
        "key", model="m", caller=flaky, max_retries=2)
    assert calls["n"] == 2  # retried once
    assert "Sharma" in out


def test_translate_window_calls_model_and_returns_english():
    def fake(text, model, key):
        return "[EN] " + text[:20]
    out = translate.translate_window("Привет мир", "fake-key",
                                     model="gemini-2.5-flash", caller=fake)
    assert out.startswith("[EN]")


def test_openai_caller_accepts_window_positional_args():
    # REGRESSION: a partial that bound model= collided with translate_window's
    # positional fn(text, model, api_key) → "multiple values for 'model'", which
    # gapped all 30 DeepSeek windows. The caller must have the (text, model,
    # api_key) signature so translate_window can drive it like any other caller.
    seen = {}
    def fake_http(url, headers, body):
        seen["url"] = url; seen["model"] = body["model"]
        return {"choices": [{"message": {"content": "Translated English text here, fully rendered."}}]}
    caller = translate.make_openai_caller(base_url="https://api.deepseek.com/v1",
                                          http=fake_http)
    # drive it exactly how translate_window does: positional (text, model, key)
    out = caller("Привет", "deepseek-chat", "sk-key")
    assert out.startswith("Translated")
    assert seen["model"] == "deepseek-chat"          # model flows from caller arg
    assert "deepseek.com" in seen["url"]             # base_url override honored


def test_openai_caller_works_through_translate_window_verified():
    # End-to-end: the factory caller must survive the full verified path without
    # the argument collision that produced [[GAP]] markers.
    def fake_http(url, headers, body):
        # echo a proportional English body so validate_translation passes
        ru = body["messages"][0]["content"]
        return {"choices": [{"message": {"content": "word " * max(len(ru)//3, 20)}}]}
    caller = translate.make_openai_caller(base_url="https://api.deepseek.com/v1",
                                          http=fake_http)
    out = translate.translate_window_verified(
        "Шарма был великим йогом и преданным практиком садханы." * 6,
        "sk-key", model="deepseek-chat", caller=caller, max_retries=1)
    assert "word" in out


def test_assemble_preserves_window_order():
    # windows must reassemble in the SAME order they were split (no race scramble)
    translated = {2: "third", 0: "first", 1: "second"}
    out = translate.assemble(translated, n_windows=3)
    assert out == "first\n\nsecond\n\nthird"


def test_run_writes_english_file_and_envelope():
    calls = []
    def fake(text, model, key):
        calls.append(text)
        # proportional Latin output so it passes validate_translation
        return "EN translation of: " + " ".join("word" for _ in text.split())
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "mossin.txt")
        open(src, "w", encoding="utf-8").write("Альфа текст\n\nБета текст\n\nГамма текст")
        out_path = os.path.join(d, "mossin_en.md")
        env = translate.run(src, "fake-key", out_path=out_path,
                            max_chars=20, caller=fake)
        # assert INSIDE the block — out_path lives in the temp dir
        assert env["success"]
        assert set(env.keys()) == {"success", "data", "metadata", "errors"}
        assert os.path.exists(out_path)
        body = open(out_path, encoding="utf-8").read()
        assert "EN translation" in body
        assert env["data"]["n_windows"] >= 1


def test_failed_window_recorded_not_lost():
    def flaky(text, model, key):
        if "Бета" in text:
            raise RuntimeError("simulated API error")
        return "EN translation of: " + " ".join("word" for _ in text.split())
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "x.txt")
        open(src, "w", encoding="utf-8").write("Альфа\n\nБета\n\nГамма")
        env = translate.run(src, "k", out_path=os.path.join(d, "o.md"),
                            max_chars=8, caller=flaky)
    # a failed window → success False, error recorded, but other windows still written
    assert not env["success"]
    assert any("simulated" in e["message"] for e in env["errors"])


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
