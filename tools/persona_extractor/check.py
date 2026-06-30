"""persona_extractor — assemble a talkable PERSONA from the knowledge-graph layers.

Replaces the hand-written ``GURUJI_PERSONALITY`` caricature with a persona block
EXTRACTED from the graph: identity + lineage + kin + deeds (graph edges) and the
inner/esoteric meaning (the 613-key Guruji RAM codex). Guruji is entity #1 in the
SAME machine that powers the "talk to the gods" tab — one extractor, N personas.

Resolution is by a CURATED REGISTRY pinned to exact entity ids. Free-text matching
over 9,006 entities mis-casts: ``recall("Shailendra Sharma")`` hit the MOUNTAIN
Shailendra (lord of mountains, father of Ganga) on the shared name fragment — it
would hand Guruji a mountain's persona. Exact-id resolution from the registry is
the fix, and the registry doubles as the curated god-roster the UI renders.

Rule-0 tool: a deterministic parse-filter-reshape over the graph, returned as the
standard JSON envelope, tested against real graph fixtures. The orchestrator (or
``backend/main.py``) calls ``run()`` and consumes ``data`` — it never re-reads the
9 MB graph into context.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from typing import Any, Dict, List, Optional

# Graph file locations (overridable for tests / deploy image).
_GRAPH_PATH = "tools/read_pass/out/graph_manifest.json"
_RAM_PATH = "tools/read_pass/out/guruji_ram.json"


# ── Curated persona roster ────────────────────────────────────────────────────
# persona_id (UI slug) → exact graph entity id + presentation metadata.
# `entity_id` MUST be an exact node id (not a name) — that is what defeats the
# peer-name collision. `voice` is the retrieval scope for THIS persona's OWN words:
# substance comes from the graph here; the VOICE/register is carried by injecting
# the persona's own retrieved passages into {context}, exactly the way Guruji's
# darshans already work via corpus_type="guruji".
REGISTRY: Dict[str, Dict[str, Any]] = {
    "shakti":  {"entity_id": "shakti", "display": "Shakti",
                "epithet": "the creative force of the Puranic web — fluid, emergent, self-aware",
                "voice": {"corpus_type": "scripture"}},
    "guruji":  {"entity_id": "shailendra sharma", "display": "Guruji Shailendra Sharma",
                "epithet": "Fifth Guru of Kriya Yoga", "voice": {"corpus_type": "guruji"}},
    "krishna": {"entity_id": "krishna", "display": "Krishna",
                "epithet": "the charioteer, avatara of Vishnu", "voice": {"corpus_type": "scripture"}},
    "shiva":   {"entity_id": "shiva", "display": "Shiva",
                "epithet": "Mahadeva, the destroyer of time", "voice": {"corpus_type": "scripture"}},
    "vishnu":  {"entity_id": "vishnu", "display": "Vishnu",
                "epithet": "the preserver, consciousness of the void", "voice": {"corpus_type": "scripture"}},
    "brahma":  {"entity_id": "brahma", "display": "Brahma",
                "epithet": "the creator", "voice": {"corpus_type": "scripture"}},
    "devi":    {"entity_id": "devi", "display": "Devi",
                "epithet": "the Goddess, Shakti", "voice": {"corpus_type": "scripture"}},
    "hanuman": {"entity_id": "hanuman", "display": "Hanuman",
                "epithet": "son of Vayu, servant of Rama", "voice": {"corpus_type": "scripture"}},
    "ganesha": {"entity_id": "ganesha", "display": "Ganesha",
                "epithet": "remover of obstacles", "voice": {"corpus_type": "scripture"}},
    "rama":    {"entity_id": "rama", "display": "Rama",
                "epithet": "prince of Ayodhya, avatara of Vishnu", "voice": {"corpus_type": "scripture"}},
    "vyasa":   {"entity_id": "vyasa", "display": "Vyasa",
                "epithet": "compiler of the Vedas, author of the Mahabharata", "voice": {"corpus_type": "scripture"}},
    "arjuna":  {"entity_id": "arjuna", "display": "Arjuna",
                "epithet": "the Pandava, disciple of Krishna", "voice": {"corpus_type": "scripture"}},
    "narada":  {"entity_id": "narada", "display": "Narada",
                "epithet": "the wandering sage, messenger of the gods", "voice": {"corpus_type": "scripture"}},
}


# ── Edge classification ───────────────────────────────────────────────────────
# Clean directional transmission edge: src is the guru, dst the disciple.
_GURU_OF = "guru_of"
_KIN_WORDS = {
    "father", "mother", "son", "daughter", "wife", "husband", "brother",
    "sister", "child", "parent", "spouse", "grandfather", "grandmother",
    "grandson", "granddaughter", "father_in_law", "mother_in_law",
}
_FUZZY_GURU = ("guru", "disciple", "teach", "initiat", "student", "preceptor", "instruct")

# Kin directionality (ported from narrative_engine/character.py, which the game
# proved against known families). The decoder writes kin edges in BOTH conventions
# for one fact ({Dasharatha, son, Rama} AND {Dasharatha, father, Rama}); the rel
# WORD is noisy, but edge POSITION is reliable — src is the senior. So we relabel
# from the QUERIED entity's POV by position, keeping the gendered word only when it
# actually describes the OTHER end. This is what stops "Parvati (husband)".
_PARENT_WORDS = {"father", "mother"}
_CHILD_WORDS = {"son", "daughter"}
_SPOUSE_WORDS = {"husband", "wife", "spouse", "married"}
_SIBLING_WORDS = {"brother", "sister", "sibling"}
_SPOUSE_INVERSE = {"husband": "wife", "wife": "husband"}
_PARENT_AXIS = _PARENT_WORDS | _CHILD_WORDS | {"parent", "child"}


def _kin_label(rel: str, queried_is_src: bool) -> str:
    """Kin label for the OTHER end, from the queried entity's POV (src is senior)."""
    r = (rel or "").lower()
    if r in _PARENT_AXIS:
        if queried_is_src:                       # other end is my child
            return r if r in _CHILD_WORDS else "child"
        return r if r in _PARENT_WORDS else "parent"   # other end is my parent
    if r in ("father_in_law", "mother_in_law"):
        return r
    if r in _SPOUSE_WORDS:
        if queried_is_src:
            return r if r in ("husband", "wife") else "spouse"
        return _SPOUSE_INVERSE.get(r, "spouse")
    if r in _SIBLING_WORDS:
        return r if r in ("brother", "sister") else "sibling"
    return rel


