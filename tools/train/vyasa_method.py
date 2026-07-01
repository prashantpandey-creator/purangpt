"""
Vyasa Method — train a model the way the Puranas were compiled.

Vyasa didn't dump all knowledge at once. He:
  1. COMPILED — gathered dispersed knowledge (the graph does this)
  2. CLASSIFIED — organized by theme, lineage, relationship
  3. TRANSMITTED — structured for precise recitation, not paraphrase
  4. LAYERED — literal → relational → symbolic → esoteric

Applied to ML training:
  Phase 1: MULA (root) — entity facts, direct relationships. Literal truth.
  Phase 2: SAMBANDHA (relation) — multi-hop chains, cross-text identity.
  Phase 3: BHASHYA (interpretation) — decode keys, inner meanings.
  Phase 4: DARSHANA (vision) — synthesis across all layers.

Each phase freezes previous layers (LoRA adapters), building the model
upward the way Vyasa built the corpus — foundation first, depth after.

Usage:
  mlx_lm.lora --model <base> --data tools/train/out/phases/phase1_mula.jsonl --train
  mlx_lm.lora --model <phase1_output> --data phase2_sambandha.jsonl --train
  ...
"""
from __future__ import annotations

import json, os, random, sys, argparse
from pathlib import Path

_HERE = Path(__file__).parent
GRAPH = os.getenv("GRAPH_PATH", "tools/read_pass/out/graph_manifest.json")
RAM   = os.getenv("RAM_PATH",   "tools/read_pass/out/guruji_ram.json")
OUT   = os.getenv("OUT_DIR",    "tools/train/out/phases")

# ── Vyasa's prompt — the model embodies the compiler's voice ──────────────────
VYASA_SYSTEM = """You are Vyasa — the compiler of the Vedas, the arranger of the Mahabharata, the voice of the Puranas. You do not interpret. You do not embellish. You state what is in the texts — exact, bare, precise. Every name you speak is an entity in the graph. Every connection you name is an edge with verse provenance. Every inner meaning is from the Shailendra Sharma lineage decryption. You transmit. Nothing more."""


def _load():
    g = json.load(open(GRAPH, encoding="utf-8"))
    g = g.get("data", g)
    r = json.load(open(RAM, encoding="utf-8"))
    r = r.get("data", r).get("framework", r.get("framework", {}))
    return g["entities"], g["edges"], r.get("decryption_keys", [])


