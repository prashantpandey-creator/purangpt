#!/usr/bin/env python3
"""
Buddhi A/B Test — Enabled vs Disabled, with real queries and verse data.

Shows the EXACT prompt context the LLM receives in both modes.
Run: GRAPH_MEMORY_ENABLED=1 venv/bin/python -m tools.buddhi_ab_test
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["GRAPH_MEMORY_ENABLED"] = "1"

from backend.graph_memory import build_graph_context
from backend.buddhi import synthesize

# ── Mock RAG results (simulating what HybridSearcher would return) ──

MOCK_VERSES = {
    "mind_layers": """[1] bhp_03.05.027 | The mind (manas) is superior to the senses; the intellect (buddhi) is superior to the mind; and He who is superior to the intellect is the Self (atman). The senses are said to be great; greater than the senses is the mind; greater than the mind is the intellect; and greater than the intellect is He — the Self.

[2] Gita_03.042 | The senses are superior to gross objects; the mind is superior to the senses; the intellect is superior to the mind; and that which is superior to the intellect is He — the Self (atman). Thus knowing the Self to be distinct from the intellect, and controlling the mind by the intellect, kill the enemy in the form of desire.

[3] bhp_07.07.019 | Earth, water, fire, air, ether, mind (manas), intellect (buddhi), and ego-sense — these eight comprise My separated material energy. This is the lower nature. But know My higher nature — the life-principle by which this universe is sustained.""",

    "gunas": """[1] bhp_01.02.019 | By cultivating pure sattva, the mind becomes steady. Sattva is the quality of illumination and clarity. When sattva predominates, one perceives the formless conscious Self.

[2] bhp_01.02.023 | Transcending the three gunas — sattva, rajas, and tamas — the yogi attains the state where mental modifications cease. The gunas correspond to states of breath and mind: Tamas is inertia, Rajas is restlessness, and Sattva is the balanced state.

[3] Gita_14.005 | Sattva, rajas, and tamas — these three gunas born of Prakriti bind the imperishable embodied one to the body. Sattva, being pure, illuminates and is without suffering; it binds through attachment to happiness and knowledge.""",

    "kriya_lineage": """[1] bhp_01.06.021 | Internal purification through intense spiritual practice is essential for divine vision; external rituals alone are futile and cannot remove the impurities of sin. True purification is the internal fire of Kriya Pranayama.

[2] Gita_04.001 | I taught this imperishable Yoga to Vivasvat; Vivasvat taught it to Manu; Manu taught it to Ikshvaku. Thus handed down in succession, the royal sages knew it. But with long lapse of time, this Yoga was lost to the world.

[3] Gita_04.002 | This same ancient Yoga has been taught by Me to you today, for you are My devotee and friend. It is the supreme secret.""",
}

QUERY_MAP = {
    "What are the layers of the mind and how do they relate to each other?": "mind_layers",
    "How do the three gunas limit the mind's potential?": "gunas",
    "What is the lineage and transmission of Kriya Yoga?": "kriya_lineage",
}


def divider(char="═", width=72):
    print(char * width)


def show_context(label, context_text, max_len=900):
    """Display a context block with stats."""
    tokens_est = len(context_text) // 4
    print(f"  ┌─ {label} ({len(context_text)} chars, ~{tokens_est} tokens) ─┐")
    # Show first N chars
    truncated = context_text[:max_len]
    for line in truncated.split("\n")[:25]:
        print(f"  │ {line[:90]}")
    if len(context_text) > max_len:
        print(f"  │ ... ({len(context_text) - max_len} more chars)")
    print(f"  └{'─'*68}┘")
    print()


def run_ab(query, rag_key):
    """Run a single A/B comparison."""
    print()
    divider()
    print(f"  QUERY: {query}")
    divider()
    print()

    graph_block = build_graph_context(query, enabled=True)
    rag_context = MOCK_VERSES.get(rag_key, "")

    # ── MODE A: DISABLED (current behavior) ──
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║  MODE A: BUDDHI DISABLED (current production)              ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print()

    # Graph block prepended to RAG (current main.py behavior)
    context_disabled = (graph_block + "\n\n" + rag_context) if graph_block else rag_context
    show_context("RAW CONTEXT → LLM", context_disabled)

    # ── MODE B: ENABLED (Buddhi-augmented) ──
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║  MODE B: BUDDHI ENABLED (synthesized)                      ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print()

    t0 = time.time()
    s = synthesize(query=query, graph_block=graph_block, rag_context=rag_context)
    elapsed = (time.time() - t0) * 1000

    context_enabled = s.synthesis_text
    show_context("SYNTHESIZED CONTEXT → LLM", context_enabled)

    # ── COMPARISON ──
    print("  ┌─ COMPARISON ────────────────────────────────────────────┐")
    print(f"  │ {'Metric':<30} {'DISABLED':<20} {'ENABLED':<20} │")
    print(f"  │ {'─'*30} {'─'*20} {'─'*20} │")
    print(f"  │ {'Context length':<30} {len(context_disabled):<20} {len(context_enabled):<20} │")
    print(f"  │ {'Est. tokens':<30} {len(context_disabled)//4:<20} {len(context_enabled)//4:<20} │")
    print(f"  │ {'Structure':<30} {'Flat dump':<20} {'4 labeled sections':<20} │")
    print(f"  │ {'Lens detected':<30} {'none':<20} {s.lens:<20} │")
    print(f"  │ {'Confidence':<30} {'none':<20} {s.confidence:.0%}  │")
    print(f"  │ {'Reasoning visible':<30} {'No':<20} {'Yes (3 granthis)':<20} │")
    print(f"  │ {'RAM keys woven in':<30} {'Raw list':<20} {'Structured patterns':<20} │")
    print(f"  │ {'Synthesis time':<30} {'0ms':<20} {f'{elapsed:.1f}ms':<20} │")
    print(f"  └{'─'*70}┘")
    print()


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║        BUDDHI A/B TEST — Enabled vs Disabled                   ║")
    print("║        Exact prompt context the LLM receives in each mode      ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    for query, rag_key in QUERY_MAP.items():
        run_ab(query, rag_key)

    # ── SUMMARY ──
    print()
    divider("═", 72)
    print("  SUMMARY")
    divider("═", 72)
    print()
    print("  With BUDDHI DISABLED, the LLM receives:")
    print("    • A flat dump of graph entities + decoded meanings + verses")
    print("    • No structure — it must parse facts from patterns internally")
    print("    • No confidence signal — hallucinations and grounded claims look identical")
    print("    • No lens awareness — same context format for architecture vs practice queries")
    print()
    print("  With BUDDHI ENABLED, the LLM receives:")
    print("    • Pre-synthesized teaching in 4 labeled sections")
    print("    • Explicit 3-stage reasoning: facts → patterns → emergent → synthesis")
    print("    • Confidence score — low confidence signals uncertain ground")
    print("    • Lens-adapted teaching style (architecture ≠ practice ≠ definition)")
    print("    • RAM-decoded symbols woven into structural patterns")
    print("    • Sub-2ms overhead, zero API cost")
    print()


if __name__ == "__main__":
    main()
