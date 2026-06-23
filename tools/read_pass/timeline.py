"""timeline — place Puranic events on the cosmic time scale.

The Puranas define their own fractal time architecture:
  Mahā-Kalpa (life of Brahmā) > Kalpa (day of Brahmā, 14 Manvantaras)
  > Manvantara (71 Mahā-Yugas) > Mahā-Yuga (4 Yugas)
  > Yuga: Satya → Tretā → Dvāpara → Kali

Every narrative event sits somewhere on this scale. This module:
1. Defines the hierarchy as structured data
2. Maps known anchor points (avatars → Yugas) deterministically
3. Extracts temporal markers from graph entities/edges by keyword
4. Uses the reasoning model for ambiguous placements (Phase 2)

The output is a chronologically ordered timeline of placed events,
each tagged with its Epoch coordinate and placement method (avatar_map,
keyword, reasoning_model, or unplaced).

JSON contract (Rule 0, precond B):
  run(events) -> {success, data:{placed_events, timeline_summary}, metadata, errors}
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# ── The Puranic cosmic hierarchy ──────────────────────────────────────────

COSMIC_HIERARCHY = {
    "kalpa": {
        "name": "Kalpa (Day of Brahmā)",
        "duration_years": 4_320_000_000,
        "sub_unit": "manvantara",
        "sub_count": 14,
    },
    "manvantara": {
        "name": "Manvantara (Reign of one Manu)",
        "duration_years": 306_720_000,
        "sub_unit": "maha_yuga",
        "sub_count": 71,
    },
    "maha_yuga": {
        "name": "Mahā-Yuga (Great Age)",
        "duration_years": 4_320_000,
        "sub_unit": "yuga",
        "sub_count": 4,
    },
    "yuga": {
        "name": "Yuga",
        "sequence": ["satya", "treta", "dvapara", "kali"],
        "durations": {
            "satya": 1_728_000,
            "treta": 1_296_000,
            "dvapara": 864_000,
            "kali": 432_000,
        },
    },
}

# Yuga ordinal for comparison
_YUGA_ORD = {"satya": 0, "treta": 1, "dvapara": 2, "kali": 3}

# The 14 Manus of the current Kalpa (Śvetavarāha)
MANU_SEQUENCE = [
    "svayambhuva", "svarocisha", "uttama", "tamasa", "raivata",
    "cakshusha", "vaivasvata", "savarni", "daksha_savarni",
    "brahma_savarni", "dharma_savarni", "rudra_savarni",
    "deva_savarni", "indra_savarni",
]


@dataclass(frozen=True)
class Epoch:
    """A coordinate on the Puranic time scale."""
    kalpa: Optional[str] = None       # e.g. "shvetavaraha" (current)
    manvantara: Optional[int] = None  # 1-14
    maha_yuga: Optional[int] = None   # within the manvantara
    yuga: Optional[str] = None        # satya/treta/dvapara/kali

    def sort_key(self) -> Tuple[int, int, int, int]:
        return (
            self.manvantara or 0,
            self.maha_yuga or 0,
            _YUGA_ORD.get(self.yuga or "", 0),
            0,
        )

    def __lt__(self, other):
        if not isinstance(other, Epoch):
            return NotImplemented
        return self.sort_key() < other.sort_key()

    def label(self) -> str:
        parts = []
        if self.kalpa:
            parts.append(f"Kalpa: {self.kalpa}")
        if self.manvantara is not None:
            manu_name = MANU_SEQUENCE[self.manvantara - 1] if 1 <= self.manvantara <= 14 else f"#{self.manvantara}"
            parts.append(f"Manvantara {self.manvantara} ({manu_name})")
        if self.yuga:
            parts.append(f"{self.yuga.title()} Yuga")
        return " / ".join(parts) if parts else "unplaced"

    def to_dict(self) -> Dict[str, Any]:
        return {"kalpa": self.kalpa, "manvantara": self.manvantara,
                "maha_yuga": self.maha_yuga, "yuga": self.yuga,
                "label": self.label()}


# ── Known anchor points (deterministic, no LLM needed) ───────────────────

# The Daśāvatāra (10 principal avatars) with their canonical epoch placements
AVATAR_EPOCH_MAP = {
    # name_normalized: Epoch
    "matsya":       Epoch(manvantara=1, yuga="satya"),
    "kurma":        Epoch(yuga="satya"),
    "varaha":       Epoch(kalpa="shvetavaraha", yuga="satya"),
    "narasimha":    Epoch(yuga="satya"),
    "vamana":       Epoch(manvantara=7, yuga="treta"),
    "parashurama":  Epoch(yuga="treta"),
    "rama":         Epoch(manvantara=7, yuga="treta"),
    "balarama":     Epoch(manvantara=7, yuga="dvapara"),
    "krishna":      Epoch(manvantara=7, yuga="dvapara"),
    "kalki":        Epoch(yuga="kali"),
    # other well-known placements
    "kapila":       Epoch(manvantara=1, yuga="satya"),
    "vyasa":        Epoch(manvantara=7, yuga="dvapara"),
    "buddha":       Epoch(yuga="kali"),
    "prithu":       Epoch(manvantara=1, yuga="satya"),
}

# Manu → Manvantara number
MANU_TO_MANVANTARA = {name: i + 1 for i, name in enumerate(MANU_SEQUENCE)}

# Yuga keyword patterns
_YUGA_PATTERNS = [
    (re.compile(r"\b(?:satya|krta|krita)\s*(?:yuga)?\b", re.I), "satya"),
    (re.compile(r"\btret[aā]\s*(?:yuga)?\b", re.I), "treta"),
    (re.compile(r"\bdv[aā]para\s*(?:yuga)?\b", re.I), "dvapara"),
    (re.compile(r"\bkali\s*(?:yuga|age)\b", re.I), "kali"),
]

_MANVANTARA_PATTERN = re.compile(
    r"(\w+)\s*manvantara|manvantara\s*(?:of\s*)?(\w+)", re.I)


# ── Placement logic ──────────────────────────────────────────────────────

def _norm_name(s: str) -> str:
    import unicodedata
    nf = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in nf if not unicodedata.combining(c)).strip().lower()


def _try_avatar_map(event: Dict) -> Optional[Tuple[Epoch, str]]:
    name = _norm_name(event.get("entity", ""))
    preds = [p.lower() for p in event.get("predicates", [])]
    if name in AVATAR_EPOCH_MAP:
        return AVATAR_EPOCH_MAP[name], "avatar_map"
    for form in event.get("all_forms", []):
        nf = _norm_name(form)
        if nf in AVATAR_EPOCH_MAP:
            return AVATAR_EPOCH_MAP[nf], "avatar_map"
    return None


def _try_keyword(event: Dict) -> Optional[Tuple[Epoch, str]]:
    text = " ".join([
        event.get("entity", ""),
        event.get("context", ""),
        " ".join(event.get("predicates", [])),
    ]).lower()

    yuga = None
    for pat, y in _YUGA_PATTERNS:
        if pat.search(text):
            yuga = y
            break

    manvantara = None
    m = _MANVANTARA_PATTERN.search(text)
    if m:
        manu_name = _norm_name(m.group(1) or m.group(2) or "")
        manvantara = MANU_TO_MANVANTARA.get(manu_name)

    if yuga or manvantara:
        return Epoch(manvantara=manvantara, yuga=yuga), "keyword"
    return None


def place_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Place events on the cosmic timeline using deterministic methods.

    Each event dict should have at minimum: entity, kind.
    Optional: predicates, context, all_forms.
    """
    placed = []
    for ev in events:
        result = _try_avatar_map(ev) or _try_keyword(ev)
        if result:
            epoch, method = result
            placed.append({
                "entity": ev.get("entity", "?"),
                "kind": ev.get("kind", ""),
                "epoch": epoch,
                "method": method,
            })
        else:
            placed.append({
                "entity": ev.get("entity", "?"),
                "kind": ev.get("kind", ""),
                "epoch": Epoch(),
                "method": "unplaced",
            })
    return placed