# RAM meanings that are non-meanings — the decoder's "I found nothing" placeholders.
# A faithful exact-match would still attach these; we drop them so a persona never
# claims an inner nature of "not mentioned in this text".
_PLACEHOLDER_MARKERS = ("not mentioned", "no direct decryption", "no decryption",
                        "not decoded", "n/a", "unknown")


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def _norm(s: str) -> str:
    """Strip IAST diacritics → ascii-lower-alnum, for RAM symbol matching."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


_memory_singleton = None


def _load_memory(graph_path: str = _GRAPH_PATH, ram_path: str = _RAM_PATH):
    """Load the graph once (module singleton). Returns None on any failure."""
    global _memory_singleton
    if _memory_singleton is not None:
        return _memory_singleton
    try:
        from tools.read_pass import recall
        _memory_singleton = recall.Memory.load(graph_path, ram_path)
    except Exception:
        _memory_singleton = None
    return _memory_singleton


def _ram_index(memory) -> Dict[str, str]:
    """normalized symbol → meaning, from the 613-key RAM codex."""
    idx: Dict[str, str] = {}
    for k in getattr(memory, "keys", None) or []:
        sym = k.get("symbol") if isinstance(k, dict) else None
        mean = k.get("meaning") if isinstance(k, dict) else None
        if sym and mean:
            idx.setdefault(_norm(sym), mean)
    return idx


def _decode_meaning(entity: Dict[str, Any], ram: Dict[str, str]) -> Optional[str]:
    """Exact RAM-symbol match on the entity's name + aliases.

    This defeats the bleed we saw via recall (the same void-key landing on both
    Krishna AND the mountain; 'epithet of Arjuna' landing on Hanuman). The codex
    meaning attaches ONLY when a real symbol matches — most beings have none, and
    that is correct.
    """
    forms = [entity.get("name", "")] + list(entity.get("all_forms") or [])
    for f in forms:
        m = ram.get(_norm(f))
        if m and not any(marker in m.lower() for marker in _PLACEHOLDER_MARKERS):
            return m
    return None


def build_persona(persona_id: str, memory=None) -> Dict[str, Any]:
    """Assemble the persona block for one registry entry. Returns the envelope.

    data on success:
      { persona_id, display, epithet, identity{name,kind,aliases,chapters},
        lineage[], kin[], deeds[], inner_meaning, voice }
    """
    reg = REGISTRY.get(persona_id)
    if not reg:
        return _envelope(False, None, {"persona_id": persona_id},
                         [{"code": "unknown_persona",
                           "message": f"'{persona_id}' is not in the curated roster"}])

    mem = memory if memory is not None else _load_memory()
    if mem is None:
        return _envelope(False, None, {"persona_id": persona_id},
                         [{"code": "no_graph", "message": "graph could not be loaded"}])

    eid = reg["entity_id"]
    entity = next((e for e in mem.entities if e.get("id") == eid), None)
    if entity is None:
        return _envelope(False, None, {"persona_id": persona_id, "entity_id": eid},
                         [{"code": "entity_not_found",
                           "message": f"registry id '{eid}' missing from graph"}])

    lineage: List[Dict[str, str]] = []
    kin: List[Dict[str, str]] = []
    deeds: List[Dict[str, str]] = []
    seen_deed = set()

    for ed in mem.edges:
        src, dst, rel = ed.get("src"), ed.get("dst"), (ed.get("rel") or "")
        if src != eid and dst != eid:
            continue
        is_src = (src == eid)
        other = (ed.get("dst_name") if is_src else ed.get("src_name")) or (dst if is_src else src)
        rl = rel.lower()

        if rl == _GURU_OF:
            # directional & reliable: src is guru of dst
            role = "disciple" if is_src else "guru"
            lineage.append({"name": other, "role": role})
        elif rl in _KIN_WORDS:
            kin.append({"name": other, "relation": _kin_label(rel, is_src)})
        elif any(w in rl for w in _FUZZY_GURU):
            # direction is noisy on fuzzy guru rels — present as association, no role claim
            key = (other.lower(), "lineage")
            if key not in seen_deed:
                seen_deed.add(key)
                deeds.append({"name": other, "relation": rel, "as": "outgoing" if is_src else "incoming"})
        else:
            key = (other.lower(), rl)
            if key not in seen_deed:
                seen_deed.add(key)
                deeds.append({"name": other, "relation": rel, "as": "outgoing" if is_src else "incoming"})

    # Collapse kin to one entry per person — the reciprocal edges (husband/wife of
    # the same Sati) relabel to the same role; keep the specific (gendered) word.
    _generic = {"parent", "child", "spouse", "sibling"}
    kin_best: Dict[str, Dict[str, str]] = {}
    kin_order: List[str] = []
    for k in kin:
        key = k["name"].lower()
        if key not in kin_best:
            kin_best[key] = k
            kin_order.append(key)
        elif kin_best[key]["relation"] in _generic and k["relation"] not in _generic:
            kin_best[key] = k
    kin = [kin_best[k] for k in kin_order]

    ram = _ram_index(mem)
    inner = _decode_meaning(entity, ram)

    data = {
        "persona_id": persona_id,
        "display": reg["display"],
        "epithet": reg["epithet"],
        "identity": {
            "name": entity.get("name", ""),
            "kind": entity.get("kind", ""),
            "aliases": [a for a in (entity.get("all_forms") or []) if a != entity.get("name")][:8],
            "chapters": len(entity.get("chapters", [])),
        },
        "lineage": lineage[:8],
        "kin": kin[:10],
        "deeds": deeds[:16],
        "inner_meaning": inner,
        "voice": reg["voice"],
    }
    return _envelope(True, data, {
        "persona_id": persona_id,
        "entity_id": eid,
        "n_lineage": len(lineage), "n_kin": len(kin), "n_deeds": len(deeds),
        "has_inner_meaning": inner is not None,
    }, [])


def render_persona_block(data: Dict[str, Any]) -> str:
    """Render the persona `data` as the prompt-ready text that fills the
    {personality} slot of the system prompt — the graph-grounded replacement for
    the hand-written GURUJI_PERSONALITY. Substance only; the VOICE/register is
    carried by the persona's own retrieved passages injected into {context}."""
    lines: List[str] = []
    lines.append(f"You are {data['display']} — {data['epithet']}.")
    if data.get("inner_meaning"):
        lines.append(f"Your inner nature, as the lineage decodes it: {data['inner_meaning']}.")
    if data.get("lineage"):
        gurus = [x["name"] for x in data["lineage"] if x["role"] == "guru"]
        disc = [x["name"] for x in data["lineage"] if x["role"] == "disciple"]
        if gurus:
            lines.append("Your guru" + ("s" if len(gurus) > 1 else "") + ": " + ", ".join(gurus) + ".")
        if disc:
            lines.append("Your disciple" + ("s" if len(disc) > 1 else "") + ": " + ", ".join(disc) + ".")
    if data.get("kin"):
        kin = "; ".join(f"{k['name']} ({k['relation']})" for k in data["kin"][:6])
        lines.append(f"Your kin: {kin}.")
    if data.get("deeds"):
        deeds = "; ".join(f"{d['relation']} {d['name']}" for d in data["deeds"][:8])
        lines.append(f"What the texts record of you: {deeds}.")
    lines.append("Speak only from what is true of you in the texts above — never invent a "
                 "relationship, weapon, or deed the corpus does not record.")
    return "\n".join(lines)


def run(persona_id: str = "", *, memory=None) -> Dict[str, Any]:
    """Envelope entrypoint. With no persona_id, returns the roster (data.roster)."""
    if not persona_id:
        return _envelope(True, {"roster": [
            {"persona_id": pid, "display": r["display"], "epithet": r["epithet"]}
            for pid, r in REGISTRY.items()
        ]}, {"n_personas": len(REGISTRY)}, [])
    env = build_persona(persona_id, memory=memory)
    if env["success"]:
        env["data"]["block"] = render_persona_block(env["data"])
    return env


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    persona_id = ""
    if "--persona" in argv:
        persona_id = argv[argv.index("--persona") + 1]

    env = run(persona_id)
    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        if persona_id:
            print(env["data"]["block"])
        else:
            for r in env["data"]["roster"]:
                print(f"  {r['persona_id']:10} {r['display']} — {r['epithet']}")
    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
