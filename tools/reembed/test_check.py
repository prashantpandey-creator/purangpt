"""Tests for tools.reembed — the pure normalize core (no model, no IO).

Run: venv/bin/python -m tools.reembed.test_check   (from purangpt/ root)

Only the deterministic normalize step is tested here. embed/import steps
require a model or a live DB — those are exercised by running the pipeline
against the full corpus.
"""
import re
from tools.reembed.normalize import (
    normalize_row, detect_script, clean, is_guruji, GURUJI_CATEGORIES,
)


def test_iast_scripture_transliterates():
    result = normalize_row("janmādyasya yataḥ anvayāt", "scripture", "bhp_1.1.1")
    assert result["script"] == "iast2deva"
    assert result["changed"] is True
    assert re.search(r"[ऀ-ॿ]", result["embed_text"]), "Expected Devanagari in output"


def test_devanagari_passthrough():
    result = normalize_row("जगत् मिथ्या ब्रह्म सत्यम्", "scripture", "yv_1.1")
    assert result["script"] == "devanagari"
    assert result["changed"] is False
    assert "जगत्" in result["embed_text"]


def test_commentary_passthrough():
    result = normalize_row("The nature of consciousness is pure awareness", "yogic-commentary", "x")
    assert result["script"] == "commentary"
    assert result["changed"] is False
    assert "consciousness" in result["embed_text"]


def test_all_guruji_categories_pass_through():
    for cat in GURUJI_CATEGORIES:
        r = normalize_row("janmādyasya yataḥ", cat, "x")
        assert r["script"] == "commentary", f"Category {cat!r} was not treated as commentary"
        assert r["changed"] is False


def test_darshan_id_passthrough():
    result = normalize_row("janmādyasya yataḥ", "scripture", "darshan-001")
    assert result["script"] == "commentary"
    assert result["changed"] is False


def test_chunk_markers_stripped():
    result = normalize_row("text BHP_1,2.3 more content", "scripture", "x")
    assert "BHP_1" not in result["embed_text"]


def test_dandas_stripped():
    result = normalize_row("राम ।। sita ॥ text", "scripture", "x")
    assert "।" not in result["embed_text"]
    assert "॥" not in result["embed_text"]


def test_detect_script():
    assert detect_script("janmādyasya yataḥ anvayāt") == "iast"
    assert detect_script("जगत् मिथ्या ब्रह्म") == "devanagari"
    assert detect_script("The nature of consciousness") == "latin"


def test_is_guruji():
    assert is_guruji("yogic-commentary", "x") is True
    assert is_guruji("yogic-discourse", "x") is True
    assert is_guruji("scripture", "darshan-001") is True
    assert is_guruji("scripture", "bhp_1.1.1") is False


def test_empty_content_graceful():
    result = normalize_row("", "scripture", "x")
    assert isinstance(result["embed_text"], str)
    assert isinstance(result["changed"], bool)


def test_clean_truncates_at_512():
    assert len(clean("a" * 600)) <= 512


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0)
