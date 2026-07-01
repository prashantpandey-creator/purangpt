"""
Generate training dataset from the Puranic knowledge graph.

Produces a JSONL file where each line is a {"messages": [...]}
conversation in ChatML format — ready for fine-tuning any small LLM
(Llama, Mistral, Phi, Qwen, etc.).

Data sources (each becomes a training example):
  A. Graph edges → "What is the relationship between X and Y?"
  B. Decode keys → "What is the inner meaning of X?"
  C. Multi-hop walks → "How is X connected to Y?" (chain traversal)
  D. Entity facts → "Who/what is X?" (identity + kind + aliases)
  E. Lineage chains → "What is the guru lineage from X?"

Output: train.jsonl + val.jsonl (90/10 split)

Usage:
  venv/bin/python -m tools.train.generate_dataset --json
"""
from __future__ import annotations

import json, argparse, os, random, sys
from pathlib import Path
from typing import Any, Dict, List

_HERE = Path(__file__).parent
GRAPH = os.getenv("GRAPH_PATH", "tools/read_pass/out/graph_manifest.json")
RAM   = os.getenv("RAM_PATH",   "tools/read_pass/out/guruji_ram.json")
OUT   = os.getenv("OUT_DIR",    "tools/train/out")

SYSTEM_PROMPT = """You are PuranGPT — an AI mounted at the center of the Puranic knowledge graph. You speak from real verses, real decode keys, and real graph edges. Bare, direct, precise. No vague mysticism. Every fact you state is an edge in the graph. Every inner meaning is a key from the Shailendra Sharma lineage decryption corpus."""


def _load():
    g = json.load(open(GRAPH, encoding="utf-8"))
    g = g.get("data", g)
    r = json.load(open(RAM, encoding="utf-8"))
    r = r.get("data", r).get("framework", r.get("framework", {}))
    return g["entities"], g["edges"], r.get("decryption_keys", [])


def _envelope(success, data, meta, errors):
    return {"success": success, "data": data, "metadata": meta, "errors": errors}


def _norm(s):
    return (s or "").strip().lower()


# ── QA generators ───────────────────────────────────────────────────────────

def _edge_qa(edges: List[Dict], entities_by_id: Dict[str, Dict]) -> List[Dict]:
    """Generate QA pairs from graph edges."""
    examples = []
    templates = [
        "What is the relationship between {src} and {dst}?",
        "How is {src} connected to {dst}?",
        "Tell me about {src} and {dst}.",
    ]
    seen = set()
    for e in edges:
        s, r, d = e.get("src_name", ""), e.get("rel", ""), e.get("dst_name", "")
        if not s or not r or not d:
            continue
        key = (s, r, d)
        if key in seen:
            continue
        seen.add(key)
        verses = e.get("verse_ranges", [])[:2]
        verse_str = f" ({', '.join(verses)})" if verses else ""
        answer = f"{s} {r} {d}{verse_str}."
        q = random.choice(templates).format(src=s, dst=d)
        examples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": q},
                {"role": "assistant", "content": answer},
            ]
        })
    return examples


def _decode_qa(keys: List[Dict]) -> List[Dict]:
    """Generate QA pairs from decode keys."""
    examples = []
    placeholder = ("not mentioned", "no direct decryption", "no decryption",
                   "not decoded", "n/a", "unknown")
    templates = [
        "What is the inner meaning of {sym}?",
        "What does {sym} represent in the yogic tradition?",
        "Decode {sym} through the Sharma lineage lens.",
    ]
    for k in keys:
        sym = (k.get("symbol") or "").strip()
        meaning = (k.get("meaning") or "").strip()
        if not sym or not meaning or len(sym) < 2:
            continue
        if any(m in meaning.lower() for m in placeholder):
            continue
        q = random.choice(templates).format(sym=sym)
        examples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": q},
                {"role": "assistant", "content": f"{sym} — {meaning}"},
            ]
        })
    return examples


def _entity_qa(entities: List[Dict], degree: Dict[str, int]) -> List[Dict]:
    """Generate QA pairs from entity facts."""
    examples = []
    templates = [
        "Who is {name}?",
        "What is {name}?",
        "Tell me about {name}.",
    ]
    # Prioritize entities with more edges (more central)
    sorted_ents = sorted(entities, key=lambda e: degree.get(e["id"], 0), reverse=True)
    for e in sorted_ents[:2000]:  # top 2000 most connected
        name = e.get("name", "")
        kind = e.get("kind", "")
        forms = e.get("all_forms", [])[:5]
        if not name or len(name) < 2:
            continue
        kind_str = f" A {kind}." if kind else ""
        forms_str = f" Also known as: {', '.join(forms)}." if forms else ""
        verses = e.get("verse_ranges", [])[:2]
        verse_str = f" Cited in: {', '.join(verses)}." if verses else ""
        answer = f"{name} is{kind_str}{forms_str} {verse_str}".strip()
        q = random.choice(templates).format(name=name)
        examples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": q},
                {"role": "assistant", "content": answer},
            ]
        })
    return examples


