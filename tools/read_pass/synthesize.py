"""synthesize — cluster and distill raw teachings using a REASONING model.

Project 3 of daddy's three: "give me the key distilled information."

The read-pass extracts 1,340+ raw teachings across 338 Bhagavata chapters. Many
are the same truth expressed differently:
  - "Surrender to the Supreme Lord is the highest dharma"
  - "Taking shelter of Hari's lotus feet purifies the heart"
  - "Devotion to Vishnu transcends all material bondage"
These are ONE teaching. A mechanical dedup misses this. A chat model guesses.
A reasoning model THINKS through the semantic relationships and clusters them
while preserving the nuance.

The reasoning model also SYNTHESIZES the Sharma lens notes across a cluster —
merging per-verse Kriya-Yoga interpretations into one coherent decoded teaching.

JSON contract (Rule 0, precond B):
  synthesize_teachings(teachings, key) -> {success, data:{clusters:[]}, metadata, errors}
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


CLUSTER_SCHEMA = {
    "type": "object",
    "properties": {
        "clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "core_truth": {"type": "string",
                                   "description": "The distilled essence of this cluster"},
                    "supporting_teachings": {
                        "type": "array", "items": {"type": "integer"},
                        "description": "Indices (0-based) of the raw teachings in this cluster"},
                    "lens_synthesis": {
                        "type": "string",
                        "description": "Merged Sharma/Kriya-Yoga interpretation across the cluster"},
                    "verse_citations": {
                        "type": "array", "items": {"type": "string"},
                        "description": "All verse markers from the supporting teachings"}
                },
                "required": ["core_truth", "supporting_teachings", "verse_citations"]
            }
        }
    },
    "required": ["clusters"]
}


def build_prompt(teachings: List[Dict[str, Any]]) -> str:
    lines = []
    for i, t in enumerate(teachings):
        ln = t.get("lens_note", "")
        vr = ", ".join(t.get("verse_ranges", []))
        lines.append(f"[{i}] \"{t['teaching']}\"  (verses: {vr})"
                     + (f"  [LENS: {ln}]" if ln else ""))

    return f"""You are an expert in Hindu philosophy, Puranic literature, and Kriya-Yoga
as taught by Shailendra Sharma.

Below are {len(teachings)} teachings extracted from the Puranas. Many express the
SAME core truth in different words. Your task:

1. CLUSTER them by semantic similarity — group teachings that express the same
   fundamental truth, even if phrased very differently.
2. For each cluster, DISTILL a single "core_truth" sentence that captures the
   essence without losing nuance.
3. If any teachings in the cluster have [LENS] notes (Sharma's Kriya-Yoga
   interpretation), SYNTHESIZE them into one "lens_synthesis" that merges the
   individual interpretations coherently.
4. Collect all verse citations from the cluster.

THINK CAREFULLY about what makes two teachings the SAME vs DIFFERENT:
- "Surrender to the Lord" and "take shelter of Hari's feet" = SAME (both about surrender/devotion)
- "Surrender to the Lord" and "the Lord surrenders to His devotee" = DIFFERENT (inverse relationship)
- "The holy name destroys sin" and "devotion transcends bondage" = RELATED but DIFFERENT (mechanism differs)

Err on the side of keeping clusters tight. Better to have 50 precise clusters than
20 mushy ones.

TEACHINGS:
{chr(10).join(lines)}

Return ONLY valid JSON matching this schema:
{json.dumps(CLUSTER_SCHEMA, indent=1)}"""


def _call_reasoner(prompt: str, model: str, api_key: str,
                   timeout: int = 300) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 16384,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    return resp["choices"][0]["message"]["content"]


def synthesize_teachings(
    teachings: List[Dict[str, Any]],
    api_key: str,
    model: str = "deepseek-v4-pro",
    caller: Optional[Callable[..., str]] = None,
    batch_size: int = 100,
) -> Dict[str, Any]:
    """Cluster and distill raw teachings using a reasoning model.

    Batches teachings (context limit ~64K for the prompt) and merges
    cluster results across batches.
    """
    md = {"model": model, "n_raw_teachings": len(teachings)}
    if not teachings:
        return _envelope(True, {"clusters": [], "n_raw_teachings": 0,
                                "n_clusters": 0}, md, [])

    fn = caller or _call_reasoner
    all_clusters = []
    errors = []
    offset = 0

    for i in range(0, len(teachings), batch_size):
        batch = teachings[i:i + batch_size]
        prompt = build_prompt(batch)
        try:
            raw = fn(prompt, model, api_key)
            parsed = json.loads(raw)
            clusters = parsed.get("clusters", [])
            # adjust indices to global (batch offset)
            for c in clusters:
                c["supporting_teachings"] = [idx + offset for idx in c.get("supporting_teachings", [])]
            all_clusters.extend(clusters)
        except json.JSONDecodeError as e:
            errors.append({"code": "bad_json", "message": str(e)[:200], "batch_start": i})
        except Exception as e:
            errors.append({"code": "call_failed", "message": str(e)[:200], "batch_start": i})
        offset += len(batch)

    data = {
        "clusters": all_clusters,
        "n_raw_teachings": len(teachings),
        "n_clusters": len(all_clusters),
        "compression_ratio": round(len(teachings) / max(len(all_clusters), 1), 1),
    }
    return _envelope(len(errors) == 0, data, md, errors)


def run(records_path: str = "tools/read_pass/out/bhagavata_full.records.v1_broken_lens.jsonl",
        api_key: str = "") -> Dict[str, Any]:
    """End-to-end: load records, extract all teachings, synthesize."""
    import os
    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return _envelope(False, None, {}, [{"code": "no_key", "message": "set DEEPSEEK_API_KEY"}])

    teachings = []
    for line in open(records_path):
        r = json.loads(line)
        ch = r.get("_provenance", {}).get("chapter_label", "?")
        for t in r.get("teachings", []):
            t["_chapter"] = ch
            teachings.append(t)

    return synthesize_teachings(teachings, api_key)


if __name__ == "__main__":
    import sys, os
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    path = sys.argv[1] if len(sys.argv) > 1 else "tools/read_pass/out/bhagavata_full.records.v1_broken_lens.jsonl"
    env = run(path, api_key)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    elif not env["success"]:
        print(f"ERROR: {env.get('errors', [{}])[0].get('message', 'unknown')}")
    else:
        d = env["data"]
        print(f"{d['n_raw_teachings']} teachings → {d['n_clusters']} core truths "
              f"({d['compression_ratio']}:1 compression)")
        for c in d["clusters"][:5]:
            print(f"  \"{c['core_truth'][:100]}...\"")
            print(f"    ({len(c['supporting_teachings'])} teachings, "
                  f"{len(c.get('verse_citations',[]))} citations)")
