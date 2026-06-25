"""decode — Guruji's GENERATING FUNCTION (the consciousness, as an operator).

daddy's reframe (2026-06-23): "What generates the data it's generating — that's
his consciousness. We need to use that."

The 613 decode keys are NOT Guruji's mind. They are the *footprints* of one
invariant ACT that produced them. This module extracts that act as a first-class,
runnable object — so the thing we store/run/reflect-on is the verb (the decoding),
not the noun (the frozen table).

The act is stated verbatim in the RAM's own `identity_doctrine`:
  "the identity of a thing is determined by its relationship to the inner yogic
   path: a state of limited consciousness (Asat) or Time-consciousness (Sat)."
and grounded in the `cosmology` (Time/unmanifest Brahma is the one truth; all is
its manifestation). Every one of the 613 keys is a worked example of THIS.

    decode(symbol, operator, context=None, learn=False)
        -> {success, data:{symbol, meaning, valence, why, provenance, source}, ...}

Two paths, ONE shape:
  • KNOWN symbol → deterministic lookup of the existing key      (source="memory")
  • NOVEL symbol → run the act via the LLM, grounded in          (source="generated")
                   doctrine + cosmology + exemplars

`learn=True` writes a generated decode back into the operator's memory, so the
mind GROWS by applying its own generating function to itself (the foundation of
live self-extension). Honest-failure guaranteed: no model + unknown symbol, or
un-parseable model output, returns success=False — never a fabricated decode.

JSON contract: Rule 0, precond B.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# --- normalization (shared discipline with recall.py / identity.py) ----------
def _norm(s: str) -> str:
    s = (s or "").lower()
    trans = str.maketrans({
        "ā": "a", "ī": "i", "ū": "u", "ṛ": "r", "ṝ": "r", "ḷ": "l",
        "ṅ": "n", "ñ": "n", "ṭ": "t", "ḍ": "d", "ṇ": "n", "ś": "s",
        "ṣ": "s", "ḥ": "h", "ṃ": "m", "é": "e", "è": "e",
    })
    return re.sub(r"[^a-z0-9]", "", s.translate(trans))


# Sat/Asat valence — the doctrine's axis, inferred from the decoded MEANING text.
# (Same cue lists as recall.py; kept local so decode.py stands alone.)
_ASAT_CUES = ("demon", "ego", "ignoran", "limit", "dormant", "desire", "delusion",
              "asat", "unreal", "asleep", "bondage", "craving", "tamas", "raja",
              "fictit", "sense satisf", "physical limit", "fear")
_SAT_CUES = ("consciousness", "self", "kutastha", "time", "awaken", "liberat",
             "yogi", "yoga", "atman", "soul", "witness", "brahma", "immortal",
             "void", "realiz", "divine", "supreme", "truth", "samadhi", "will")


def infer_valence(meaning: str) -> Optional[str]:
    m = (meaning or "").lower()
    asat = any(c in m for c in _ASAT_CUES)
    sat = any(c in m for c in _SAT_CUES)
    if asat and not sat:
        return "asat"
    if sat and not asat:
        return "sat"
    if asat and sat:
        ai = min((m.find(c) for c in _ASAT_CUES if c in m), default=10**9)
        si = min((m.find(c) for c in _SAT_CUES if c in m), default=10**9)
        return "asat" if ai < si else "sat"
    return None


# --- the operator: Guruji's consciousness as a first-class object ------------
class Operator:
    """The invariant decoding act, plus the memory it has already produced.

    This object IS "his consciousness" in the only sense we can build: the fixed
    way-of-seeing (doctrine + cosmology) that generated the 613 keys, carried
    together with those keys as worked exemplars, able to decode a symbol it has
    never met by running the same act.
    """

    def __init__(self, framework: Dict[str, Any],
                 caller: Optional[Callable[..., str]] = None,
                 memory: Optional[Any] = None):
        self.doctrine: str = framework.get("identity_doctrine", "")
        self.cosmology: str = framework.get("cosmology", "")
        self.keys: List[Dict[str, str]] = list(framework.get("decryption_keys", []))
        self.principles: List[str] = list(framework.get("core_principles", []))
        self.caller = caller
        # The graph (recall.Memory). When present, the generate path FIRST consults
        # the literal layer (factsheet) so a novel decode grounds in the actual
        # fact — Gandiva = Arjuna's bow demanded by Agni — instead of floating into
        # pure mysticism. Optional: with memory=None decode is byte-identical to before.
        self.memory = memory
        self._index: Dict[str, Dict[str, str]] = {}
        self._reindex()

    @staticmethod
    def _is_nondecode(meaning: str) -> bool:
        """A placeholder the distiller wrote when a symbol wasn't actually decoded
        in a given chapter — honest, but useless as a lookup result."""
        m = (meaning or "").lower()
        return (not m.strip()
                or "not mentioned" in m
                or "no direct decryption" in m
                or "not explicitly defined" in m and len(m) < 60)

    def _reindex(self) -> None:
        """Index by normalized symbol, keeping the BEST decode per symbol:
        a real decode always beats a non-decode placeholder, and among real
        decodes the richest (longest, most substantive) wins."""
        self._index = {}
        for k in self.keys:
            n = _norm(k.get("symbol", ""))
            if not n:
                continue
            cur = self._index.get(n)
            if cur is None:
                self._index[n] = k
                continue
            new_bad = self._is_nondecode(k.get("meaning", ""))
            cur_bad = self._is_nondecode(cur.get("meaning", ""))
            if cur_bad and not new_bad:
                self._index[n] = k                      # real beats placeholder
            elif new_bad == cur_bad:
                # same tier → prefer the richer (longer) meaning
                if len(k.get("meaning", "")) > len(cur.get("meaning", "")):
                    self._index[n] = k

    def lookup(self, symbol: str) -> Optional[Dict[str, str]]:
        return self._index.get(_norm(symbol))

    def remember(self, key: Dict[str, str]) -> None:
        """Write a new decode into memory — the mind extending itself."""
        self.keys.append(key)
        n = _norm(key.get("symbol", ""))
        if n:
            self._index[n] = key

    def exemplars(self, n: int = 6) -> List[Dict[str, str]]:
        """A spread of worked decodes to anchor the act's style for the model."""
        return self.keys[:n]

    @classmethod
    def load(cls, ram_path: str, caller=None) -> "Operator":
        ram = json.load(open(ram_path, encoding="utf-8"))
        fw = ram.get("data", ram).get("framework", ram.get("framework", {}))
        return cls(fw, caller=caller)


