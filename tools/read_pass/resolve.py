"""resolve — LLM-powered entity resolution using a REASONING model.

The mechanical alias merge (graph.py union-find) catches explicit alias
declarations. This module handles what code can't: implicit identities,
avatar theology, and context-dependent names. It feeds the graph's
alias_overlaps() to a reasoning model (deepseek-v4-pro) and gets back
adjudicated verdicts.

WHY A REASONING MODEL: "Is Vāsudeva here referring to Krishna or his
father?" is a judgment call requiring evidence synthesis across chapters.
deepseek-chat guesses; deepseek-v4-pro thinks through the textual evidence
in its 6K reasoning tokens, which is exactly what those tokens are for.

Verdicts:
  same_entity    — merge the nodes (e.g. Pārtha = Arjuna)
  avatar_relation — keep separate, mark the theological link
  coincidental   — same name, different person (e.g. multiple Vasudevas)
  context_dependent — sometimes one, sometimes the other

JSON contract (Rule 0, precond B):
  resolve_overlaps(pairs, entities, key) -> {success, data, metadata, errors}
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


ADJUDICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "adjudications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity_a": {"type": "string"},
                    "entity_b": {"type": "string"},
                    "verdict": {"type": "string",
                                "enum": ["same_entity", "avatar_relation",
                                         "coincidental", "context_dependent"]},
                    "reasoning": {"type": "string"},
                    "shared_aliases_assessment": {
                        "type": "object",
                        "description": "For each shared alias, which entity it primarily refers to or 'both'"
                    }
                },
                "required": ["entity_a", "entity_b", "verdict", "reasoning"]
            }
        }
    },
    "required": ["adjudications"]
}


def build_prompt(pairs: List[Tuple[Tuple[str, str], Set[str]]],
                 entities: List[Dict[str, Any]]) -> str:
    eid = {e["id"]: e for e in entities}
    sections = []
    for (a_id, b_id), shared in pairs:
        ea = eid.get(a_id, {})
        eb = eid.get(b_id, {})
        sections.append(f"""
PAIR: {ea.get('name','?')} (id: {a_id}) vs {eb.get('name','?')} (id: {b_id})
  Entity A forms: {ea.get('all_forms',[])}
  Entity A kind: {ea.get('kind','?')}, chapters: {ea.get('chapters',[])}
  Entity B forms: {eb.get('all_forms',[])}
  Entity B kind: {eb.get('kind','?')}, chapters: {eb.get('chapters',[])}
  Shared aliases: {sorted(shared)}
""".strip())

    return f"""You are an expert in Hindu sacred texts (Puranas, Epics, Upanishads).

I have a knowledge graph extracted from the Puranas. The following entity pairs SHARE
one or more aliases/epithets. For each pair, determine whether they are:
- **same_entity**: truly the same person/being (merge them)
- **avatar_relation**: distinct but theologically linked (e.g. Krishna is an avatāra of Vishnu — keep separate but mark the link)
- **coincidental**: same name, different person entirely (e.g. multiple kings named Bharata across different Puranas)
- **context_dependent**: sometimes refers to one, sometimes the other depending on context (e.g. Vāsudeva = Krishna usually, but also Vasudeva his father)

For each shared alias, assess which entity it primarily refers to, or "both" if genuinely shared.

THINK CAREFULLY. Use your knowledge of Puranic genealogy, avatar theology, and Sanskrit
etymology. Cite specific textual evidence where possible.

{chr(10).join(sections)}

Return ONLY valid JSON matching this schema:
{json.dumps(ADJUDICATION_SCHEMA, indent=1)}"""


def _call_reasoner(prompt: str, model: str, api_key: str,
                   timeout: int = 300) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 16384,  # reasoning model burns ~6K on thinking
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    return resp["choices"][0]["message"]["content"]


def resolve_overlaps(
    pairs: List[Tuple[Tuple[str, str], Set[str]]],
    entities: List[Dict[str, Any]],
    api_key: str,
    model: str = "deepseek-v4-pro",
    caller: Optional[Callable[..., str]] = None,
    batch_size: int = 10,
) -> Dict[str, Any]:
    """Adjudicate entity alias overlaps using a reasoning model.

    Batches pairs to stay within context limits. Returns the full set of
    adjudications in one envelope.
    """
    md = {"model": model, "n_pairs_submitted": len(pairs)}
    if not pairs:
        return _envelope(True, {"adjudications": [], "n_pairs_submitted": 0}, md, [])

    fn = caller or _call_reasoner
    all_adjs = []
    errors = []

    for i in range(0, len(pairs), batch_size):
        batch = pairs[i:i + batch_size]
        prompt = build_prompt(batch, entities)
        try:
            raw = fn(prompt, model, api_key)
            parsed = json.loads(raw)
            adjs = parsed.get("adjudications", [])
            all_adjs.extend(adjs)
        except json.JSONDecodeError as e:
            errors.append({"code": "bad_json", "message": str(e)[:200],
                           "batch_start": i})
        except Exception as e:
            errors.append({"code": "call_failed", "message": str(e)[:200],
                           "batch_start": i})

    data = {
        "adjudications": all_adjs,
        "n_pairs_submitted": len(pairs),
        "n_adjudicated": len(all_adjs),
        "verdict_counts": {},
    }
    for a in all_adjs:
        v = a.get("verdict", "unknown")
        data["verdict_counts"][v] = data["verdict_counts"].get(v, 0) + 1

    return _envelope(len(errors) == 0, data, md, errors)


def run(graph_path: str = "tools/read_pass/out/bhagavata_v2.records.jsonl",
        api_key: str = "", top_n: int = 20) -> Dict[str, Any]:
    """End-to-end: load graph, extract top overlaps, adjudicate."""
    import os
    from tools.read_pass import graph as G

    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return _envelope(False, None, {}, [{"code": "no_key", "message": "set DEEPSEEK_API_KEY"}])

    g = G.build([json.loads(l) for l in open(graph_path) if l.strip()])
    overlaps = g.alias_overlaps()
    # sort by number of shared aliases (most ambiguous first)
    ranked = sorted(overlaps.items(), key=lambda x: -len(x[1]))[:top_n]
    pairs = [(k, v) for k, v in ranked]

    return resolve_overlaps(pairs, g.entities, api_key)


if __name__ == "__main__":
    import sys, os
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    path = sys.argv[1] if len(sys.argv) > 1 else "tools/read_pass/out/bhagavata_full.records.v1_broken_lens.jsonl"
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    env = run(path, api_key, top_n)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    elif not env["success"]:
        print(f"ERROR: {env.get('errors', [{}])[0].get('message', 'unknown')}")
    else:
        d = env["data"]
        print(f"Adjudicated {d['n_adjudicated']}/{d['n_pairs_submitted']} pairs")
        print(f"Verdicts: {d['verdict_counts']}")
        for a in d["adjudications"][:5]:
            print(f"  {a['entity_a']} ↔ {a['entity_b']}: {a['verdict']}")
            print(f"    {a['reasoning'][:120]}...")
