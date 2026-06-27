"""Tests-first for inhouse — the in-house decode caller (Rule 0 precond A).

daddy's design: the LLM that comprehends each chapter is CLAUDE ITSELF (a Workflow
fan-out of subagents), not Gemini/DeepSeek. So we never hit the Gemini free-tier wall
again, and the moat stops depending on Google's quota.

Mechanism (keeps comprehend_window + run.py's resumable loop 100% unchanged):
  - `prompt_key(prompt)` -> a stable hash; the cache filename for that chapter's answer.
  - A Workflow decodes each chapter and writes its JSON to <cache>/<key>.json.
  - `make_inhouse_caller(cache)` returns a caller(prompt,model,key) that reads that file.
    Cache hit  -> returns the JSON string (comprehend_window parses it as usual).
    Cache miss -> raises InhouseResponseMissing(key) so the orchestrator knows what's left.

Deterministic file/hash logic — no LLM, no network in the caller itself. So it gets tests.
Run: venv/bin/python -m tools.read_pass.test_inhouse   (exit 0)
"""
from __future__ import annotations

import json
import os
import tempfile

from tools.read_pass import inhouse


def test_prompt_key_is_stable_and_hex():
    k1 = inhouse.prompt_key("read this chapter")
    k2 = inhouse.prompt_key("read this chapter")
    assert k1 == k2, "same prompt must hash to the same key (resume depends on it)"
    assert all(c in "0123456789abcdef" for c in k1)
    assert len(k1) >= 16


def test_prompt_key_differs_for_different_prompts():
    assert inhouse.prompt_key("chapter A") != inhouse.prompt_key("chapter B")


def test_cache_hit_returns_stored_json_string():
    with tempfile.TemporaryDirectory() as d:
        prompt = "comprehend the Gita chapter 1"
        payload = {"chapter_summary": "x", "entities": [], "relationships": [],
                   "story": {"title": "t", "arc": "a"}, "teachings": []}
        inhouse.write_response(d, prompt, payload)
        caller = inhouse.make_inhouse_caller(d)
        raw = caller(prompt, "claude", "no-key")
        assert json.loads(raw)["chapter_summary"] == "x"


def test_cache_miss_raises_response_missing_with_the_key():
    with tempfile.TemporaryDirectory() as d:
        caller = inhouse.make_inhouse_caller(d)
        try:
            caller("an undecoded chapter", "claude", "no-key")
            assert False, "miss must raise"
        except inhouse.InhouseResponseMissing as e:
            assert inhouse.prompt_key("an undecoded chapter") in str(e)


def test_write_response_accepts_dict_or_json_string():
    with tempfile.TemporaryDirectory() as d:
        inhouse.write_response(d, "p1", {"a": 1})
        inhouse.write_response(d, "p2", '{"a": 2}')  # already-serialized JSON string
        caller = inhouse.make_inhouse_caller(d)
        assert json.loads(caller("p1", "", ""))["a"] == 1
        assert json.loads(caller("p2", "", ""))["a"] == 2


def test_pending_prompts_lists_only_uncached():
    with tempfile.TemporaryDirectory() as d:
        prompts = ["p1", "p2", "p3"]
        inhouse.write_response(d, "p2", {"ok": True})  # only p2 cached
        pend = inhouse.pending_prompts(d, prompts)
        assert pend == ["p1", "p3"], pend


def test_resolve_provider_picks_inhouse_when_env_set(monkeypatch_env=None):
    # INHOUSE_DECODE=1 must select the in-house provider over deepseek/gemini keys.
    old = dict(os.environ)
    try:
        os.environ["INHOUSE_DECODE"] = "1"
        os.environ["DEEPSEEK_API_KEY"] = "should-be-ignored"
        from tools.read_pass import comprehend
        provider, key, model = comprehend.resolve_provider()
        assert provider == "inhouse", f"got {provider}"
    finally:
        os.environ.clear()
        os.environ.update(old)


def test_inhouse_caller_registered_in_callers():
    from tools.read_pass import comprehend
    assert "inhouse" in comprehend._CALLERS, "inhouse must be a registered provider caller"


def test_dump_prompt_key_matches_comprehend_window_key():
    # THE LOAD-BEARING INVARIANT: the prompt dump_prompts hashes must be byte-identical
    # to the prompt comprehend_window(provider='inhouse') hashes — else the fold pass
    # rebuilds a different key and every cached answer misses. Prove the keys match by
    # routing a real window through comprehend_window with the inhouse caller and a
    # cache pre-filled under dump_prompts' key.
    from tools.read_pass import comprehend
    window = {"purana": "Test", "chapter_label": "Chapter 1", "seq_start": 1,
              "seq_end": 2, "chunk_ids": ["test-1-1"], "text": "bhp_01.01.001 hello"}
    lens = []
    good = {"chapter_summary": "s", "entities": [], "relationships": [],
            "story": {"title": "t", "arc": "a"}, "teachings": []}
    with tempfile.TemporaryDirectory() as d:
        prompt = inhouse.build_chapter_prompt(window, lens)
        inhouse.write_response(d, prompt, good)
        # comprehend_window will rebuild the prompt internally and call _CALLERS['inhouse'];
        # point that caller at our temp cache by swapping it in for the test.
        old = comprehend._CALLERS["inhouse"]
        comprehend._CALLERS["inhouse"] = inhouse.make_inhouse_caller(d)
        try:
            env = comprehend.comprehend_window(window, lens, "inhouse",
                                               model="claude", provider="inhouse")
        finally:
            comprehend._CALLERS["inhouse"] = old
        assert env["success"] is True, env["errors"]
        assert env["data"]["_provenance"]["provider"] == "inhouse"
        assert env["data"]["chapter_summary"] == "s"


