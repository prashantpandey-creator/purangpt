"""inhouse — the in-house decode caller: CLAUDE is the LLM, not Gemini/DeepSeek.

daddy's directive: comprehend the corpus with our own compute (a Workflow fan-out of
Claude subagents) so the pipeline never hits the Gemini free-tier 429 again, and the
moat stops renting Google's quota.

This plugs into comprehend.py's existing provider registry as the "inhouse" caller.
comprehend_window(...) already takes an injectable caller; run.py's resumable loop is
unchanged. The only new idea is a per-chapter response CACHE on disk:

  1. DUMP   : something builds each chapter's prompt (comprehend.build_prompt) and lists
              the pending ones (pending_prompts).
  2. DECODE : a Workflow fans out subagents; each writes its chapter JSON via
              write_response(cache, prompt, json).
  3. FOLD   : run.py runs with provider="inhouse"; make_inhouse_caller(cache) resolves
              every call from disk instantly, and the normal parse/validate/salvage +
              record-writing path runs untouched.

Cache key = a hash of the exact prompt, so the same chapter always maps to the same
file (resume-safe, idempotent). Pure file/hash logic — fixture-tested, no network.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Union

# default cache dir (gitignored, lives beside the other out/ artifacts)
DEFAULT_CACHE = "tools/read_pass/out/inhouse_cache"


class InhouseResponseMissing(Exception):
    """Raised by the caller when a chapter's decoded JSON isn't in the cache yet.
    Carries the prompt_key so the orchestrator knows exactly what still needs decoding.
    comprehend_window catches this as a normal call failure (false envelope), so a
    half-filled cache degrades gracefully instead of crashing the run."""


def prompt_key(prompt: str) -> str:
    """Stable hex key for a prompt — the cache filename stem for that chapter's answer."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32]


def _path(cache_dir: str, prompt: str) -> str:
    return os.path.join(cache_dir, f"{prompt_key(prompt)}.json")


def write_response(cache_dir: str, prompt: str,
                   response: Union[str, Dict[str, Any]]) -> str:
    """Persist a chapter's decoded JSON, keyed by its prompt. `response` may be a dict
    or an already-serialized JSON string. Returns the path written."""
    os.makedirs(cache_dir, exist_ok=True)
    if isinstance(response, str):
        text = response
    else:
        text = json.dumps(response, ensure_ascii=False)
    path = _path(cache_dir, prompt)
    with open(path, "w") as f:
        f.write(text)
    return path


def make_inhouse_caller(cache_dir: str = DEFAULT_CACHE) -> Callable[..., str]:
    """Return a caller(prompt, model, api_key, ...) compatible with comprehend._CALLERS.
    Cache hit -> the stored JSON string; miss -> InhouseResponseMissing(key)."""
    def _call_inhouse(prompt: str, model: str = "", api_key: str = "",
                      timeout: int = 0) -> str:
        path = _path(cache_dir, prompt)
        if not os.path.exists(path):
            raise InhouseResponseMissing(
                f"no cached decode for prompt_key={prompt_key(prompt)} "
                f"(decode it and write_response into {cache_dir})")
        with open(path) as f:
            return f.read()
    return _call_inhouse


def pending_prompts(cache_dir: str, prompts: List[str]) -> List[str]:
    """Of these prompts, which have NO cached response yet — the decode work remaining."""
    return [p for p in prompts if not os.path.exists(_path(cache_dir, p))]


def build_chapter_prompt(window: Dict[str, Any], lens: List[Dict[str, Any]]) -> str:
    """Rebuild the EXACT prompt comprehend_window(provider='inhouse') will hash on.

    This MUST stay byte-identical to comprehend_window's prompt assembly for the
    inhouse path, or the cache key won't match on the fold pass. It mirrors:
      build_prompt(window, select_lens(...)) + the inhouse schema suffix.
    Kept here (not importing comprehend at module load) to avoid a circular import;
    comprehend imports inhouse, so we import comprehend lazily inside the function.
    """
    from tools.read_pass import comprehend, schema  # lazy: breaks the import cycle
    lens_text = comprehend.select_lens(window, lens)
    prompt = comprehend.build_prompt(window, lens_text)
    prompt = prompt + "\n\nReturn ONLY valid JSON matching this schema:\n" + json.dumps(
        schema.RESPONSE_SCHEMA, indent=1)
    return prompt


def dump_prompts(input_path: str, cache_dir: str = DEFAULT_CACHE) -> Dict[str, Any]:
    """For one chunk file: group → windows → build each chapter's prompt → list the
    ones not yet cached. Returns a manifest the decode Workflow consumes:
      {input, total, pending: [{chunk_id, chapter_label, prompt_key, prompt}, ...]}
    No LLM, no writes to the cache — pure read/plan."""
    from tools.read_pass import comprehend, group  # lazy
    g = group.run(input_path)
    if not g.get("success"):
        return {"input": input_path, "total": 0, "pending": [], "errors": g.get("errors", [])}
    lens = comprehend.load_lens()
    windows = g["data"]["windows"]
    pending = []
    for w in windows:
        prompt = build_chapter_prompt(w, lens)
        if os.path.exists(_path(cache_dir, prompt)):
            continue
        cids = w.get("chunk_ids", [])
        pending.append({
            "chunk_id": cids[0] if cids else None,
            "chapter_label": w.get("chapter_label"),
            "purana": w.get("purana"),
            "prompt_key": prompt_key(prompt),
            "prompt": prompt,
        })
    return {"input": input_path, "total": len(windows),
            "pending": pending, "errors": []}
