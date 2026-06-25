"""insights — emergent understanding from the connected graph.

This is the layer that THINKS ABOUT what the graph contains, rather than
just extracting or cleaning it. It operates on graph-level summaries (not
raw text) and asks the reasoning model questions that no single chapter
could answer:

  - Pattern detection across hundreds of stories
  - Karmic chain analysis (curse → incarnation → liberation)
  - Cross-text reconciliation and contradiction
  - Theological synthesis from accumulated evidence
  - Structural observations about how the Puranas are constructed

The input is a graph_summary dict (pre-computed by summarize_graph()) that
compresses the full graph into what a reasoning model can fit in context.
This is NOT the raw graph — it's the narrative hubs, cross-chapter chains,
avatar patterns, teaching clusters, and predicate distribution.

JSON contract (Rule 0, precond B):
  generate_insights(summary, key) -> {success, data:{insights:[], meta_observation}, metadata, errors}
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


INSIGHT_TYPES = [
    "pattern",              # recurrent structural pattern across stories
    "karmic_chain",         # curse/boon → consequence → resolution
    "theological_synthesis",# position derived from accumulated evidence
    "cross_text",           # agreement/disagreement between Puranas
    "structural",           # how the text is constructed (not what it says)
    "anomaly",              # something unexpected or contradictory
]

INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": INSIGHT_TYPES},
                    "title": {"type": "string"},
                    "insight": {"type": "string",
                                "description": "The full insight, 2-4 sentences"},
                    "evidence": {"type": "array", "items": {"type": "string"},
                                 "description": "Specific citations or data points"},
                    "confidence": {"type": "string",
                                   "enum": ["high", "medium", "speculative"]},
                    "cross_references": {"type": "array", "items": {"type": "string"},
                                         "description": "References to other texts that could confirm/deny"},
                },
                "required": ["type", "title", "insight", "evidence", "confidence"]
            }
        },
        "meta_observation": {
            "type": "string",
            "description": "One overarching observation about the corpus as a whole"
        }
    },
    "required": ["insights", "meta_observation"]
}


def build_prompt(graph_summary: Dict[str, Any]) -> str:
    sections = []

    if "narrative_hubs" in graph_summary:
        hub_lines = []
        for h in graph_summary["narrative_hubs"]:
            preds = ", ".join(h.get("sample_preds", [])[:6])
            hub_lines.append(f"  {h['name']}: {h['n_predicates']} predicates ({preds}...)")
        sections.append("NARRATIVE HUBS (entities with the most diverse relationship types):\n"
                       + "\n".join(hub_lines))

    if "cross_chapter_chains" in graph_summary:
        chain_lines = []
        for ch in graph_summary["cross_chapter_chains"]:
            consequences = " → ".join(
                f"{c['event']} (ch.{c['chapter']})" for c in ch.get("consequences", []))
            chain_lines.append(f"  {ch['curse']} (ch.{ch['chapter']}) → {consequences}")
        sections.append("CROSS-CHAPTER CHAINS (events connected across distant chapters):\n"
                       + "\n".join(chain_lines))

    if "avatar_actions" in graph_summary:
        av_lines = []
        for a in graph_summary["avatar_actions"]:
            acts = ", ".join(a.get("actions", []))
            av_lines.append(f"  {a['avatar']} (avatar of {a['source']}): {acts}")
        sections.append("AVATAR PATTERNS:\n" + "\n".join(av_lines))

    if "teaching_clusters" in graph_summary:
        tc_lines = []
        for tc in graph_summary["teaching_clusters"]:
            tc_lines.append(f"  \"{tc['core_truth']}\" ({tc['n_instances']} instances)")
        sections.append("RECURRING TEACHINGS:\n" + "\n".join(tc_lines))

    n_ent = graph_summary.get("n_entities", "?")
    n_edge = graph_summary.get("n_edges", "?")

    return f"""You are a scholar of Hindu sacred texts (Puranas, Epics, Upanishads) with deep
knowledge of Kriya-Yoga as taught by Shailendra Sharma.

I have a knowledge graph extracted from the Puranas containing {n_ent} entities and
{n_edge} edges across {graph_summary.get('n_predicates', '?')} relationship types. Below is
a STRUCTURAL SUMMARY of the graph — not the source text, but the PATTERNS that emerge
from connecting all the data.

Your task: look at this connected graph and tell me what you UNDERSTAND that no single
chapter could have told you. I want EMERGENT insights — patterns, chains, structures,
and theological positions that only become visible when you see the whole picture.

Think about:
1. PATTERNS: Do certain types of entities (avatars, sages, kings) follow recurrent
   narrative patterns? Are there structural regularities?
2. KARMIC CHAINS: Where does a cause in one chapter produce effects chapters/books later?
   What are the longest causal chains?
3. THEOLOGICAL POSITIONS: What positions does this text ARGUE (not just state)? How does
   the narrative structure support the theological argument?
4. ANOMALIES: What's unexpected? What breaks the pattern? (These are often the most
   interesting insights.)
5. STRUCTURAL OBSERVATIONS: How is the text itself constructed? What does the choice of
   which stories to tell (and how to connect them) reveal about the compiler's intent?

If you know Sharma's Kriya-Yoga perspective, apply it: what does this structural pattern
look like through the lens of inner yogic practice?

GRAPH SUMMARY:
{chr(10).join(sections)}