def extract_temporal_markers(entities: List[Dict], edges: List[Dict]) -> List[Dict]:
    """Extract event dicts from graph data suitable for place_events().

    Scans entities and edges for temporal signals: avatar predicates,
    yuga mentions in names/kinds, manvantara references.
    """
    markers = []
    ent_preds = {}
    ent_context = {}

    for e in edges:
        ent_preds.setdefault(e["src"], []).append(e["rel"])
        ctx = f"{e['rel']} {e['dst_name']}"
        ent_context.setdefault(e["src"], []).append(ctx)

    for ent in entities:
        preds = ent_preds.get(ent["id"], [])
        ctx_parts = ent_context.get(ent["id"], [])
        markers.append({
            "entity": ent["name"],
            "kind": ent.get("kind", ""),
            "predicates": preds,
            "context": " ".join(ctx_parts),
            "all_forms": ent.get("all_forms", []),
        })
    return markers


def propagate_epochs(placed: List[Dict], edges: List[Dict],
                     max_hops: int = 3) -> List[Dict]:
    """Spread epoch placements through graph edges.

    If Krishna is Dvāpara and Arjuna is connected to Krishna by an edge,
    Arjuna inherits Dvāpara. Propagation runs BFS up to max_hops from
    each anchor entity. Only unplaced entities receive a propagated epoch.

    Edges that are clearly cross-epoch (like "avatar of", "incarnation of")
    do NOT propagate — an avatar's source deity spans all Yugas.
    """
    NON_PROPAGATING = {"avatar", "incarnation", "a_form", "an_expansion",
                       "form", "worshipped_in_yuga"}

    entity_epoch = {}
    entity_method = {}
    for p in placed:
        if p["method"] != "unplaced":
            entity_epoch[p["entity"]] = p["epoch"]
            entity_method[p["entity"]] = p["method"]

    adj = {}
    for e in edges:
        if e["rel"] in NON_PROPAGATING:
            continue
        adj.setdefault(e["src_name"], set()).add(e["dst_name"])
        adj.setdefault(e["dst_name"], set()).add(e["src_name"])

    for _hop in range(max_hops):
        new_placements = {}
        for anchor, epoch in entity_epoch.items():
            for neighbor in adj.get(anchor, []):
                if neighbor not in entity_epoch and neighbor not in new_placements:
                    new_placements[neighbor] = epoch
        if not new_placements:
            break
        for ent, epoch in new_placements.items():
            entity_epoch[ent] = epoch
            entity_method[ent] = "propagated"

    result = []
    for p in placed:
        ent = p["entity"]
        if ent in entity_epoch:
            result.append({
                "entity": ent,
                "kind": p["kind"],
                "epoch": entity_epoch[ent],
                "method": entity_method.get(ent, p["method"]),
            })
        else:
            result.append(p)
    return result


