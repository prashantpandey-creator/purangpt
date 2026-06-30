#!/usr/bin/env python3
"""
AI merge-conflict resolver — the "merge bot".

Reads files that contain git conflict markers and asks Google Gemini (free tier)
to produce a clean resolution that preserves the intent of BOTH sides. Used by
the deploy workflow's auto-merge step so a drifted `claude/**` branch heals
itself instead of silently blocking its own deploy.

WHY IT EXISTS
  The Hetzner deploy Action auto-merges each `claude/**` push into `main` before
  deploying. If the branch has drifted, `git merge` conflicts, the step fails,
  and the deploy is silently skipped. This script lets that step resolve the
  conflict automatically with an LLM.

CONTRACT
  Usage:  ai-merge-resolve.py <file1> [<file2> ...]
  Env:    GEMINI_API_KEY (or GOOGLE_API_KEY / GOOGLE_GEMINI_API_KEY / GENAI_API_KEY)
          GEMINI_MODEL (optional, default "gemini-2.0-flash")
  Exit:   0  -> every file resolved, zero conflict markers remain
          1  -> at least one file could NOT be resolved (caller should abort +
                open an issue for a human). Nothing is half-written: a file is
                only overwritten when its resolution is marker-free.

  Pure standard library (urllib) — no pip install on the runner.

PRIVACY NOTE
  File contents are sent to Google's Gemini API. These repos are private; the
  free tier may use submitted data to improve Google products. Use a paid key
  (or a self-hosted model) if that is unacceptable.
"""
import os
import re
import sys
import json
import urllib.request

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
MARKER_RE = re.compile(r"^(<<<<<<<|=======|>>>>>>>)", re.M)

PROMPT = """You are a senior engineer resolving a git merge conflict.

The file below contains git conflict markers (<<<<<<<, =======, >>>>>>>).
Return the COMPLETE resolved file with EVERY conflict marker removed.

Rules:
- Integrate the intent of BOTH sides. Do not drop functionality from either side.
- Keep the file syntactically valid for its language.
- Change nothing outside the conflicted regions.
- Output ONLY the raw file contents. No explanations, no markdown code fences.

FILE PATH: {path}
======== FILE WITH CONFLICTS ========
{content}
"""


def api_key() -> str:
    for name in (
        "GEMINI_API_KEY",
        "GOOGLE_GEMINI_API_KEY",
        "GENAI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        val = os.environ.get(name)
        if val:
            return val
    return ""


def call_gemini(prompt: str) -> str | None:
    key = api_key()
    if not key:
        print("  ERROR: no Gemini API key in env", file=sys.stderr)
        return None
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent?key={key}"
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 8192},
        }
    ).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:  # noqa: BLE001 — surface any failure, keep the bot resilient
        print(f"  ERROR: Gemini request failed: {exc}", file=sys.stderr)
        return None


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9._-]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print("no conflicted files passed; nothing to do")
        return 0

    all_ok = True
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            print(f"  ERROR: cannot read {path}: {exc}", file=sys.stderr)
            all_ok = False
            continue

        if not MARKER_RE.search(content):
            print(f"  {path}: no markers, skipping")
            continue

        print(f"resolving {path} via {MODEL} ...")
        out = call_gemini(PROMPT.format(path=path, content=content))
        if not out:
            print(f"  FAILED: no AI output for {path}", file=sys.stderr)
            all_ok = False
            continue

        out = strip_code_fences(out)
        if MARKER_RE.search(out):
            print(f"  FAILED: conflict markers remain in AI output for {path}", file=sys.stderr)
            all_ok = False
            continue

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(out if out.endswith("\n") else out + "\n")
        print(f"  OK: resolved {path}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