Return ONLY valid JSON:
{json.dumps(INSIGHT_SCHEMA, indent=1)}"""


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


def generate_insights(
    graph_summary: Dict[str, Any],
    api_key: str,
    model: str = "deepseek-v4-pro",
    caller: Optional[Callable[..., str]] = None,
) -> Dict[str, Any]:
    """Ask the reasoning model to think about the connected graph."""
    md = {"model": model}
    fn = caller or _call_reasoner
    prompt = build_prompt(graph_summary)

    try:
        raw = fn(prompt, model, api_key)
        parsed = json.loads(raw)
        ins = parsed.get("insights", [])
        meta = parsed.get("meta_observation", "")
        data = {
            "insights": ins,
            "meta_observation": meta,
            "n_insights": len(ins),
            "type_counts": {},
        }
        for i in ins:
            t = i.get("type", "unknown")
            data["type_counts"][t] = data["type_counts"].get(t, 0) + 1
        return _envelope(True, data, md, [])
    except json.JSONDecodeError as e:
        return _envelope(False, None, md,
                         [{"code": "bad_json", "message": str(e)[:200]}])
    except Exception as e:
        return _envelope(False, None, md,
                         [{"code": "call_failed", "message": str(e)[:200]}])


def summarize_graph(graph_obj, teaching_clusters=None, top_hubs=10, top_chains=10):
    """Build the summary dict that generate_insights expects.

    Takes a built Graph object + optional teaching clusters and compresses
    them into a prompt-friendly structure.
    """
    from collections import defaultdict

    ent_pred_diversity = defaultdict(set)
    for e in graph_obj.edges:
        ent_pred_diversity[e["src"]].add(e["rel"])
        ent_pred_diversity[e["dst"]].add(e["rel"])
    diverse = sorted(ent_pred_diversity.items(), key=lambda x: -len(x[1]))[:top_hubs]
    eid = {e["id"]: e for e in graph_obj.entities}

    hubs = []
    for entity_id, preds in diverse:
        ent = eid.get(entity_id, {})
        hubs.append({
            "name": ent.get("name", entity_id),
            "n_predicates": len(preds),
            "sample_preds": sorted(preds)[:6],
        })

    # cross-chapter chains: find curses with consequences in other chapters
    chains = []
    curses = graph_obj.curses()
    for c in curses[:top_chains]:
        dst_name = c["dst_name"].lower()
        consequences = [e for e in graph_obj.edges
                        if dst_name in e.get("dst_name", "").lower()
                        and e["rel"] != "cursed"
                        and e.get("chapters") != c.get("chapters")]
        if consequences:
            chains.append({
                "curse": f"{c['src_name']} cursed {c['dst_name']}",
                "chapter": c.get("chapters", ["?"])[0],
                "consequences": [
                    {"event": f"{e['src_name']} {e['rel']} {e['dst_name']}",
                     "chapter": e.get("chapters", ["?"])[0]}
                    for e in consequences[:5]
                ]
            })

    # avatar patterns
    avatars_raw = graph_obj.edges_of_kind("avatar")
    avatar_patterns = []
    for av in avatars_raw[:15]:
        actions = [e for e in graph_obj.edges
                   if e["src"] == av["src"] and e["rel"] != "avatar"]
        ent = eid.get(av["src"], {})
        avatar_patterns.append({
            "avatar": ent.get("name", av["src"]),
            "source": av.get("dst_name", "?"),
            "actions": [f"{a['rel']} {a['dst_name']}" for a in actions[:4]],
        })

    summary = {
        "n_entities": len(graph_obj.entities),
        "n_edges": len(graph_obj.edges),
        "n_predicates": len(graph_obj.predicates()),
        "narrative_hubs": hubs,
        "cross_chapter_chains": chains,
        "avatar_actions": avatar_patterns,
    }
    if teaching_clusters:
        summary["teaching_clusters"] = [
            {"core_truth": c["core_truth"],
             "n_instances": len(c.get("supporting_teachings", []))}
            for c in teaching_clusters[:20]
        ]
    return summary


def run(records_path: str = "tools/read_pass/out/bhagavata_full.records.v1_broken_lens.jsonl",
        api_key: str = "",
        synthesis_path: str = "") -> Dict[str, Any]:
    """End-to-end: build graph, summarize, generate insights."""
    import os
    from tools.read_pass import graph as G

    if not api_key:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return _envelope(False, None, {}, [{"code": "no_key", "message": "set DEEPSEEK_API_KEY"}])

    recs = [json.loads(l) for l in open(records_path) if l.strip()]
    g = G.build(recs)

    tc = None
    if synthesis_path and os.path.exists(synthesis_path):
        syn = json.load(open(synthesis_path))
        tc = syn.get("data", {}).get("clusters", [])

    summary = summarize_graph(g, tc)
    return generate_insights(summary, api_key)


if __name__ == "__main__":
    import sys, os
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    path = sys.argv[1] if len(sys.argv) > 1 else "tools/read_pass/out/bhagavata_full.records.v1_broken_lens.jsonl"
    syn = sys.argv[2] if len(sys.argv) > 2 else ""
    env = run(path, api_key, syn)
    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    elif not env["success"]:
        print(f"ERROR: {env.get('errors', [{}])[0].get('message', 'unknown')}")
    else:
        d = env["data"]
        print(f"=== {d['n_insights']} INSIGHTS ===")
        print(f"Types: {d['type_counts']}")
        print(f"\nMeta: {d['meta_observation'][:200]}")
        for i in d["insights"]:
            print(f"\n[{i['type'].upper()}] {i['title']} ({i['confidence']})")
            print(f"  {i['insight'][:200]}")
            if i.get("evidence"):
                for ev in i["evidence"][:3]:
                    print(f"    - {ev[:120]}")
