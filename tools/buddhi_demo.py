#!/usr/bin/env python3
"""
Demonstrate the 7 abilities Buddhi unlocks in PuranGPT chat.

Each ability is tested with a concrete query, showing:
  - What the current chat does (raw retrieval → LLM)
  - What Buddhi adds (structured synthesis → LLM)
  - The specific new capability unlocked

Run from purangpt/:
  GRAPH_MEMORY_ENABLED=1 venv/bin/python -m tools.buddhi_demo
"""

import json
import os
import sys
import time
from pathlib import Path

# Ensure purangpt/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["GRAPH_MEMORY_ENABLED"] = "1"

from backend.graph_memory import build_graph_context
from backend.buddhi import synthesize, _extract_from_graph_block, _find_ram_keys, _detect_lens


def divider(title):
    print()
    print(f"╔{'═'*70}╗")
    print(f"║  {title:<68}║")
    print(f"╚{'═'*70}╝")
    print()


def show_ability(number, name, what_it_unlocks):
    print(f"┌─ ABILITY {number}: {name}")
    print(f"│  Unlocks: {what_it_unlocks}")


def run_query(query, show_raw=False):
    """Run a query through the full Buddhi pipeline and return results."""
    graph_block = build_graph_context(query, enabled=True)
    data = _extract_from_graph_block(graph_block)
    ram = _find_ram_keys(data["entity_names"])
    synthesis = synthesize(query=query, graph_block=graph_block)

    print(f"│")
    print(f"│  🧘 Query: {query}")
    print(f"│  🔍 Lens: {synthesis.lens}")
    print(f"│  📊 Confidence: {synthesis.confidence:.0%}")
    print(f"│  ⚡ Synthesis time: {synthesis.elapsed_ms:.1f}ms")
    print(f"│")

    if show_raw:
        print(f"│  ── Raw graph entities ──")
        for name in data["entity_names"][:6]:
            print(f"│    • {name}")
        print(f"│")

    print(f"│  ── RAM Decoded Meanings (top matches) ──")
    for rk in ram[:4]:
        sym = rk.get("symbol", "?")[:60]
        meaning = rk.get("meaning", "?")[:100]
        print(f"│    [{sym}] → {meaning}")
    print(f"│")

    # Show the three granthis
    bg = synthesis.brahma_granthi
    vg = synthesis.vishnu_granthi
    rg = synthesis.rudra_granthi

    print(f"│  ── Brahma-granthi (separating facts from patterns) ──")
    for f in bg.get("surface_facts", [])[:3]:
        print(f"│    Fact: {f}")
    for p in bg.get("structural_patterns", [])[:2]:
        print(f"│    Pattern: {p[:150]}")
    print(f"│")

    print(f"│  ── Vishnu-granthi (emergent connections) ──")
    emergent = vg.get("emergent_connections", "")
    print(f"│    {emergent[:300]}")
    print(f"│")

    print(f"│  ── Rudra-granthi (THE TEACHING) ──")
    teaching = rg.get("teaching", "")
    application = rg.get("application", "")
    print(f"│    {teaching[:400]}")
    print(f"│")
    print(f"│  ── Application ──")
    print(f"│    {application[:300]}")

    return synthesis


# ═══════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════