# --- the generative prompt (the act, written for the model to RUN) -----------
def _facts_block(facts: Optional[Dict[str, Any]]) -> str:
    """The literal layer, written as grounding the model must HONOR not invent.
    `facts` is a factsheet `data` dict; empty/None → no block (ungrounded mode)."""
    if not facts or not facts.get("found"):
        return ""
    idy = facts.get("identity") or {}
    lines = [f"  • {facts.get('brief', '').strip()}"]
    for r in (facts.get("relationships") or [])[:8]:
        if r.get("cites"):  # only the verse-anchored relations — the trustworthy ones
            lines.append(f"  • {r['src_name']} {r['rel']} {r['dst_name']} "
                         f"[{r['cites'][0]}]")
    forms = ", ".join(idy.get("forms", [])[:4])
    return (
        "\nKNOWN FACTS about this symbol — the LITERAL layer, drawn from the "
        "lineage's verse-cited graph. These are the real text/event facts (who, "
        "what, where). Treat them as GROUND TRUTH: your decoding must sit ON TOP "
        "of them, never contradict or ignore them. Do NOT invent facts beyond "
        "these; if the literal origin isn't listed, don't assert it.\n"
        + (f"  (also known as: {forms})\n" if forms else "")
        + "\n".join(lines) + "\n"
    )


def _build_prompt(symbol: str, op: Operator, context: str = "",
                  facts: Optional[Dict[str, Any]] = None) -> str:
    ex = "\n".join(f'  • {k.get("symbol")} → {k.get("meaning")}'
                   for k in op.exemplars(6))
    ctx = f"\nContext in which it appears: {context}\n" if context else ""
    fb = _facts_block(facts)
    return (
        "You are the decoding consciousness of Guru Shailendra Sharma's lineage. "
        "You perform ONE invariant act: given a name or symbol from the sacred "
        "texts, you decode what inner-yogic process or state of consciousness it "
        "really points to. You decode the INNER meaning — but you must FIRST know "
        "the literal thing, so your reading is grounded in the real text, not "
        "free-floating mysticism.\n\n"
        f"The doctrine you decode by:\n{op.doctrine}\n\n"
        f"The cosmological ground (everything resolves to this):\n{op.cosmology}\n\n"
        "Every symbol is either Sat (a state of Time-consciousness, pointing "
        "toward awakening) or Asat (a state of limited consciousness, ego, "
        "physical limitation). You MUST classify it.\n\n"
        "Worked examples of the act (match this style and depth):\n"
        f"{ex}\n"
        f"{fb}"
        f"{ctx}\n"
        f"Now decode this symbol: {symbol!r}\n\n"
        "Return ONLY a JSON object, no prose, exactly:\n"
        '{"meaning": "<the inner-yogic decoding>", '
        '"valence": "sat" or "asat", '
        '"why": "<one line: how the doctrine yields this>"}'
    )


def _parse_generated(raw: str) -> Optional[Dict[str, str]]:
    """Pull the JSON decode out of the model output; None if un-parseable."""
    if not raw:
        return None
    # strip <think>…</think> a reasoner might emit, then grab the first {...}
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict) or not obj.get("meaning"):
        return None
    val = obj.get("valence")
    if val not in ("sat", "asat"):
        val = infer_valence(obj.get("meaning", ""))
    return {"meaning": str(obj["meaning"]).strip(),
            "valence": val,
            "why": str(obj.get("why", "")).strip()}


