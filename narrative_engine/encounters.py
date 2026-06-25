"""encounters — the bible's encounter bank, classified from the real biography.

Turns Guruji's 285 lived entity-encounters (from sharma_biography.json) into a
structured bank the game can serve: each tagged with a REGISTER (how the
disciple-POV perceives it), the GRANTHI-ACT it feeds, and the decoded PRINCIPLE
the being embodies.

Classification is DETERMINISTIC (pattern rules over the encounter text + the RAM
decode principle index) — not an LLM guess — so it is reproducible, testable, and
honest about its confidence. The rules encode the bible's own definitions:

  REGISTER (reverent-distance POV — the player walks TOWARD Guruji):
    told     — the disciple HEARS of it (story, photo, book, "referenced", "heard")
    glimpsed — present at the EDGE: a materialization, footprints, a flood, a statue
               gone warm, an appearance/arrival
    beheld   — the PRINCIPLE becomes perceptible to awakening senses (samadhi,
               realization, perceiving Time/Void, the un-faced vision)

  ACT (the three-knot spine):
    lineage     — a guru-spine transmission (Babaji/Lahiri/Tinkori/Satyacharan)
    act1_brahma — body/matter knot: early seeking, khechari, finding the true guru
    act2_vishnu — heart knot: smashan years, deities arriving, Vishnu-in-the-heart
    act3_rudra  — time knot + climax: Omkar, conscious exit, perceiving unmanifest Time
    ambient     — world-texture, not a gated beat
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from tools.read_pass.recall import Memory, _norm


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


_BIO_PATH = os.environ.get("BIO_PATH", "tools/read_pass/out/sharma_biography.json")

# the guru-spine names — encounters with these are lineage transmissions
_LINEAGE = {"babaji", "mahavatar babaji", "lahiri mahasaya", "tinkori lahiri",
            "satyacharan lahiri", "shri satyacharan lahiri"}

# decoded principle each major being embodies (from guruji_ram.json, condensed)
_PRINCIPLE = {
    "shiva": "Time (Kal) — annihilation, beyond matter and void",
    "mahadev": "Time (Kal) — annihilation, beyond matter and void",
    "rudra": "Time (Kal) — the destroyer aspect",
    "vishnu": "consciousness of the conscious void",
    "vasudev": "the four-armed form of Time, in the heart",
    "vasudeva": "the four-armed form of Time, in the heart",
    "krishna": "the universal form revealed as Time",
    "shakti": "earth element, apana — the muladhara matrix",
    "adi shakti": "earth element, apana — the muladhara matrix",
    "devi": "the Dark Mother; earth/apana pole",
    "kali": "the Dark Mother; destruction and protection",
    "hanuman": "prana in perfect continence; guardian of power",
    "yama": "death as dharma",
    "yamaraj": "death as dharma",
    "dattatreya": "the Adi-Guru; origin of Aghora/Nath/Kapalika streams",
    "matsyendranath": "the Nath transmission (tejas at the tallu)",
    "babaji": "the deathless guru; giver of Omkar kriya + conscious exit",
    "mahavatar babaji": "the deathless guru; giver of Omkar kriya + conscious exit",
}

# register cue words (checked in priority order: beheld > glimpsed > told)
_BEHELD_CUES = ["samadhi", "realization", "realiz", "perceiv", "expanded his consciousness",
                "void", "became one", "darshan", "merged", "in his heart", "amrita",
                "conscious exit", "time and void"]
_GLIMPSED_CUES = ["appeared", "materializ", "appears", "footprints", "flood", "vanish",
                  "grabbed", "pulled him", "stopped", "knocked", "turned into",
                  "turn into", "delivered", "patted", "garland", "statue", "murti",
                  "transparent", "in person", "met him", "met personally", "came back",
                  "subtle body", "physical meeting", "stood in room"]
_TOLD_CUES = ["heard", "read", "story", "referenced", "mentioned", "studied",
              "learned about", "photo", "books", "recognized", "legend", "claims",
              "described", "considered"]

# act cue words
_ACT3_CUES = ["omkar", "conscious exit", "unmanifest time", "57th birthday",
              "time and void", "destroyer", "annihilat", "voluntary death",
              "leaving the body", "samadhi", "air lingam", "srikalahasti"]
_ACT2_CUES = ["smashan", "cremation", "govardhan", "heart", "vasudev", "python",
              "hemorrhage", "yantra", "devahuti", "vishnu", "1996", "shivalingam",
              "dhuni", "darbar", "yogiraj"]
_ACT1_CUES = ["khechari", "kriya books", "found his teacher", "first guru",
              "initiation", "pranayama", "gita commentary", "photo", "anandamayi",
              "puri", "vrindavan", "began", "search"]


def _classify_register(text: str) -> str:
    t = text.lower()
    if any(c in t for c in _BEHELD_CUES):
        return "beheld"
    if any(c in t for c in _GLIMPSED_CUES):
        return "glimpsed"
    if any(c in t for c in _TOLD_CUES):
        return "told"
    return "told"  # default to the most-distant register (conservative)


def _classify_act(entity: str, text: str) -> str:
    e, t = _norm(entity), text.lower()
    if any(name in e for name in ["babaji", "lahiri", "tinkori", "satyacharan"]):
        return "lineage"
    if any(c in t for c in _ACT3_CUES):
        return "act3_rudra"
    if any(c in t for c in _ACT2_CUES):
        return "act2_vishnu"
    if any(c in t for c in _ACT1_CUES):
        return "act1_brahma"
    return "ambient"


def _principle_for(entity: str) -> str:
    e = _norm(entity)
    for key, pr in _PRINCIPLE.items():
        if key in e:
            return pr
    return ""


def _load_encounters() -> List[Dict[str, str]]:
    try:
        with open(_BIO_PATH, encoding="utf-8") as f:
            bio = json.load(f).get("data", {}).get("biography", {})
        out, seen = [], set()
        for e in bio.get("entity_encounters", []) or []:
            ent, txt = e.get("entity", ""), e.get("encounter", "")
            if not txt or len(txt) < 12:
                continue
            key = (ent, txt)
            if key in seen:
                continue
            seen.add(key)
            out.append({"entity": ent, "encounter": txt})
        return out
    except Exception:
        return []


def encounter_bank(memory: Optional[Memory] = None) -> Dict[str, Any]:
    """Classify every biographical encounter into register/act/principle."""
    raw = _load_encounters()
    classified = []
    for e in raw:
        classified.append({
            "entity": e["entity"],
            "register": _classify_register(e["encounter"]),
            "act": _classify_act(e["entity"], e["encounter"]),
            "principle": _principle_for(e["entity"]),
            "text": e["encounter"],
        })
    # distribution tallies (plain code)
    by_reg, by_act = {}, {}
    for c in classified:
        by_reg[c["register"]] = by_reg.get(c["register"], 0) + 1
        by_act[c["act"]] = by_act.get(c["act"], 0) + 1
    return _envelope(
        True,
        {"encounters": classified,
         "by_register": by_reg, "by_act": by_act},
        {"total": len(classified)},
        [],
    )


def encounters_for_act(act: str, memory: Optional[Memory] = None) -> Dict[str, Any]:
    """All encounters feeding one granthi-act — what populates that act's scenes."""
    bank = encounter_bank(memory)["data"]["encounters"]
    hits = [c for c in bank if c["act"] == act]
    return _envelope(True, {"act": act, "encounters": hits},
                     {"n": len(hits)}, [])


def encounters_with(entity: str, memory: Optional[Memory] = None) -> Dict[str, Any]:
    """Every recorded encounter with a given being."""
    n = _norm(entity)
    bank = encounter_bank(memory)["data"]["encounters"]
    hits = [c for c in bank if n in _norm(c["entity"]) or _norm(c["entity"]) in n]
    return _envelope(True, {"entity": entity, "encounters": hits},
                     {"n": len(hits)}, [])