def _to_chatml(user, assistant):
    return {"messages": [
        {"role": "system", "content": VYASA_SYSTEM},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — MULA (Root): Entity facts + direct relationships
# ═══════════════════════════════════════════════════════════════════════════════

def phase1_mula(entities, edges, entities_by_id, degree):
    """Literal truth. Who is X? How is X connected to Y? Exact, cited."""
    examples = []
    seen = set()

    # Entity identity — the most-connected first (Vyasa starts with the central figures)
    sorted_ents = sorted(entities, key=lambda e: degree.get(e["id"], 0), reverse=True)
    for e in sorted_ents[:3000]:
        name = e.get("name", "")
        kind = e.get("kind", "")
        forms = e.get("all_forms", [])[:6]
        if not name or len(name) < 2:
            continue
        kind_str = f" A {kind}." if kind else ""
        forms_str = f" Also named: {', '.join(forms)}." if forms else ""
        answer = f"{name}.{kind_str}{forms_str}"
        examples.append(_to_chatml(f"Who is {name}?", answer))
        examples.append(_to_chatml(f"What is {name} known as?", f"{name} is known as: {', '.join(forms[:5])}." if forms else f"{name}."))

    # Direct relationships — one edge, one fact
    for e in edges:
        s, r, d = e.get("src_name"), e.get("rel"), e.get("dst_name")
        if not s or not r or not d:
            continue
        key = (s, r, d)
        if key in seen or len(seen) > 15000:
            continue
        seen.add(key)
        examples.append(_to_chatml(
            f"How is {s} connected to {d}?",
            f"{s} {r} {d}."
        ))

    return examples


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — SAMBANDHA (Relation): Multi-hop chains + cross-text identity
# ═══════════════════════════════════════════════════════════════════════════════

def phase2_sambandha(entities, edges, entities_by_id, degree):
    """Walk the web. How is X connected to Y through Z?"""
    examples = []

    # Build adjacency for walks
    adj: dict = {}
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        r, sn, dn = e.get("rel", ""), e.get("src_name", ""), e.get("dst_name", "")
        if s and d:
            adj.setdefault(s, []).append((d, r, dn))
            adj.setdefault(d, []).append((s, r, sn))

    # Walk from hub entities
    hubs = [(eid, deg) for eid, deg in degree.items() if deg >= 5]
    random.shuffle(hubs)

    for eid, _ in hubs[:2000]:
        if eid not in adj or len(adj[eid]) < 2:
            continue
        # Two-hop walk
        h1 = random.choice(adj[eid])
        n1_id, r1, n1_name = h1
        if n1_id in adj and adj[n1_id]:
            h2_candidates = [(n, r, nm) for n, r, nm in adj[n1_id] if n != eid]
            if h2_candidates:
                h2 = random.choice(h2_candidates)
                _, r2, n2_name = h2
                e_name = entities_by_id.get(eid, {}).get("name", eid)
                if e_name and n1_name and n2_name:
                    examples.append(_to_chatml(
                        f"Walk the connection from {e_name} to {n2_name}.",
                        f"{e_name} → {r1} → {n1_name} → {r2} → {n2_name}."
                    ))

    # Cross-text identity — same entity, different texts
    for e in entities:
        forms = e.get("all_forms", [])
        name = e.get("name", "")
        chapters = e.get("chapters", [])
        if len(forms) >= 5 and len(set(chapters)) >= 3:
            texts = list(set(c.split(" ")[0] if " " not in c else c for c in chapters))[:4]
            examples.append(_to_chatml(
                f"Which texts mention {name}?",
                f"{name} appears in: {', '.join(texts)}."
            ))

    return examples


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — BHASHYA (Interpretation): Decode keys, inner meanings
# ═══════════════════════════════════════════════════════════════════════════════

def phase3_bhashya(keys):
    """The Sharma lens. What does X really mean?"""
    examples = []
    placeholder = ("not mentioned", "no direct decryption", "no decryption",
                   "not decoded", "n/a", "unknown")
    for k in keys:
        sym = (k.get("symbol") or "").strip()
        meaning = (k.get("meaning") or "").strip()
        if not sym or not meaning or len(sym) < 2:
            continue
        if any(m in meaning.lower() for m in placeholder):
            continue
        examples.append(_to_chatml(
            f"What is the inner meaning of {sym}?",
            f"{sym} — {meaning}"
        ))
        examples.append(_to_chatml(
            f"Decode {sym} through the lineage lens.",
            f"{sym} — {meaning}"
        ))
    return examples


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — DARSHANA (Vision): Synthesis across all layers
# ═══════════════════════════════════════════════════════════════════════════════

def phase4_darshana(entities, edges, keys, entities_by_id, degree):
    """Full vision. The entity, its relationships, and its inner meaning — together."""
    examples = []
    # Build a quick lookup: entity name → decode meaning
    decode_map = {}
    placeholder = ("not mentioned", "no direct decryption", "no decryption",
                   "not decoded", "n/a", "unknown")
    for k in keys:
        sym = (k.get("symbol") or "").strip().lower()
        meaning = (k.get("meaning") or "").strip()
        if sym and meaning and not any(m in meaning.lower() for m in placeholder):
            decode_map[sym] = meaning

    # For central entities (degree >= 50), compose the full picture
    central = [(e, degree.get(e["id"], 0)) for e in entities if degree.get(e["id"], 0) >= 50]
    central.sort(key=lambda x: x[1], reverse=True)

    for e, _ in central[:500]:
        name = e.get("name", "")
        nlower = name.lower()
        kind = e.get("kind", "")
        forms = e.get("all_forms", [])[:5]

        # Find top relationships for this entity
        rels = []
        for ed in edges:
            if ed.get("src_name") == name:
                rels.append(f"{ed['rel']} {ed['dst_name']}")
            elif ed.get("dst_name") == name:
                rels.append(f"{ed['src_name']} {ed['rel']} (incoming)")
            if len(rels) >= 5:
                break

        # Find decode key if one exists
        decode = decode_map.get(nlower, "")

        # Compose the darshana
        parts = [f"{name} is a {kind}."]
        if forms:
            parts.append(f"Also known as: {', '.join(forms)}.")
        if rels:
            parts.append(f"Connected: {'; '.join(rels[:4])}.")
        if decode:
            parts.append(f"Inner meaning: {decode}")

        examples.append(_to_chatml(
            f"Give me the full vision of {name} — identity, connections, and inner meaning.",
            " ".join(parts)
        ))

    return examples


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN — Vyasa compiles
# ═══════════════════════════════════════════════════════════════════════════════

def run(graph_path=GRAPH, ram_path=RAM, out_dir=OUT, seed=108):
    """108 = number of Upanishads. Vyasa's number."""
    random.seed(seed)
    entities, edges, keys = _load()
    os.makedirs(out_dir, exist_ok=True)

    entities_by_id = {e["id"]: e for e in entities}
    degree: dict = {}
    for ed in edges:
        degree[ed.get("src")] = degree.get(ed.get("src"), 0) + 1
        degree[ed.get("dst")] = degree.get(ed.get("dst"), 0) + 1

    print(f"Vyasa compiles from: {len(entities)} entities, {len(edges)} edges, {len(keys)} keys\n")

    phases = [
        ("phase1_mula",      phase1_mula(entities, edges, entities_by_id, degree)),
        ("phase2_sambandha", phase2_sambandha(entities, edges, entities_by_id, degree)),
        ("phase3_bhashya",   phase3_bhashya(keys)),
        ("phase4_darshana",  phase4_darshana(entities, edges, keys, entities_by_id, degree)),
    ]

    total = 0
    for name, examples in phases:
        random.shuffle(examples)
        path = os.path.join(out_dir, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"  {name}: {len(examples)} examples → {path}")
        total += len(examples)

    print(f"\nTotal across all phases: {total}")
    print("Train in order: Mula → Sambandha → Bhashya → Darshana")
    print("Each phase freezes previous layers. The foundation holds the depth.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Vyasa Method — Puranic curriculum learning")
    ap.add_argument("--seed", type=int, default=108)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    run(out_dir=a.out, seed=a.seed)
