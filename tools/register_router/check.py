"""register_router — decide whether a chat query should get the structured
Scholar layout (summary -> key quoted passage -> relevance) or the flowing Guru
voice. Deterministic, testable; replaces leaving the choice to the model.

Why this exists: the single-prompt merge gated the Scholar layout behind a few
keywords ('cite', 'source'). Genuinely complex/analytical questions that DESERVE
the structured layout silently fell back to flowing prose. This scores the query
on explicit-intent + complexity signals and, when it crosses threshold, returns a
ready-to-inject directive that forces the structured layout.

Input contract:  run(query: str) -> envelope
Output (envelope.data):
  { register: "scholar"|"guru", score: float, threshold: float,
    signals: [str], directive: str }   # directive is "" when register == guru
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List, Tuple

ENVELOPE_KEYS = {"success", "data", "metadata", "errors"}

# Crossing this total tips the query into the structured Scholar layout.
THRESHOLD = 3.0

# Explicit "I want sources/scholarship" phrases. Any hit alone forces scholar.
_EXPLICIT = [
    "cite", "citation", "reference", "sources", "source", "quote",
    "exact words", "exact verse", "what exactly does", "according to the text",
    "original sanskrit", "shloka", "sutra number", "which verse", "what verse",
]

# Analytical verbs/asks that signal a real essay-shaped question.
_ANALYTIC = [
    "compare", "contrast", "differ", "difference", "differences",
    "analyse", "analyze", "relationship between", "distinguish",
    "trace", "across the", "versus", " vs ", "reconcile", "synthesi",
]

# The directive injected when scholar wins — mirrors the UNIFIED_SYSTEM Scholar
# register so the model emits exactly: summary -> key passage(s) -> relevance.
_SCHOLAR_DIRECTIVE = (
    "## REGISTER: This question is complex/scholarly — answer in the STRUCTURED "
    "Scholar layout, not flowing prose. Use exactly these three movements:\n"
    "1. A 2-3 sentence **Summary** stating the answer directly.\n"
    "2. **The key passage(s)** — quote the most relevant retrieved verse(s) "
    "(original Sanskrit/Hindi where present + English), each with its [n] "
    "citation. Do NOT cite Guruji's own works with [n]; speak those as your own.\n"
    "3. A brief **Explanation** of how those passages answer the question — "
    "what it means for the seeker's understanding and practice.\n"
    "Keep the Guru's voice throughout; the structure serves clarity, it does not "
    "turn you into an academic."
)


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _score(query: str) -> Tuple[float, List[str]]:
    q = (query or "").lower().strip()
    signals: List[str] = []
    score = 0.0
    if not q:
        return 0.0, signals

    # 1. Explicit scholarly intent — each hit is decisive on its own.
    for kw in _EXPLICIT:
        if kw in q:
            score += 3.0
            signals.append(f"explicit:{kw}")
            break  # one explicit signal is enough; don't double-count synonyms

    # 2. Analytical framing. A comparison/analysis verb is essay-shaped by
    #    nature ("compare X with Y" wants summary->passages->synthesis), so it
    #    alone is decisive — weighted to clear THRESHOLD on its own.
    for kw in _ANALYTIC:
        if kw in q:
            score += 3.0
            signals.append(f"analytic:{kw.strip()}")
            break

    # 3. Multi-part question (more than one '?' or an ' and ' joining clauses
    #    inside a question) — a compound ask wants structure.
    qmarks = q.count("?")
    if qmarks >= 2:
        score += 1.5
        signals.append("multi:question_marks")
    elif "?" in q and re.search(r"\band\b", q):
        score += 1.0
        signals.append("multi:and_clause")

    # 4. Length/heft — long queries are usually substantive. Word count buckets.
    words = len(q.split())
    if words >= 25:
        score += 1.5
        signals.append(f"length:{words}w")
    elif words >= 16:
        score += 1.0
        signals.append(f"length:{words}w")

    # 5. Named-text mention ("in the X Purana", "the Gita", "Upanishad") nudges
    #    toward scholarship but is weak on its own.
    if re.search(r"\b(purana|upanishad|gita|veda|sutra|samhita|mahabharata|ramayana)\b", q):
        score += 0.5
        signals.append("corpus_ref")

    return score, signals


def run(query: str = "") -> Dict[str, Any]:
    if not isinstance(query, str):
        return _envelope(False, None, {"query_type": type(query).__name__},
                         [{"code": "bad_input", "message": "query must be a string"}])

    score, signals = _score(query)
    register = "scholar" if score >= THRESHOLD else "guru"
    data = {
        "register": register,
        "score": round(score, 2),
        "threshold": THRESHOLD,
        "signals": signals,
        "directive": _SCHOLAR_DIRECTIVE if register == "scholar" else "",
    }
    metadata = {"query_len": len(query), "word_count": len(query.split())}
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    query = ""
    if "--query" in argv:
        query = argv[argv.index("--query") + 1]

    env = run(query)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"register={d['register']}  score={d['score']}/{d['threshold']}")
        print(f"signals: {', '.join(d['signals']) or '(none)'}")

    if not env["success"]:
        return 2
    # Exit 1 == "finding" (scholar layout selected); 0 == default guru.
    return 1 if env["data"]["register"] == "scholar" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
