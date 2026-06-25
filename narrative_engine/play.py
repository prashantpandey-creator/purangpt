"""play — the Phase-A1 client harness for THE AWAKENER.

A thin terminal client that drives the CURRENT engine (scene + saga + codex +
combat) so a person can actually walk a scene and watch the Puranic graph
assemble a character's whole story-braid live. This is the brain→client proof:
nothing here invents — every line is the engine reading the corpus.

Run: venv/bin/python -m narrative_engine.play
Or import Game and drive it programmatically (see demo() / test).
"""
from __future__ import annotations

import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_pass.recall import Memory
from narrative_engine import scene as scene_mod
from narrative_engine import saga as saga_mod
from narrative_engine import codex as codex_mod
from narrative_engine import combat as combat_mod
from narrative_engine.seeker import SeekerState

_GRAPH = "tools/read_pass/out/graph_manifest.json"
_RAM = "tools/read_pass/out/guruji_ram.json"

# ANSI — saffron/gold register, restrained
_B = "\033[1m"; _D = "\033[2m"; _R = "\033[0m"
_GOLD = "\033[33m"; _CY = "\033[36m"; _RED = "\033[31m"; _GRN = "\033[32m"


def _c(s, code):
    return f"{code}{s}{_R}"


def _wrap(t, indent="    "):
    return "\n".join(indent + l for l in textwrap.wrap(t, 76))


class Game:
    """The harness. Stateless toward the engine; holds only the seeker + memory."""

    def __init__(self, memory: Memory):
        self.mem = memory
        self.seeker = SeekerState(name="Disciple")
        self.running = True

    # --- rendering (each method renders one engine result) -------------------

    def render_scene(self, location=None, act=None) -> dict:
        if location:
            self.seeker.move_to(location)
        r = scene_mod.assemble_scene(self.seeker, self.mem,
                                     location or self.seeker.current_location, act)
        if not r["success"]:
            print(_c("  (no scene — the disciple stands nowhere)", _D))
            return r
        d = r["data"]
        loc = d["location"]
        print()
        print(_c("─" * 60, _D))
        print(f"  {_c(loc['name'], _B)}  {_c('(' + loc.get('kind', '') + ')', _D)}"
              + ("" if d["charted"] else _c("  [uncharted]", _D)))
        print(_c("─" * 60, _D))
        npcs = d["surroundings"]["npcs"]
        if npcs:
            print(f"  {_c('Present:', _CY)} " +
                  ", ".join(n["name"] for n in npcs[:6]))
        if d.get("armory"):
            for a in d["armory"][:4]:
                print(f"    {_c('⚔', _RED)} {a['npc']} wields {', '.join(a['wields'][:4])}")
        if d.get("act_encounters"):
            print(f"  {_c('You may behold here:', _CY)}")
            for e in d["act_encounters"][:4]:
                print(f"    [{e['register']}] {e['entity']} "
                      + _c(f"— {e['principle'][:38]}" if e['principle'] else "", _D))
        exits = d["surroundings"]["exits"]
        if exits:
            print(f"  {_c('Paths:', _CY)} " +
                  ", ".join(e["name"] for e in exits[:6]))
        return r

    def render_saga(self, name) -> dict:
        r = saga_mod.saga(name, self.mem)
        if not r["success"]:
            print(_c(f"  '{name}' is unknown to the texts.", _D))
            return r
        d = r["data"]
        print()
        print(f"  {_c(d['headline'], _B)}")
        print(f"  {_c('carries: ' + ', '.join(d['carries']), _D)}")
        for strand in ("identity", "weapons", "vows_and_curses", "lineage", "deeds"):
            items = d["strands"][strand]
            if not items:
                continue
            print(f"  {_c('▸ ' + strand.replace('_', ' ').upper(), _CY)}")
            for x in items[:4]:
                print(f"      {x['subject']} {_c('—' + x['relation'] + '→', _D)} {x['object']}")
        return r

    def render_weapon(self, name) -> dict:
        r = codex_mod.weapon_entry(name, self.mem)
        d = r["data"]
        print()
        print(f"  {_c(d['name'], _B)}  {_c('[truth: ' + d['truth_level'] + ']', _D)}")
        if d.get("inner_meaning"):
            print(f"    {_c('inner:', _CY)} {d['inner_meaning']}")
        if d.get("rules"):
            cb = d["rules"].get("countered_by")
            if cb:
                print(f"    {_c('countered by:', _CY)} {', '.join(cb)}")
            for b in d["animation_hints"]["behaviors"][:3]:
                print(f"    • {b}")
        if d.get("gaps"):
            print(_c(f"    gaps: {'; '.join(d['gaps'][:2])}", _D))
        return r

    def render_fight(self, astra, defender, action="resist") -> dict:
        r = combat_mod.encounter(self.seeker, astra, defender, action, self.mem)
        d = r["data"]
        res = d["resolution"]
        col = _GRN if res["outcome"] == "neutralized" else _RED if res["outcome"] == "devastating" else _GOLD
        print()
        print(f"  {self.seeker.name} fires {_c(astra, _B)} at {defender} ({action})")
        print(f"    {_c('→ ' + res['outcome'], col)} — {res.get('reason', '')}")
        banner = _c("CANON", _GRN) if d["is_canon"] else _c("EARLY DRAFT", _GOLD)
        print(f"    [{banner}]  grounding: {d['grounding']['confidence']}")
        for w in d["draft_warnings"]:
            mark = _c("⚠", _RED) if w["severity"] == "blocking" else _c("·", _D)
            print(_c(f"    {mark} {w['message']}", _D))
        return r


# --- a scripted demo (also the test path: deterministic, no input) ------------

def demo(memory: Memory) -> dict:
    """A non-interactive walk that exercises the full loop — returns a summary
    so a test can assert the harness drives the engine end to end."""
    g = Game(memory)
    out = {}
    print(_c("\n  T H E   A W A K E N E R  —  vertical slice\n", _B))

    # 1. stand in a scene
    s = g.render_scene(location="Kurukshetra", act="act2_vishnu")
    out["scene_ok"] = s["success"]

    # 2. read the saga of a warrior the texts know richly
    sa = g.render_saga("Ashvatthama")
    out["saga_ok"] = sa["success"]
    out["saga_strands"] = len(sa["data"]["carries"]) if sa["success"] else 0

    # 3. inspect a weapon, true to the teeth
    w = g.render_weapon("Gandiva")
    out["weapon_truth"] = w["data"]["truth_level"]

    # 4. a fight, with its honesty banner
    f = g.render_fight("Brahmastra", "Ashwatthama", "counter_with:Brahmastra")
    out["fight_outcome"] = f["data"]["resolution"]["outcome"]
    out["fight_is_canon"] = f["data"]["is_canon"]

    print()
    return out


def main():
    if not os.path.exists(_GRAPH):
        print(f"Graph not found at {_GRAPH}")
        return 1
    mem = Memory.load(_GRAPH, _RAM)
    demo(mem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