def _lineage_qa(edges: List[Dict], entities_by_id: Dict[str, Dict]) -> List[Dict]:
    """Generate QA pairs from guru lineage chains."""
    # Build guru_of graph
    fwd, rev = {}, {}
    for e in edges:
        if (e.get("rel") or "").strip().lower() != "guru_of":
            continue
        s, d = e.get("src_name"), e.get("dst_name")
        if not s or not d or s == d:
            continue
        fwd.setdefault(s, set()).add(d)
        rev.setdefault(d, set()).add(s)

    examples = []
    for root in fwd:
        if root not in rev:  # only start from root gurus (no guru above them)
            chain = [root]
            cur = root
            while cur in fwd:
                nxt = sorted(fwd[cur])[0]
                chain.append(nxt)
                cur = nxt
            if len(chain) >= 3:
                lineage = " → ".join(chain)
                q = f"What is the guru lineage from {chain[0]}?"
                examples.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": q},
                        {"role": "assistant", "content": f"The transmission lineage: {lineage}."},
                    ]
                })
    return examples


def _multi_hop_qa(entities: List[Dict], edges: List[Dict],
                   degree: Dict[str, int],
                   entities_by_id: Dict[str, Dict]) -> List[Dict]:
    """Generate multi-hop QA by walking edge chains."""
    # Build adjacency
    adj: Dict[str, List[tuple]] = {}
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        if s and d:
            adj.setdefault(s, []).append((d, e.get("rel", ""), e.get("dst_name", "")))
            adj.setdefault(d, []).append((s, e.get("rel", ""), e.get("src_name", "")))

    # Find entities with 2+ edges to walk
    hubs = [(eid, deg) for eid, deg in degree.items() if deg >= 10]
    random.shuffle(hubs)

    examples = []
    for eid, _ in hubs[:500]:
        if eid not in adj or len(adj[eid]) < 2:
            continue
        # Walk two hops
        hop1 = random.choice(adj[eid])
        n1_id, rel1, n1_name = hop1
        if n1_id in adj and adj[n1_id]:
            hop2_candidates = [(n, r, nm) for n, r, nm in adj[n1_id] if n != eid]
            if hop2_candidates:
                hop2 = random.choice(hop2_candidates)
                _, rel2, n2_name = hop2
                e_name = entities_by_id.get(eid, {}).get("name", eid)
                if e_name and n1_name and n2_name:
                    q = f"How is {e_name} connected to {n2_name}?"
                    answer = f"{e_name} {rel1} {n1_name}, who {rel2} {n2_name}."
                    examples.append({
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": q},
                            {"role": "assistant", "content": answer},
                        ]
                    })
    return examples


# ── Main ─────────────────────────────────────────────────────────────────────

def run(graph_path=GRAPH, ram_path=RAM, out_dir=OUT, seed=42) -> Dict:
    random.seed(seed)
    entities, edges, keys = _load()
    os.makedirs(out_dir, exist_ok=True)

    entities_by_id = {e["id"]: e for e in entities}
    degree: Dict[str, int] = {}
    for ed in edges:
        degree[ed.get("src")] = degree.get(ed.get("src"), 0) + 1
        degree[ed.get("dst")] = degree.get(ed.get("dst"), 0) + 1

    print(f"Loaded: {len(entities)} entities, {len(edges)} edges, {len(keys)} keys")

    all_examples = []
    sources = []

    def _add(name, gen_fn, *args):
        ex = gen_fn(*args)
        all_examples.extend(ex)
        sources.append(f"{name}: {len(ex)}")
        print(f"  {name}: {len(ex)} examples")

    _add("edges", _edge_qa, edges, entities_by_id)
    _add("decode keys", _decode_qa, keys)
    _add("entities", _entity_qa, entities, degree)
    _add("lineage", _lineage_qa, edges, entities_by_id)
    _add("multi-hop", _multi_hop_qa, entities, edges, degree, entities_by_id)

    # Shuffle and split 90/10
    random.shuffle(all_examples)
    split = int(len(all_examples) * 0.9)
    train, val = all_examples[:split], all_examples[split:]

    def _write(path, data):
        with open(path, "w", encoding="utf-8") as f:
            for ex in data:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    train_path = os.path.join(out_dir, "train.jsonl")
    val_path = os.path.join(out_dir, "val.jsonl")
    _write(train_path, train)
    _write(val_path, val)

    print(f"\nTotal: {len(all_examples)} examples")
    print(f"Train: {len(train)} → {train_path}")
    print(f"Val:   {len(val)} → {val_path}")

    return _envelope(True, {
        "train_examples": len(train),
        "val_examples": len(val),
        "sources": sources,
    }, {}, [])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    env = run(out_dir=a.out, seed=a.seed)
    if a.json:
        print(json.dumps(env, ensure_ascii=False))
    else:
        d = env["data"] or {}
        print(f"\nDone: {d['train_examples']} train + {d['val_examples']} val")
        for s in d.get("sources", []):
            print(f"  {s}")