def build_timeline_summary(placed: List[Dict]) -> Dict[str, Any]:
    """Group placed events by epoch for display."""
    by_yuga = {}
    unplaced_count = 0
    for p in placed:
        if p["method"] == "unplaced":
            unplaced_count += 1
            continue
        yuga = p["epoch"].yuga or "unknown"
        by_yuga.setdefault(yuga, []).append(p["entity"])

    return {
        "by_yuga": {k: sorted(set(v)) for k, v in sorted(
            by_yuga.items(), key=lambda x: _YUGA_ORD.get(x[0], 99))},
        "n_placed": len(placed) - unplaced_count,
        "n_unplaced": unplaced_count,
        "coverage": round((len(placed) - unplaced_count) / max(len(placed), 1), 3),
    }


def run(events: List[Dict[str, Any]],
        edges: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """JSON contract endpoint."""
    placed = place_events(events)
    if edges:
        placed = propagate_epochs(placed, edges)
    summary = build_timeline_summary(placed)

    serializable = []
    for p in placed:
        sp = dict(p)
        sp["epoch"] = sp["epoch"].to_dict()
        serializable.append(sp)

    # sort by epoch
    placed_sorted = sorted(
        [p for p in placed if p["method"] != "unplaced"],
        key=lambda p: p["epoch"].sort_key())
    sorted_serializable = []
    for p in placed_sorted:
        sp = dict(p)
        sp["epoch"] = sp["epoch"].to_dict()
        sorted_serializable.append(sp)

    data = {
        "placed_events": serializable,
        "placed_events_sorted": sorted_serializable,
        "timeline_summary": summary,
    }
    return _envelope(True, data, {"n_input_events": len(events)}, [])


if __name__ == "__main__":
    import sys
    from tools.read_pass import graph as G

    path = sys.argv[1] if len(sys.argv) > 1 else \
        "tools/read_pass/out/bhagavata_full.records.v1_broken_lens.jsonl"
    recs = [json.loads(l) for l in open(path) if l.strip()]
    g = G.build(recs)
    markers = extract_temporal_markers(g.entities, g.edges)
    env = run(markers, edges=g.edges)

    if "--json" in sys.argv:
        print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    else:
        d = env["data"]
        s = d["timeline_summary"]
        print(f"Placed {s['n_placed']}/{s['n_placed'] + s['n_unplaced']} "
              f"entities ({s['coverage']*100:.1f}% coverage)")
        for yuga, ents in s["by_yuga"].items():
            print(f"\n  {yuga.upper()} YUGA ({len(ents)} entities):")
            for e in ents[:10]:
                print(f"    {e}")
            if len(ents) > 10:
                print(f"    ...+{len(ents)-10} more")