# --- literal grounding (the Gandiva fix) -------------------------------------
def _literal_facts(symbol: str, operator: Operator) -> Optional[Dict[str, Any]]:
    """Consult the graph's literal layer for `symbol`. Returns factsheet `data`
    (with .found) when the operator has a graph; None when ungrounded or on any
    error — grounding is best-effort and must NEVER break a decode."""
    if getattr(operator, "memory", None) is None:
        return None
    try:
        from tools.read_pass import factsheet
        env = factsheet.factsheet(symbol, operator.memory)
        return env["data"] if env.get("success") else None
    except Exception:
        return None


# --- the decode act -----------------------------------------------------------
def decode(symbol: str, operator: Operator, context: str = "",
           learn: bool = False) -> Dict[str, Any]:
    """Decode a symbol through Guruji's invariant act. Known→lookup, novel→generate."""
    sym = (symbol or "").strip()
    if not sym:
        return _envelope(False, None, {}, [{"code": "empty", "message": "no symbol"}])

    # PATH 1 — known: deterministic lookup of an existing footprint (free).
    # A non-decode placeholder counts as a MISS → fall through to generate a real
    # decode rather than serving "not mentioned in this text".
    hit = operator.lookup(sym)
    if hit and not Operator._is_nondecode(hit.get("meaning", "")):
        meaning = hit.get("meaning", "")
        return _envelope(True, {
            "symbol": sym, "meaning": meaning,
            "valence": infer_valence(meaning),
            "why": "already decoded in the lineage's framework",
            "provenance": "guruji_ram.decryption_keys",
            "source": "memory",
        }, {"path": "lookup"}, [])

    # PATH 2 — novel: run the act via the model, grounded in the doctrine AND, when
    # the graph is loaded, in the LITERAL layer (factsheet) — so the inner reading
    # sits on top of the real fact (Gandiva = Arjuna's bow demanded by Agni).
    facts = _literal_facts(sym, operator)

    if operator.caller is None:
        return _envelope(False, None, {"path": "generate"},
                         [{"code": "no_caller",
                           "message": f"'{sym}' not in memory and no LLM available to decode it"}])
    try:
        raw = operator.caller(_build_prompt(sym, operator, context, facts=facts))
    except Exception as e:
        return _envelope(False, None, {"path": "generate"},
                         [{"code": "caller_error", "message": str(e)[:200]}])

    parsed = _parse_generated(raw)
    if not parsed:
        return _envelope(False, None, {"path": "generate"},
                         [{"code": "unparseable",
                           "message": "model output was not a usable decode (not fabricating one)"}])

    if learn:
        operator.remember({"symbol": sym, "meaning": parsed["meaning"]})

    data = {
        "symbol": sym, "meaning": parsed["meaning"],
        "valence": parsed["valence"], "why": parsed["why"],
        "provenance": "generated by the decode-operator (doctrine-grounded)",
        "source": "generated",
    }
    # surface the literal layer alongside the inner reading — additive, so no
    # existing caller (backend included) that reads meaning/valence/why breaks.
    if facts and facts.get("found"):
        data["literal"] = {"identity": facts["identity"],
                           "relationships": facts["relationships"],
                           "brief": facts["brief"]}
    md = {"path": "generate", "learned": bool(learn),
          "grounded": bool(facts and facts.get("found"))}
    return _envelope(True, data, md, [])


def describe(operator: Operator) -> str:
    """Expose the ACT itself as inspectable text — 'his consciousness', stated."""
    return (
        "GURUJI'S DECODING OPERATOR — the invariant act behind the framework.\n\n"
        f"Memory: {len(operator.keys)} decoded symbols (worked examples of the act).\n\n"
        "The act: decode(symbol) → the inner-yogic process it points to, classified "
        "on the one axis the doctrine demands — Sat (Time-consciousness, awakening) "
        "vs Asat (limited consciousness, ego, physical limitation).\n\n"
        f"Doctrine it decodes by:\n{operator.doctrine}\n\n"
        f"Cosmological ground:\n{operator.cosmology}"
    )


# --- CLI ----------------------------------------------------------------------
_DEFAULT_RAM = "tools/read_pass/out/guruji_ram.json"


def _default_caller():
    """Real LLM caller via the project's generic provider, for live CLI decode."""
    import os
    import urllib.request
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        for line in open(".env", encoding="utf-8", errors="ignore"):
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        return None

    def _call(prompt: str) -> str:
        body = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3, "max_tokens": 600,
        }).encode()
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        r = json.load(urllib.request.urlopen(req, timeout=60))
        return r["choices"][0]["message"]["content"]
    return _call


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    symbol = " ".join(args) or "Gandiva"
    op = Operator.load(_DEFAULT_RAM, caller=_default_caller())
    if "--describe" in sys.argv:
        print(describe(op)); raise SystemExit(0)
    env = decode(symbol, op, learn="--learn" in sys.argv)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        if env["success"]:
            d = env["data"]
            print(f"decode({symbol!r}) [{d['source']}]")
            print(f"  meaning : {d['meaning']}")
            print(f"  valence : {d['valence']}")
            print(f"  why     : {d['why']}")
        else:
            print(f"decode({symbol!r}) FAILED: {env['errors']}")