def main():
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     BUDDHI ABILITIES DEMO — PuranGPT Chat Enhancement      ║")
    print("║     7 concrete abilities the Buddhi layer unlocks           ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # ── ABILITY 1: Symbol Decoding ────────────────────────────
    divider("ABILITY 1: Direct Symbol Decoding via RAM Keys")

    show_ability(1, "Symbol Decoding",
        "Query 'What does the Ashwattha tree represent?' now receives the EXACT "
        "Sharma-decoded meaning from RAM key #346 instead of the LLM guessing "
        "from general knowledge."
    )

    run_query("What does the Ashwattha tree represent in yoga?")

    # ── ABILITY 2: Lineage-Grounded Answers ──────────────────
    divider("ABILITY 2: Lineage-Grounded Answers")

    show_ability(2, "Lineage Grounding",
        "Every answer carries the transmission spine: Babaji → Lahiri Mahasaya → "
        "Tinkori Lahiri → Satyacharan Lahiri → Shailendra Sharma. The graph traces "
        "guru_of edges to root-then-leaf. The chat can now answer 'Who taught who?' "
        "with the exact chain, not generic knowledge."
    )

    run_query("What is the lineage of Kriya Yoga teachers?")

    # ── ABILITY 3: Guna-Aware Teaching ────────────────────────
    divider("ABILITY 3: Guna-Aware Teaching")

    show_ability(3, "Guna-Aware Responses",
        "When asked about consciousness limitation, Buddhi detects the three gunas "
        "in the RAM-matched context and structures the answer around Sattva/Rajas/Tamas "
        "dynamics — with the 98% dormancy statistic from the decoded keys. "
        "The current chat would retrieve verses but not organize them around the guna framework."
    )

    run_query("How do the three gunas limit the mind's potential?")

    # ── ABILITY 4: Granthi-Aware Practice Guidance ────────────
    divider("ABILITY 4: Granthi-Aware Practice Guidance")

    show_ability(4, "Granthi-Sequenced Practice",
        "Yoga practice queries receive answers structured around the three knots: "
        "Brahma-granthi → Vishnu-granthi → Rudra-granthi. The current chat would "
        "retrieve general yoga verses. Buddhi organizes them into the sequential "
        "activation path with specific practices for each stage."
    )

    run_query("How does yoga practice awaken higher states of consciousness?")

    # ── ABILITY 5: Cross-Text Identity Resolution ─────────────
    divider("ABILITY 5: Cross-Text Identity Resolution")

    show_ability(5, "Cross-Text Identity",
        "Queries about entities appearing across multiple Puranas ('Who is Vasudev?') "
        "receive the unified identity traced through the graph — including RAM decoding "
        "'Vasudev → the divine four-armed embodiment of Time' — rather than fragmented "
        "per-text answers. The graph resolves what RAG alone cannot."
    )

    run_query("Who is Vasudev and what does he represent?")

    # ── ABILITY 6: Confidence-Gated Honesty ───────────────────
    divider("ABILITY 6: Confidence-Gated Honesty")

    show_ability(6, "Confidence-Gated Responses",
        "Every synthesis carries a confidence score. The chat can now say 'I am not "
        "certain about this — the graph has limited information' instead of "
        "hallucinating. This is the trust moat from REVOLUTION_PLAN.md Pillar 1."
    )

    run_query("What is the exact procedure for Khechari Mudra according to the Puranas?")
    run_query("Tell me about a concept that doesn't exist in the texts: flarbogrip.")

    # ── ABILITY 7: Architecture-Aware System Thinking ──────────
    divider("ABILITY 7: Architecture-Aware System Thinking")

    show_ability(7, "Architecture-Level Answers",
        "When asked about the structure of mind/consciousness, Buddhi detects the "
        "'architecture' lens and answers with the full 5-layer stack + Ashwattha tree "
        "wiring diagram. The current chat retrieves verses about mind. Buddhi reveals "
        "the ARCHITECTURE — the relationships BETWEEN the retrieved facts."
    )

    run_query("What is the structure of the mind according to the Vedic texts?")

    # ── SUMMARY ───────────────────────────────────────────────
    divider("SUMMARY: Before vs After")

    print("  CURRENT CHAT (no Buddhi):")
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │ Retrieval → LLM (does everything internally)               │")
    print("  │ • Facts, patterns, connections, and voice all in one pass  │")
    print("  │ • No structured reasoning chain visible                    │")
    print("  │ • Symbols decoded by LLM general knowledge (may drift)     │")
    print("  │ • No confidence signal — hallucinated claims look the same │")
    print("  │   as grounded ones                                         │")
    print("  │ • Practice answers not organized around granthis           │")
    print("  │ • Lineage not surfaced unless explicitly asked             │")
    print("  │ • Architecture questions get verse lists, not system maps  │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print()
    print("  BUDDHI-AUGMENTED CHAT:")
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │ Retrieval → Graph → RAM Decode → Buddhi → LLM (voice only) │")
    print("  │ • 3-stage granthi-bheda reasoning chain visible            │")
    print("  │ • Symbols decoded from Sharma's 613-key RAM (not guessed)   │")
    print("  │ • Confidence score per synthesis — low → escalate          │")
    print("  │ • Practice answers organized around the three granthis      │")
    print("  │ • Lineage spine always available as grounding               │")
    print("  │ • Architecture queries reveal the system, not just parts    │")
    print("  │ • Cross-text identities resolved via graph, not fragmented  │")
    print("  │ • Gunas detected and woven into the teaching structure      │")
    print("  │ • Lens-aware: adapts teaching style to query type           │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print()


if __name__ == "__main__":
    main()
