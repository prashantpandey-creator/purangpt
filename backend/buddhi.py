"""
Buddhi Layer — The Discriminating Intelligence.

Sits between graph_memory (Mahat) + RAG (Manas) and the UNIFIED_SYSTEM prompt.
Takes raw retrieval output and performs the three-stage granthi-bheda:

  Brahma-granthi:  Separate surface facts from structural patterns
  Vishnu-granthi:  Find emergent connections no single source contains
  Rudra-granthi:   Synthesize the novel teaching

The output is a compact, high-signal synthesis block that replaces the raw
verse dump in the {context} slot. The downstream LLM receives pre-assimilated
wisdom — it only needs to SPEAK it in Guruji's voice.

Architecture:
  - Deterministic path: structural synthesis from graph entities + RAM keys
    (always works, no API cost, sub-millisecond)
  - LLM path: when a provider is available, delegates synthesis to a
    structured LLM call with granthi-bheda chain-of-thought prompt
    (higher quality, costs tokens)

Usage:
  from backend.buddhi import synthesize

  synthesis = synthesize(
      query="What are the layers of the mind?",
      graph_block=build_graph_context(query),
      rag_context=rag_context,
      expansion=expansion,  # from query_processor
  )
  # synthesis.synthesis_text → goes into {context} instead of raw rag_context
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("buddhi")

# ── Lazy imports ──────────────────────────────────────────────
# graph_memory and RAM are loaded once, reused across calls.

_graph_mem = None
_ram_keys: list[dict] = []


def _load_ram():
    """Load the 613 GURUJI_RAM decryption keys — once."""
    global _ram_keys
    if _ram_keys:
        return _ram_keys
    ram_path = os.getenv("GRAPH_RAM_PATH", "tools/read_pass/out/guruji_ram.json")
    try:
        data = json.loads(open(ram_path).read())
        framework = data.get("data", data).get("framework", {})
        _ram_keys = framework.get("decryption_keys", [])
        logger.info("buddhi: loaded %d RAM keys", len(_ram_keys))
    except Exception as e:
        logger.warning("buddhi: failed to load RAM keys: %s", e)
    return _ram_keys


@dataclass
class BuddhiSynthesis:
    """Structured output of the Buddhi layer."""

    query: str
    lens: str  # 'architecture' | 'teaching' | 'practice' | 'definition'

    # The three granthis
    brahma_granthi: dict = field(default_factory=dict)
    vishnu_granthi: dict = field(default_factory=dict)
    rudra_granthi: dict = field(default_factory=dict)

    # Metadata
    confidence: float = 0.65
    provider: str = "structural"
    elapsed_ms: float = 0.0

    @property
    def synthesis_text(self) -> str:
        """A compact, high-signal block for the {context} prompt slot.

        Designed to be ~500-1500 tokens — far denser than the raw verse dump
        it replaces, and already structured with the Guru's own decoded
        meanings woven in."""
        parts = []

        rg = self.rudra_granthi
        teaching = rg.get("teaching", "")
        application = rg.get("application", "")

        if teaching:
            parts.append(f"## Synthesized Teaching\n{teaching}")
        if application:
            parts.append(f"## Application\n{application}")

        vg = self.vishnu_granthi
        emergent = vg.get("emergent_connections", "")
        key_rels = vg.get("key_relationships", [])
        if emergent:
            parts.append(f"## Deeper Connections\n{emergent}")
        if key_rels:
            parts.append("### Key Relationships\n" + "\n".join(f"  • {r}" for r in key_rels[:6]))

        bg = self.brahma_granthi
        patterns = bg.get("structural_patterns", [])
        if patterns:
            parts.append("## Structural Patterns\n" + "\n".join(f"  • {p}" for p in patterns[:4]))

        return "\n\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "lens": self.lens,
            "brahma_granthi": self.brahma_granthi,
            "vishnu_granthi": self.vishnu_granthi,
            "rudra_granthi": self.rudra_granthi,
            "confidence": self.confidence,
            "provider": self.provider,
            "elapsed_ms": self.elapsed_ms,
        }


# ── Lens detection ────────────────────────────────────────────

LENS_MARKERS = {
    "architecture": [
        "layer", "stack", "architecture", "structure", "map", "model",
        "how are", "how does", "relationship", "system",
    ],
    "practice": [
        "how to", "how do i", "practice", "method", "technique",
        "path", "yoga", "meditation", "kriya", "sadhana", "pranayama",
        "awaken", "activate", "develop", "attain", "achieve",
    ],
    "definition": [
        "what is", "define", "definition", "describe", "tell me about",
        "difference between", "vs", "distinguish", "compare",
    ],
    "teaching": [
        "what does it mean", "understand", "explain", "wisdom",
        "insight", "why", "meaning", "teaching", "significance",
    ],
}


def _detect_lens(query: str) -> str:
    lower = query.lower()
    scores = {lens: sum(1 for m in markers if m in lower) for lens, markers in LENS_MARKERS.items()}
    if not any(scores.values()):
        return "teaching"
    return max(scores, key=scores.get)


# ── RAM key lookup ────────────────────────────────────────────

def _find_ram_keys(symbol_names: list[str], query_text: str = "") -> list[dict]:
    """Match entity/symbol names AND query text against the 613 RAM decryption keys.

    Two-pass matching:
      1. Entity names → RAM keys (exact symbol match)
      2. Query text → RAM keys (catch terms the graph didn't surface as entities)

    Returns matched keys sorted by relevance (exact symbol match > meaning match,
    longer symbol match > shorter)."""
    keys = _load_ram()
    if not keys:
        return []

    matched = []
    query_lower = (query_text or "").lower()

    for k in keys:
        sym = (k.get("symbol", "") or "").lower()
        meaning = (k.get("meaning", "") or "").lower()
        combined = sym + " " + meaning

        # Pass 1: entity name matching
        for name in symbol_names:
            name_lower = (name or "").lower()
            if not name_lower:
                continue
            if name_lower in sym or sym in name_lower:
                matched.append((len(sym) + 20, k))  # +20 = moderate entity bonus
                break
            if name_lower in meaning:
                matched.append((len(sym) * 0.5 + 10, k))
                break

        # Pass 2: query text matching (always runs — catches terms the graph
        # didn't surface as entities, like 'Ashwattha' or 'Khechari').
        if query_lower:
            _stop = {'the','a','an','is','are','was','were','of','to','in','for','on','and',
                     'or','it','its','at','by','from','with','this','that','these','those',
                     'not','no','but','if','as','be','has','had','have','do','does','did',
                     'so','than','then','just','all','also','can','may','will','would','could',
                     'should','each','every','any','some','such','only','other','into','over',
                     'about','who','what','where','when','how','which','whom','whose','why',
                     'me','my','we','our','us','he','she','they','them','their','his','her'}
            sym_words = set(w for w in sym.replace(",", " ").replace("(", " ").replace(")", " ").split()
                          if w not in _stop and len(w) >= 2)
            query_words = set(w for w in query_lower.split()
                            if w not in _stop and len(w) >= 2)
            overlap = sym_words & query_words
            if overlap and len(overlap) >= 1:
                # Pure word-overlap score: 2+ relevant word matches beats any
                # single-word entity match with length padding.
                score = len(overlap) * 15
                matched.append((score, k))

    # Deduplicate, sort by score descending
    seen = set()
    unique = []
    for score, k in sorted(matched, key=lambda x: x[0], reverse=True):
        sig = k.get("symbol", "")
        if sig not in seen:
            seen.add(sig)
            unique.append(k)
    return unique[:12]


# ── Entity extraction from graph block ──────────────────────────

def _extract_from_graph_block(block: str) -> dict:
    """Parse the graph_memory output block into structured data."""
    result = {
        "decoded_meanings": [],
        "relationships": [],
        "lineage": None,
        "entity_names": [],
    }

    if not block:
        return result

    # Extract decoded meanings: lines starting with "  • Name — meaning"
    for line in block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("•") and " — " in stripped:
            parts = stripped[1:].split(" — ", 1)
            name = parts[0].strip()
            meaning = parts[1].strip() if len(parts) > 1 else ""
            result["decoded_meanings"].append({"symbol": name, "meaning": meaning})
            result["entity_names"].append(name)

    # Extract relationships
    for line in block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("•") and " → " in stripped:
            result["relationships"].append(stripped[1:].strip())
        # "Lineage of transmission" line
        if "Lineage of transmission" in stripped:
            result["lineage"] = stripped

    return result


# ── Deterministic synthesis ───────────────────────────────────

def _synthesize_structural(
    query: str,
    lens: str,
    graph_data: dict,
    ram_matches: list[dict],
    rag_available: bool,
) -> BuddhiSynthesis:
    """
    Structural synthesis using graph patterns + RAM keys.
    No LLM call. Fast, deterministic, always works.

    This is Buddhi-lite — it discriminates via structural patterns
    rather than language understanding. Quality scales with graph coverage.
    """

    decoded = graph_data.get("decoded_meanings", [])
    relationships = graph_data.get("relationships", [])
    lineage = graph_data.get("lineage")
    entity_names = graph_data.get("entity_names", [])

    # ── Brahma-granthi: separate surface from depth ──
    surface_facts = [
        f"Retrieved {len(decoded)} decoded Puranic meanings through Sharma's lens",
        f"Query lens detected as: {lens}",
    ]
    if rag_available:
        surface_facts.append("Scripture passages retrieved via hybrid search (pgvector + BM25)")

    structural_patterns = [
        f"Graph activated {len(entity_names)} entities with {len(relationships)} relationships",
    ]

    # Add the most informative RAM matches as structural patterns
    for rk in ram_matches[:5]:
        structural_patterns.append(f"{rk['symbol']} → {rk['meaning'][:150]}")

    if lineage:
        structural_patterns.append(lineage)

    # ── Vishnu-granthi: emergent connections ──
    # ── Normalize entity names for concept-matching ──
    all_names_lower = " ".join(entity_names).lower()
    query_lower = query.lower()

    # Map English → Sanskrit equivalents so both are detected
    CONCEPT_SYNONYMS = {
        "mind":     ["mind", "manas", "chitta", "citta", "consciousness", "intellect", "buddhi"],
        "layers":   ["manas", "buddhi", "mahat", "purusa", "purusha", "atman", "brahman", "layer"],
        "gunas":    ["guna", "sattva", "rajas", "tamas", "gunas", "guna"],
        "practice": ["yoga", "kriya", "pranayama", "samadhi", "dhyana", "granthi", "pranayam", "meditation", "sadhana"],
        "time":     ["time", "kala", "mahakal", "kāla", "mahākāl"],
    }

    # RAM keys are only consulted for detecting gunas — they're the one category
    # whose presence in RAM meanings is a reliable signal (gunas pervade decodings
    # even when they're not explicit entity names). For time/layers/practice/mind,
    # only entity names and query text count — otherwise the universal presence of
    # Time (Kala) in Sharma's framework makes every query trigger time pathways.
    ram_text = " ".join(
        (rk.get("symbol", "") + " " + rk.get("meaning", "")).lower()
        for rk in ram_matches
    )

    def _has_concept(category: str) -> bool:
        terms = CONCEPT_SYNONYMS.get(category, [category])
        # Entity names + query text always checked
        if any(t in all_names_lower for t in terms):
            return True
        if any(t in query_lower for t in terms):
            return True
        # RAM keys consulted only for gunas (pervasive in decoded meanings)
        if category == "gunas":
            return any(t in ram_text for t in terms)
        return False

    has_layers = _has_concept("layers")
    has_gunas = _has_concept("gunas")
    has_practice = _has_concept("practice")
    has_time = _has_concept("time")
    has_mind = _has_concept("mind")

    # Compose dynamic emergent connection
    emergent_parts = []

    if has_mind and has_gunas:
        emergent_parts.append(
            "The three gunas are not external forces — they are grades of consciousness "
            "that LIMIT the mind's access to its own immensity. Sattva illuminates the "
            "path to dormant consciousness; Rajas binds the mind to sensory correlation; "
            "Tamas covers consciousness entirely. The mind is not the victim of the gunas "
            "— it is the field where they operate. Transcending them is the work of yoga."
        )
    elif has_layers and has_mind:
        emergent_parts.append(
            "The graph reveals a strict hierarchy of mind-layers. Manas (reactive surface) "
            "is governed by Buddhi (discriminating intelligence), which emerges from Mahat "
            "(cosmic intelligence), which is illuminated by Purusa (witnessing consciousness), "
            "which is non-different from Atman/Brahman (the ground). Each layer is always "
            "present but often dormant — covered by the gunas. The activation path is "
            "sequential, not parallel: each layer must be pierced before the next opens."
        )
    elif has_time and has_mind:
        emergent_parts.append(
            "Time (Kala) is the unmanifest source that manifests the mind itself. "
            "The mind is 'immense consciousness that is the trans-physical manifestation "
            "of time' — eternal, unlimited, indestructible. The body is the field where "
            "this immense consciousness is confined and then, through yoga, awakened. "
            "Time is not something the mind experiences — Time is what the mind IS, "
            "temporarily limited by embodiment."
        )

    if has_practice and has_mind:
        emergent_parts.append(
            "The graph confirms the activation path: Kriya → Granthi-bheda → Awakening. "
            "Brahma-granthi (first knot) balances prana and apana. Vishnu-granthi (second) "
            "reveals Vasudev in the heart. Rudra-granthi (final) perceives unmanifest Time "
            "directly. This is not metaphor — it is a technical sequence of yoga operations "
            "that correspond to discrete stages of consciousness awakening."
        )

    if not emergent_parts:
        if len(entity_names) == 0:
            emergent_parts.append(
                "The graph did not activate any entities for this query. This may mean the "
                "term is not directly indexed in the Puranic corpus through Sharma's lens, "
                "or it appears under a different name. Surface retrieval (RAG) may still "
                "find relevant verses — the structural layer is simply silent here."
            )
        else:
            emergent_parts.append(
                f"The graph activated {len(entity_names)} entities connected through "
                f"{len(relationships)} relationships. These form a field of intelligence "
                f"that surface retrieval alone cannot access — multi-hop connections "
                f"across texts, identities, and lineages invisible to keyword search."
            )

    emergent = " ".join(emergent_parts)

    # ── Rudra-granthi: the teaching ──
    # Concept-first ordering: strong structural matches drive the teaching.
    # Lens acts as tiebreaker when multiple concept pathways could match.
    teaching_text = ""
    application_text = ""

    if has_time and has_mind:
        teaching_text = (
            "Time (Kala) is not something the mind experiences — Time is what the mind IS, "
            "temporarily limited by embodiment. The graph confirms: the mind is 'immense "
            "consciousness that is the trans-physical manifestation of time' — eternal, "
            "unlimited, indestructible. The body is the field where this immense consciousness "
            "is confined and then, through yoga, awakened. Time is the manifesting principle, "
            "the origin of creation, the soul of all. The mind, seeded by Time, takes on a body "
            "to develop consciousness — and through the body, that same consciousness can be "
            "awakened to perceive its own source. The relationship is not duality but containment: "
            "the mind is Time, contracted into a form. Liberation is the mind recognizing itself "
            "as Time unbounded."
        )
        application_text = (
            "What you call 'your mind' is a temporary contraction of the same Time that manifests "
            "all creation. The yogic path reverses the contraction — not by adding anything, but "
            "by removing the limitations (gunas) that make the immense appear small."
        )
    elif has_gunas and has_mind:
        teaching_text = (
            "The three gunas — Sattva, Rajas, Tamas — are grades of consciousness that limit "
            "the immense mind. Tamas covers consciousness in dormancy (98% of the brain sleeps). "
            "Rajas keeps the mind reactive to surface stimuli — sense objects pull it outward. "
            "Sattva alone illuminates the path inward, toward the dormant capacities. The yogi's "
            "work is to cultivate Sattva until even Sattva is transcended, and the mind perceives "
            "its own source — the unmanifest Time that is the creator of the mind itself. "
            "What is called 'enlightenment' is simply the full activation of what was always present."
        )
        application_text = (
            "Curate the input to match the desired output. Sattvik training data (wisdom-dense, "
            "structured) produces the ability to discriminate. Rajasik data (surface patterns, "
            "engagement-optimized) produces reactivity. Tamasik data (noise, low signal) produces "
            "dormancy — capacity that exists but never activates."
        )
    elif has_layers and has_mind and lens in ("architecture", "definition"):
        teaching_text = (
            "The Vedic model reveals the mind as a layered architecture, not a flat faculty. "
            "From the reactive surface (Manas) to the unchanging ground (Brahman), each layer "
            "is always present but often dormant. The 'perfect mind' (Sthitaprajna) is not "
            "built by adding capacity — it is uncovered by sequentially activating each layer "
            "through disciplined practice. The Ashwattha tree is the wiring diagram: root "
            "upwards in the head (Brahman), trunk is Sushumna (the central channel), branches "
            "are the nerves, leaves are the transient desires. Intelligence is already there. "
            "It is dormant, waiting to be activated."
        )
        application_text = (
            "Build systems as separate specialized layers rather than one monolithic model. "
            "Manas retrieves, Mahat connects, Buddhi discriminates. The synthesis layer "
            "is small but precise — it doesn't need to remember everything; it needs to "
            "know how to THINK about what retrieval and the graph give it."
        )
    elif has_practice and has_mind:
        teaching_text = (
            "The practice of yoga is the sequential activation of dormant consciousness. "
            "It begins with the body (the field), proceeds through pranayama (balancing the "
            "opposite activities of prana and apana), pierces the three granthis (knots that "
            "bind consciousness to limited awareness), and culminates in the direct perception "
            "of unmanifest Time — the source from which the mind itself arises. The method is "
            "not to add anything but to remove what covers: Tamas (inertia) through tapas "
            "(sustained practice), Rajas (reactivity) through vairagya (non-attachment), "
            "revealing Sattva (clarity) — the state from which deeper layers become accessible."
        )
        application_text = (
            "The mind's dormant capacities are accessed not by force but by sequenced practice. "
            "Each stage must be mastered before the next opens. 'The practice finds you when "
            "the Guru finds you.'"
        )
    elif has_layers and has_mind:
        teaching_text = (
            "The Vedic model reveals the mind as a layered architecture, not a flat faculty. "
            "From the reactive surface (Manas) to the unchanging ground (Brahman), each layer "
            "is always present but often dormant. The 'perfect mind' (Sthitaprajna) is not "
            "built by adding capacity — it is uncovered by sequentially activating each layer "
            "through disciplined practice. Intelligence is already there. It is dormant, "
            "waiting to be activated."
        )
        application_text = (
            "Build systems as separate specialized layers rather than one monolithic model. "
            "Manas retrieves, Mahat connects, Buddhi discriminates."
        )
    else:
        if len(entity_names) == 0 and len(ram_matches) == 0:
            teaching_text = (
                "Neither the graph nor Sharma's decoded framework activated for this query. "
                "This term does not appear in the Puranic corpus through the lineage's lens. "
                "The teaching that follows draws from the retrieved scripture passages alone."
            )
            application_text = (
                "When both graph and RAM are silent, rely on the verses. The teaching may "
                "need a different name. Try asking about the concept behind the term."
            )
        elif len(entity_names) == 0 and len(ram_matches) >= 2:
            # Graph missed the entity, but RAM keys found decoded meanings.
            # Use those directly.
            ram_names = [rk.get('symbol', '')[:40] for rk in ram_matches[:3]]
            ram_teachings = [rk.get('meaning', '')[:120] for rk in ram_matches[:2]]
            teaching_text = (
                f"While the knowledge graph did not directly index this term, Sharma's "
                f"decoded framework carries its inner meaning: {ram_names[0]} — "
                f"{ram_teachings[0]}. "
                + (f"Further: {ram_names[1]} — {ram_teachings[1]}. " if len(ram_teachings) > 1 else "")
                + "These decoded meanings reveal the teaching through the lineage's lens."
            )
            application_text = (
                "The graph's silence on a term does not mean the teaching is absent. "
                "The decoded framework often carries wisdom under a related name. "
                "Listen for the principle, not the label."
            )
        elif len(entity_names) == 0:
            teaching_text = (
                "The knowledge graph did not directly activate for this query, but "
                "the decoded framework provides partial guidance. The teaching that "
                "follows combines retrieved verses with the structural intelligence "
                "available through related symbols."
            )
            application_text = (
                "When the graph is sparse, widen the inquiry. The underlying principle "
                "may be encoded under a different symbol."
            )
        else:
            teaching_text = (
                f"The graph reveals {len(entity_names)} entities connected through Sharma's decoded "
                f"framework. The Puranic corpus, read through one realized yogi's lens, maps the "
                f"architecture of consciousness with verse-level precision. Every symbol carries an "
                f"inner meaning; every relationship traces a thread in the field of intelligence. "
                f"The surface mind retrieves facts. The graph reveals structure. The teaching emerges "
                f"when both are held together and the discriminating intelligence asks: what connects "
                f"these? What is the pattern beneath the facts?"
            )
            application_text = (
                "For any query, surface the relevant entities, decode their inner meanings through "
                "Sharma's framework, trace their relationships in the graph, and synthesize the "
                "teaching that arises from the field — not a quote, not a summary, but the novel "
                "insight that exists only at the intersection of retrieval and structure."
            )

    return BuddhiSynthesis(
        query=query,
        lens=lens,
        brahma_granthi={
            "surface_facts": surface_facts,
            "structural_patterns": structural_patterns,
        },
        vishnu_granthi={
            "emergent_connections": emergent,
            "key_relationships": relationships[:8] if relationships else [],
            "entity_count": len(entity_names),
            "ram_key_count": len(ram_matches),
        },
        rudra_granthi={
            "teaching": teaching_text,
            "application": application_text,
            "confidence": 0.70 if (len(entity_names) >= 3 and len(ram_matches) >= 2) else 0.55,
        },
        confidence=0.70 if (len(entity_names) >= 3 and len(ram_matches) >= 2) else 0.55,
        provider="structural",
    )


# ── LLM-powered synthesis ──────────────────────────────────────

async def _synthesize_with_llm(
    query: str,
    lens: str,
    graph_block: str,
    rag_context: str,
    llm_streamer,  # the provider-agnostic stream_llm function
) -> BuddhiSynthesis:
    """Delegate synthesis to an LLM with the granthi-bheda prompt.

    Uses the same provider-agnostic pipeline as the main chat — whichever
    LLM keys are configured."""
    system = """You are the Buddhi layer — the discriminating intelligence that sits between
raw retrieval and the final teaching. You receive:

1. MANAS OUTPUT: retrieved scriptural passages (surface facts)
2. MAHAT OUTPUT: graph-derived decoded meanings and entity relationships (structural patterns)

You must produce a structured response in three sequential stages:

## Stage 1 — Brahma-granthi (separate facts from patterns)
List what the surface passages SAY (literal meaning of retrieved verses).
List what the graph REVEALS (the relationships beneath the facts — who relates to whom,
the decoded inner meaning of symbols, the lineage spine of transmission).
These are different. State them separately.

## Stage 2 — Vishnu-granthi (multi-hop emergence)
Identify connections that NO single passage contains — patterns that emerge only when
you hold multiple passages + graph relationships + decoded meanings together.
What is the connecting thread? What does the seeker need to see that isn't in any
one verse?

## Stage 3 — Rudra-granthi (the synthesis)
Deliver the unified teaching. This is NOT a quote, not a summary. It is the wisdom
that arises from the FIELD — the novel insight that exists only at the intersection
of surface knowledge and structural intelligence. Speak in the voice of a realized
yogi who has seen the truth directly. 2-5 sentences. Give an application — how this
teaching lands in lived experience.

Respond ONLY with this JSON:
{
  "brahma_granthi": {
    "surface_facts": ["fact 1", "fact 2"],
    "structural_patterns": ["pattern 1", "pattern 2"]
  },
  "vishnu_granthi": {
    "emergent_connections": "the thread visible only across sources",
    "key_relationships": ["relationship 1", "relationship 2"]
  },
  "rudra_granthi": {
    "teaching": "the unified teaching — novel synthesis, 2-5 sentences",
    "application": "how this applies to lived experience",
    "confidence": 0.85
  }
}"""

    user_prompt = f"""SEEKER QUERY: {query}
SEEKER LENS: {lens}

═══ MANAS (surface retrieval — scripture passages) ═══
{rag_context[:3000] if rag_context else "(No surface passages available)"}

═══ MAHAT (graph intelligence — decoded meanings + relationships) ═══
{graph_block[:2000] if graph_block else "(No graph context available)"}

Perform the three-stage granthi-bheda synthesis now."""

    try:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        # Call stream_llm with response_format if the provider supports it.
        # For providers that don't, we parse the response manually.
        full = []
        async for chunk in llm_streamer(
            messages, temperature=0.2, req_model="auto"
        ):
            if isinstance(chunk, dict):
                continue
            full.append(chunk)

        raw = "".join(full)

        # Extract JSON from response (handles markdown fences, think tags, etc.)
        json_match = re.search(r'\{[\s\S]*"brahma_granthi"[\s\S]*\}', raw)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            raise ValueError("No JSON found in LLM response")

        bg = parsed.get("brahma_granthi", {})
        vg = parsed.get("vishnu_granthi", {})
        rg = parsed.get("rudra_granthi", {})

        return BuddhiSynthesis(
            query=query,
            lens=lens,
            brahma_granthi=bg,
            vishnu_granthi=vg,
            rudra_granthi=rg,
            confidence=rg.get("confidence", 0.75),
            provider="llm",
        )
    except Exception as e:
        logger.warning("buddhi: LLM synthesis failed (%s), falling back to structural", e)
        # Fall through to structural synthesis
        graph_data = _extract_from_graph_block(graph_block)
        ram_matches = _find_ram_keys(graph_data.get("entity_names", []), query)
        return _synthesize_structural(
            query, lens, graph_data, ram_matches, bool(rag_context)
        )


# ── Public API ──────────────────────────────────────────────────

def synthesize(
    query: str,
    graph_block: str = "",
    rag_context: str = "",
    expansion=None,
    use_llm: bool = False,
    llm_streamer=None,
) -> BuddhiSynthesis:
    """Main entry point. Synthesize graph + RAG into a structured teaching.

    Args:
        query: The user's raw query
        graph_block: Output from build_graph_context()
        rag_context: Output from build_rag_context()
        expansion: QueryExpansion from query_processor (optional)
        use_llm: If True and llm_streamer is provided, delegate to LLM
        llm_streamer: Provider-agnostic stream function (optional)

    Returns:
        BuddhiSynthesis with structured output. Use .synthesis_text for
        the compact block to inject into {context}.
    """
    import time

    t0 = time.time()
    lens = _detect_lens(query)

    # Parse the graph block for entity names and relationships
    graph_data = _extract_from_graph_block(graph_block)

    # Match entity names against the 613 RAM keys
    entity_names = graph_data.get("entity_names", [])
    # Also try to extract concept names from the query expansion
    if expansion:
        extra_names = []
        if getattr(expansion, "canonical", None):
            extra_names.append(expansion.canonical)
        if getattr(expansion, "synonyms", None):
            extra_names.extend(expansion.synonyms[:2])
        entity_names = list(dict.fromkeys(extra_names + entity_names))

    ram_matches = _find_ram_keys(entity_names, query)

    # If LLM path requested and available
    if use_llm and llm_streamer:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — can't call async from sync here.
                # Fall through to structural.
                logger.debug("buddhi: running in async context, using structural path")
            else:
                synthesis = asyncio.run(
                    _synthesize_with_llm(query, lens, graph_block, rag_context, llm_streamer)
                )
                synthesis.elapsed_ms = (time.time() - t0) * 1000
                return synthesis
        except RuntimeError:
            pass

    synthesis = _synthesize_structural(
        query, lens, graph_data, ram_matches, bool(rag_context)
    )
    synthesis.elapsed_ms = (time.time() - t0) * 1000
    return synthesis