def test_fold_pass_runs_inhouse_without_a_key():
    """THE FOLD-PATH GAP (found by the BORI smoke 2026-06-26): run.run with
    provider='inhouse' must NOT require an LLM key — the cache IS the LLM. Before
    the fix, run.py:96 `if not api_key` bailed with code 'no_key' for inhouse, so a
    fully-decoded cache could never be folded into the graph. Pin: a real window
    with a cached decode folds end-to-end, verify-gated, with api_key=''."""
    from tools.read_pass import comprehend
    from tools.read_pass import run as RUN

    # a window whose source text literally contains the marker its node will cite,
    # so the verify-gate KEEPS the node (proves the gate runs and passes on the path)
    window = {"purana": "Test", "chapter_label": "Chapter 1", "seq_start": 1,
              "seq_end": 2, "chunk_ids": ["test-1-1"],
              "text": "mbh_01.001.005 Bhishma vowed celibacy."}
    grounded = {"chapter_summary": "s",
                "entities": [{"name": "Bhishma", "kind": "king",
                              "verse_ranges": ["mbh_01.001.005"]}],
                "relationships": [], "story": {"title": "t", "arc": "a"},
                "teachings": []}

    with tempfile.TemporaryDirectory() as d:
        prompt = inhouse.build_chapter_prompt(window, [])
        inhouse.write_response(d, prompt, grounded)
        old = comprehend._CALLERS["inhouse"]
        comprehend._CALLERS["inhouse"] = inhouse.make_inhouse_caller(d)
        # group.run reads from disk; stub it to yield exactly our one window so the
        # test is hermetic (no dependency on a real chunk file shipping).
        import tools.read_pass.group as group_mod
        old_group = group_mod.run
        group_mod.run = lambda _p, **_kw: {"success": True,
                                           "data": {"windows": [window]},
                                           "metadata": {}, "errors": []}
        try:
            env = RUN.run("ignored.jsonl", "test_inhouse_fold", api_key="",
                          provider="inhouse", model="claude", limit=1)
        finally:
            comprehend._CALLERS["inhouse"] = old
            group_mod.run = old_group
            # clean the per-test output the run appended
            for suf in (".records.jsonl", ".progress.jsonl"):
                p = os.path.join(RUN.OUT_DIR, "test_inhouse_fold" + suf)
                if os.path.exists(p):
                    os.remove(p)

        assert env["success"] is True, env["errors"]
        # the key gate must NOT have fired
        assert not any(e.get("code") == "no_key" for e in env["errors"]), env["errors"]
        d2 = env["data"]
        assert d2["comprehended"] == 1, d2
        # the grounded node survived the gate (cite is in the window)
        assert d2["nodes_kept"] == 1, d2
        assert d2["nodes_dropped"] == 0, d2
        assert d2["grounded_rate"] == 1.0, d2


def test_fold_pass_inhouse_gate_prunes_ungrounded():
    """Companion: on the inhouse fold path, a node whose cite is NOT in the window
    is pruned by the gate (the whole point — the cache can still narrate)."""
    from tools.read_pass import comprehend
    from tools.read_pass import run as RUN

    window = {"purana": "Test", "chapter_label": "Chapter 1", "seq_start": 1,
              "seq_end": 2, "chunk_ids": ["test-1-1"],
              "text": "mbh_01.001.005 only this marker is real here."}
    # node cites mbh_09.099.099 which is NOT in the window → must be pruned → husk
    narrated = {"chapter_summary": "s",
                "entities": [{"name": "Phantom", "kind": "concept",
                              "verse_ranges": ["mbh_09.099.099"]}],
                "relationships": [], "story": {"title": "t", "arc": "a"},
                "teachings": []}

    with tempfile.TemporaryDirectory() as d:
        prompt = inhouse.build_chapter_prompt(window, [])
        inhouse.write_response(d, prompt, narrated)
        old = comprehend._CALLERS["inhouse"]
        comprehend._CALLERS["inhouse"] = inhouse.make_inhouse_caller(d)
        import tools.read_pass.group as group_mod
        old_group = group_mod.run
        group_mod.run = lambda _p, **_kw: {"success": True,
                                           "data": {"windows": [window]},
                                           "metadata": {}, "errors": []}
        try:
            env = RUN.run("ignored.jsonl", "test_inhouse_husk", api_key="",
                          provider="inhouse", model="claude", limit=1)
        finally:
            comprehend._CALLERS["inhouse"] = old
            group_mod.run = old_group
            for suf in (".records.jsonl", ".progress.jsonl"):
                p = os.path.join(RUN.OUT_DIR, "test_inhouse_husk" + suf)
                if os.path.exists(p):
                    os.remove(p)

        assert env["success"] is True, env["errors"]
        d2 = env["data"]
        assert d2["nodes_kept"] == 0, d2
        assert d2["nodes_dropped"] == 1, d2
        assert d2["husked"] == 1, d2  # pruned to nothing → not written


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
