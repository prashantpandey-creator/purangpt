"""seeker — the player's state in the Puranic universe.

Tracks the guna balance (sattva/rajas/tamas), tapasya relationships with
deities, earned boons, active curses, and the karma chain of dharmic choices.

The guna system is NOT a morality meter. It's the framework the texts themselves
describe — three qualities that color every action, and the goal (per Gita 14)
is to transcend all three (gunatita). High sattva isn't "good"; it's one valid
mode of being that opens certain paths and closes others.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


@dataclass
class GunaBalance:
    """The three gunas as a normalized triple (always sums to 1.0)."""
    sattva: float = 0.40
    rajas: float = 0.35
    tamas: float = 0.25

    def shift(self, ds: float = 0.0, dr: float = 0.0, dt: float = 0.0):
        """Apply a guna shift and re-normalize."""
        self.sattva = max(0.01, self.sattva + ds)
        self.rajas = max(0.01, self.rajas + dr)
        self.tamas = max(0.01, self.tamas + dt)
        total = self.sattva + self.rajas + self.tamas
        self.sattva /= total
        self.rajas /= total
        self.tamas /= total

    @property
    def dominant(self) -> str:
        if self.sattva >= self.rajas and self.sattva >= self.tamas:
            return "sattva"
        if self.rajas >= self.tamas:
            return "rajas"
        return "tamas"

    def to_dict(self) -> Dict[str, float]:
        return {
            "sattva": round(self.sattva, 3),
            "rajas": round(self.rajas, 3),
            "tamas": round(self.tamas, 3),
            "dominant": self.dominant,
        }


@dataclass
class TapasyaRecord:
    """Sustained devotion toward a specific deity."""
    deity: str
    accumulated: float = 0.0
    sessions: int = 0
    last_session: float = 0.0

    def add(self, amount: float):
        self.accumulated += amount
        self.sessions += 1
        self.last_session = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deity": self.deity,
            "accumulated": round(self.accumulated, 1),
            "sessions": self.sessions,
        }


@dataclass
class DharmicChoice:
    """A recorded decision at a narrative fork."""
    event_id: str
    event_description: str
    choice: str
    guna_shift: Dict[str, float]
    consequences: List[str] = field(default_factory=list)
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event_id,
            "description": self.event_description,
            "choice": self.choice,
            "guna_shift": self.guna_shift,
            "consequences": self.consequences,
            "timestamp": self.timestamp,
        }


@dataclass
class SeekerState:
    """The player's full state in the Puranic universe."""
    name: str = "Seeker"
    guna: GunaBalance = field(default_factory=GunaBalance)
    tapasya: Dict[str, TapasyaRecord] = field(default_factory=dict)
    boons: List[Dict[str, str]] = field(default_factory=list)
    curses: List[Dict[str, str]] = field(default_factory=list)
    choices: List[DharmicChoice] = field(default_factory=list)
    current_location: str = ""
    visited_locations: List[str] = field(default_factory=list)
    relationships: Dict[str, float] = field(default_factory=dict)

    def meditate(self, deity: str, intensity: float = 1.0):
        """Perform tapasya toward a deity. Shifts guna toward sattva.

        Tapasya ACCUMULATES the full intensity (cumulative devotion — high
        intensity earns boon-gating tapasya fast). But the per-session GUNA shift
        is capped: one sitting can't flatline the triple. Sustained sattva comes
        from many sessions, not one giant intensity number. Without this cap a
        single intensity-60 meditation pinned sattva to ~0.98 and made every
        min_sattva combat gate trivially passable.
        """
        if deity not in self.tapasya:
            self.tapasya[deity] = TapasyaRecord(deity=deity)
        self.tapasya[deity].add(intensity)
        # cap the guna nudge so a single meditation shifts sattva by at most ~0.10
        capped = min(intensity, 5.0)
        self.guna.shift(ds=0.02 * capped, dr=-0.01 * capped, dt=-0.01 * capped)

    def make_choice(self, event_id: str, description: str, choice: str,
                    guna_shift: Dict[str, float],
                    consequences: Optional[List[str]] = None):
        """Record a dharmic choice and apply its guna shift."""
        dc = DharmicChoice(
            event_id=event_id,
            event_description=description,
            choice=choice,
            guna_shift=guna_shift,
            consequences=consequences or [],
            timestamp=time.time(),
        )
        self.choices.append(dc)
        self.guna.shift(
            ds=guna_shift.get("sattva", 0),
            dr=guna_shift.get("rajas", 0),
            dt=guna_shift.get("tamas", 0),
        )

    def earn_boon(self, boon_name: str, granted_by: str, citation: str = ""):
        self.boons.append({
            "name": boon_name,
            "granted_by": granted_by,
            "citation": citation,
        })

    def receive_curse(self, curse_name: str, cursed_by: str, citation: str = ""):
        self.curses.append({
            "name": curse_name,
            "cursed_by": cursed_by,
            "citation": citation,
        })

    def move_to(self, location: str):
        if self.current_location and self.current_location not in self.visited_locations:
            self.visited_locations.append(self.current_location)
        self.current_location = location

    def adjust_relationship(self, npc: str, delta: float):
        """Shift relationship with an NPC. Positive = trust, negative = distance."""
        current = self.relationships.get(npc, 0.0)
        self.relationships[npc] = max(-1.0, min(1.0, current + delta))

    def can_use_astra(self, astra_name: str, required_deity: Optional[str] = None,
                      min_tapasya: float = 0.0) -> Dict[str, Any]:
        """Check if the seeker has earned access to a divine weapon."""
        has_boon = any(b["name"].lower() == astra_name.lower() for b in self.boons)
        has_tapasya = True
        if required_deity:
            tap = self.tapasya.get(required_deity)
            has_tapasya = tap is not None and tap.accumulated >= min_tapasya

        is_cursed = any(c["name"].lower() == astra_name.lower() for c in self.curses)

        can_use = has_boon and has_tapasya and not is_cursed
        reason = ""
        if not has_boon:
            reason = f"No boon grants access to {astra_name}"
        elif not has_tapasya:
            reason = f"Insufficient tapasya with {required_deity} (need {min_tapasya})"
        elif is_cursed:
            reason = f"A curse prevents use of {astra_name}"

        return {
            "astra": astra_name,
            "can_use": can_use,
            "reason": reason,
            "has_boon": has_boon,
            "has_tapasya": has_tapasya,
            "is_cursed": is_cursed,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "guna": self.guna.to_dict(),
            "tapasya": {k: v.to_dict() for k, v in self.tapasya.items()},
            "boons": self.boons,
            "curses": self.curses,
            "choices": [c.to_dict() for c in self.choices],
            "current_location": self.current_location,
            "visited_locations": self.visited_locations,
            "relationships": {k: round(v, 2) for k, v in self.relationships.items()},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SeekerState":
        state = cls(name=d.get("name", "Seeker"))
        g = d.get("guna", {})
        state.guna = GunaBalance(
            sattva=g.get("sattva", 0.40),
            rajas=g.get("rajas", 0.35),
            tamas=g.get("tamas", 0.25),
        )
        for deity, tap in d.get("tapasya", {}).items():
            state.tapasya[deity] = TapasyaRecord(
                deity=deity,
                accumulated=tap.get("accumulated", 0),
                sessions=tap.get("sessions", 0),
            )
        state.boons = d.get("boons", [])
        state.curses = d.get("curses", [])
        # choices roundtrip: to_dict() emits "event"/"description"; map them back
        # to the dataclass fields event_id/event_description. Without this the
        # entire karma chain was silently lost on every reload.
        for c in d.get("choices", []):
            state.choices.append(DharmicChoice(
                event_id=c.get("event", c.get("event_id", "")),
                event_description=c.get("description", c.get("event_description", "")),
                choice=c.get("choice", ""),
                guna_shift=c.get("guna_shift", {}),
                consequences=c.get("consequences", []),
                timestamp=c.get("timestamp", 0.0),
            ))
        state.current_location = d.get("current_location", "")
        state.visited_locations = d.get("visited_locations", [])
        state.relationships = d.get("relationships", {})
        return state


# --- public API ---------------------------------------------------------------

def get_state(seeker: SeekerState) -> Dict[str, Any]:
    return _envelope(True, seeker.to_dict(), {}, [])

def meditate(seeker: SeekerState, deity: str, intensity: float = 1.0) -> Dict[str, Any]:
    seeker.meditate(deity, intensity)
    return _envelope(True, {
        "action": "meditate",
        "deity": deity,
        "tapasya": seeker.tapasya[deity].to_dict(),
        "guna_after": seeker.guna.to_dict(),
    }, {}, [])

def make_choice(seeker: SeekerState, event_id: str, description: str,
                choice: str, guna_shift: Dict[str, float],
                consequences: Optional[List[str]] = None) -> Dict[str, Any]:
    seeker.make_choice(event_id, description, choice, guna_shift, consequences)
    return _envelope(True, {
        "action": "choice",
        "event": event_id,
        "choice": choice,
        "guna_after": seeker.guna.to_dict(),
        "consequences": consequences or [],
    }, {}, [])


# default starting balance — must match GunaBalance() field defaults so the
# replay below reconstructs the true arc from a clean start.
_START_GUNA = (0.40, 0.35, 0.25)


def karma_chain(seeker: SeekerState) -> Dict[str, Any]:
    """Reconstruct the seeker's journey: every choice, how guna drifted at each
    step, the running dominant guna, and accumulated consequences.

    A derived view — replays stored guna_shifts from the canonical start so a
    game client can render "the path you walked" without recomputing anything.
    Note: replay starts from the default balance; if a seeker's guna was seeded
    differently, the per-step absolutes are relative-correct but offset.
    """
    g = GunaBalance(sattva=_START_GUNA[0], rajas=_START_GUNA[1], tamas=_START_GUNA[2])
    steps = []
    all_consequences: List[str] = []

    # choices are appended in order; sort by timestamp when present for stability
    ordered = sorted(
        seeker.choices,
        key=lambda c: (c.timestamp if c.timestamp else 0.0),
    ) if any(c.timestamp for c in seeker.choices) else list(seeker.choices)

    for i, c in enumerate(ordered):
        before = g.dominant
        g.shift(
            ds=c.guna_shift.get("sattva", 0),
            dr=c.guna_shift.get("rajas", 0),
            dt=c.guna_shift.get("tamas", 0),
        )
        after = g.dominant
        all_consequences.extend(c.consequences)
        steps.append({
            "index": i,
            "event": c.event_id,
            "description": c.event_description,
            "choice": c.choice,
            "guna_shift": c.guna_shift,
            "guna_after": g.to_dict(),
            "dominant_changed": before != after,
            "shifted_from": before,
            "shifted_to": after,
            "consequences": c.consequences,
            "timestamp": c.timestamp,
        })

    return _envelope(True, {
        "seeker": seeker.name,
        "n_choices": len(steps),
        "starting_guna": {"sattva": _START_GUNA[0], "rajas": _START_GUNA[1],
                          "tamas": _START_GUNA[2]},
        "current_guna": seeker.guna.to_dict(),
        "replayed_guna": g.to_dict(),
        "dominant_guna_now": seeker.guna.dominant,
        "steps": steps,
        "all_consequences": all_consequences,
        "turning_points": [s for s in steps if s["dominant_changed"]],
    }, {"n_steps": len(steps), "n_consequences": len(all_consequences),
        "n_turning_points": sum(1 for s in steps if s["dominant_changed"])}, [])
