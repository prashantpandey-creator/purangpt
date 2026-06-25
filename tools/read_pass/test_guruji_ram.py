"""Tests-first for the Guruji RAM builder (Rule 0 precond A).

Daddy's correction: I built the identity model on ONE grepped paragraph of
Sharma. This tool reads the ENTIRE Sharma corpus (Yogeshwari Gita 79K words +
Shiv Sutra + Yoga Alchemy + Gorakh Bodh + Khechari Vidya + Ojas-Amrita) and
distills his COMPLETE decryption framework into a structured reference object —
the "Guruji RAM" the whole pipeline sits on.

The RAM is NOT a summary. It is a structured worldview:
  - decryption_keys: symbol → yogic meaning (Kurukshetra→body, Krishna→Kutastha)
  - core_principles: the load-bearing metaphysical claims (One appears as many)
  - identity_doctrine: how Sharma treats names/forms/the One-and-many
  - cosmology: his time/creation model
  - practice_axes: the inner-yoga dimensions he reads everything through

The builder loads the raw corpus, windows it, and uses the reasoning model to
extract the framework. Tier-3 work (genuine judgment over unstructured prose) —
the legitimate sub-agent/reasoner case, not a decision tree.

Run: venv/bin/python -m tools.read_pass.test_guruji_ram   (exit 0)
"""
from __future__ import annotations
import json
import os
import tempfile

from tools.read_pass import guruji_ram


def test_load_corpus_reads_all_sources():
    # Make two fake source files, confirm both are loaded + labeled
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "shiv_sutra.txt"), "w").write(
            "Sutra 1. Translation — Consciousness is soul.\n"
            "Exposition — The mind manifested by body is soul.")
        open(os.path.join(d, "yoga_alchemy.txt"), "w").write(
            "PRANA IS MERCURY. Guruji: prana is mercury, apana is sulfur.")
        sources = guruji_ram.load_corpus(d)
        assert len(sources) == 2
        names = {s["source"] for s in sources}
        assert any("shiv_sutra" in n for n in names)
        assert all("text" in s and len(s["text"]) > 0 for s in sources)


def test_windows_cover_whole_text():
    # A long text must be split into windows that together cover everything
    text = "\n\n".join(f"Paragraph {i} with some content here." for i in range(200))
    windows = guruji_ram.make_windows(text, max_chars=1000)
    assert len(windows) >= 2
    # union of windows covers all paragraphs (no silent drop)
    joined = " ".join(windows)
    assert "Paragraph 0 " in joined
    assert "Paragraph 199 " in joined


def test_merge_frameworks_unions_keys():
    # Two partial frameworks from different windows merge into one
    f1 = {
        "decryption_keys": [{"symbol": "Kurukshetra", "meaning": "the body"}],
        "core_principles": ["The One appears as many"],
        "identity_doctrine": "Names are aspects of one Self.",
        "cosmology": "",
        "practice_axes": ["pranayama"],
    }
    f2 = {
        "decryption_keys": [{"symbol": "Krishna", "meaning": "Kutastha Chaitanya"}],
        "core_principles": ["Surrender dissolves the ego"],
        "identity_doctrine": "",
        "cosmology": "Time is standstill but appears divided.",
        "practice_axes": ["pranayama", "samadhi"],
    }
    merged = guruji_ram.merge_frameworks([f1, f2])
    symbols = {k["symbol"] for k in merged["decryption_keys"]}
    assert "Kurukshetra" in symbols and "Krishna" in symbols
    assert len(merged["core_principles"]) == 2
    assert "pranayama" in merged["practice_axes"] and "samadhi" in merged["practice_axes"]
    # identity_doctrine: non-empty wins
    assert merged["identity_doctrine"]
    assert merged["cosmology"]


def test_extract_framework_uses_reasoner():
    def fake_reasoner(prompt, model, key):
        return json.dumps({
            "decryption_keys": [{"symbol": "Arjuna", "meaning": "the aspirant's mind"}],
            "core_principles": ["The body is the field of yoga"],
            "identity_doctrine": "The One Self wears many names.",
            "cosmology": "Creation evolves gross to subtle.",
            "practice_axes": ["kundalini"],
        })
    fw = guruji_ram.extract_framework("some Sharma text", "fake-key",
                                      caller=fake_reasoner)
    assert fw["decryption_keys"][0]["symbol"] == "Arjuna"


def test_envelope_shape():
    def fake_reasoner(prompt, model, key):
        return json.dumps({
            "decryption_keys": [{"symbol": "X", "meaning": "Y"}],
            "core_principles": ["P"], "identity_doctrine": "D",
            "cosmology": "C", "practice_axes": ["A"],
        })
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "shiv_sutra.txt"), "w").write("Sutra 1. short text.")
        env = guruji_ram.run(d, "fake-key", caller=fake_reasoner)
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"]
    assert "framework" in env["data"]
    assert "decryption_keys" in env["data"]["framework"]


def test_load_returns_built_framework():
    # load() reads the saved RAM json — the LIVE accessor other stages use.
    with tempfile.TemporaryDirectory() as d:
        ram_path = os.path.join(d, "guruji_ram.json")
        json.dump({"success": True, "data": {"framework": {
            "decryption_keys": [{"symbol": "Krishna", "meaning": "Kutastha"}],
            "core_principles": ["One appears as many"],
            "identity_doctrine": "Manifest vs ground.",
            "cosmology": "Time.", "practice_axes": ["samadhi"]}}},
            open(ram_path, "w"))
        fw = guruji_ram.load(ram_path)
    assert fw["identity_doctrine"] == "Manifest vs ground."
    assert fw["decryption_keys"][0]["symbol"] == "Krishna"


def test_load_missing_returns_empty_not_crash():
    fw = guruji_ram.load("/nonexistent/ram.json")
    assert fw == guruji_ram._empty_framework()


def test_keys_for_text_matches_relevant_symbols():
    # given a chapter text, return only the RAM keys whose symbol appears in it
    fw = {"decryption_keys": [
        {"symbol": "Kurukshetra", "meaning": "the body"},
        {"symbol": "Krishna", "meaning": "Kutastha"},
        {"symbol": "Ganga", "meaning": "the sushumna"},
    ], "core_principles": [], "identity_doctrine": "", "cosmology": "", "practice_axes": []}
    text = "On the field of Kurukshetra, Krishna spoke to Arjuna."
    keys = guruji_ram.keys_for_text(text, fw)
    syms = {k["symbol"] for k in keys}
    assert "Kurukshetra" in syms and "Krishna" in syms
    assert "Ganga" not in syms  # not mentioned


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
