"""adventure — text-adventure client for the narrative engine.

A minimal CLI that proves the full game loop works:
  enter location → see NPCs → talk → make choice → combat → move on

Runs entirely against the local graph (no server needed).
Usage: venv/bin/python -m narrative_engine.adventure
"""
from __future__ import annotations

import os
import random
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_pass.recall import Memory
from narrative_engine import world, character, combat, seeker, narrative

_GRAPH = "tools/read_pass/out/graph_manifest.json"
_RAM = "tools/read_pass/out/guruji_ram.json"

_DIVIDER = "─" * 60


def _wrap(text: str, indent: str = "  ") -> str:
    lines = textwrap.wrap(text, width=70)
    return "\n".join(indent + l for l in lines)


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def _gold(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def _cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


class Adventure:
    def __init__(self, mem: Memory):
        self.mem = mem
        self.sk = seeker.SeekerState()
        self.running = True

    def _prompt(self, msg: str = "> ") -> str:
        try:
            return input(_gold(msg)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            self.running = False
            return ""

    def _show_guna(self):
        g = self.sk.guna
        bar_s = "█" * int(g.sattva * 20)
        bar_r = "█" * int(g.rajas * 20)
        bar_t = "█" * int(g.tamas * 20)
        print(f"  Sattva {_green(bar_s)} {g.sattva:.0%}")
        print(f"  Rajas  {_gold(bar_r)} {g.rajas:.0%}")
        print(f"  Tamas  {_red(bar_t)} {g.tamas:.0%}")

    def _show_location(self, loc_name: str):
        r = world.location_detail(loc_name, self.mem)
        if not r["success"]:
            print(f"  {_dim('This place is unknown to the texts.')}")
            return

        d = r["data"]
        loc = d["location"]
        print(f"\n{_DIVIDER}")
        print(f"  {_bold(loc['name'])}  {_dim('(' + loc['kind'] + ')')}")
        if loc.get("aliases"):
            print(f"  {_dim('Also: ' + ', '.join(loc['aliases'][:5]))}")
        print(_DIVIDER)

        if d["residents"]:
            print(f"\n  {_cyan('Beings present:')}")
            for res in d["residents"][:10]:
                print(f"    • {res['name']} ({res['kind']}) — {res['relationship']}")

        if d["events"]:
            print(f"\n  {_cyan('What happened here:')}")
            for ev in d["events"][:5]:
                print(f"    • {ev['actor']} {ev['action']}")

        if d["connected_places"]:
            print(f"\n  {_cyan('Paths from here:')}")
            for cp in d["connected_places"][:8]:
                direction = cp.get("direction", "")
                d_str = f" [{direction}]" if direction else ""
                print(f"    → {cp['name']} ({cp['kind']}) via {cp['relationship']}{d_str}")

    def _show_character(self, name: str):
        r = character.character_sheet(name, self.mem)
        if not r["success"]:
            print(f"  {_dim('Unknown to the texts.')}")
            return

        d = r["data"]
        ident = d["identity"]
        print(f"\n{_DIVIDER}")
        print(f"  {_bold(ident['name'])}  {_dim('(' + ident.get('kind', '?') + ')')}")
        if ident.get("aliases"):
            print(f"  {_dim('Also: ' + ', '.join(ident['aliases'][:5]))}")
        ch_count = ident.get("chapters_present", 0)
        print(f"  {_dim(f'Present in {ch_count} chapters')}")
        print(_DIVIDER)

        if d["family"]:
            print(f"\n  {_cyan('Kin:')}")
            for f in d["family"][:8]:
                print(f"    • {f['name']} ({f['relationship']})")

        if d["weapons"]:
            print(f"\n  {_cyan('Weapons:')}")
            for w in d["weapons"][:5]:
                print(f"    • {w['name']} ({w['relationship']})")

        if d["boons"]:
            print(f"\n  {_cyan('Boons:')}")
            for b in d["boons"][:5]:
                print(f"    • {b['name']} ({b['relationship']})")

        if d["curses"]:
            print(f"\n  {_red('Curses:')}")
            for c in d["curses"][:5]:
                print(f"    • {c['name']} ({c['relationship']})")

        if d.get("literal_brief"):
            print(f"\n  {_cyan('The texts say:')}")
            print(_wrap(d["literal_brief"][:300]))

    def _do_meditate(self):
        print(f"\n  {_cyan('Whom do you offer tapasya to?')}")
        deity = self._prompt("  Deity: ")
        if not deity:
            return
        intensity = 1.0
        try:
            ans = self._prompt("  Intensity (1-5): ")
            if ans:
                intensity = max(1.0, min(5.0, float(ans)))
        except ValueError:
            pass

        self.sk.meditate(deity, intensity)
        tap = self.sk.tapasya.get(deity)
        print(f"\n  {_green('You meditate...')}")
        print(f"  Tapasya accumulated for {deity}: {tap.accumulated:.1f}")
        print(f"  Sessions: {tap.sessions}")
        self._show_guna()

    def _do_combat(self):
        print(f"\n  {_cyan('Astra combat')}")
        astra = self._prompt("  Your weapon: ")
        if not astra:
            return
        rules = combat.get_astra_rules(astra)
        if not rules["success"]:
            print(f"  {_dim('That astra is not known to the texts.')}")
            return

        r = rules["data"]["rules"]
        print(f"\n  {_bold(r['name'])}")
        if r.get("restrictions"):
            print(f"  {_dim('Restrictions: ' + ', '.join(r['restrictions']))}")
        if r.get("special_rules"):
            for s in r["special_rules"]:
                print(f"    • {s}")

        defender = self._prompt("  Target: ")
        if not defender:
            return
        action = self._prompt("  Their action (resist/surrender/counter_with:<astra>): ") or "resist"

        result = combat.resolve_attack(self.sk.name or "Seeker", astra, defender, action, self.mem)
        d = result["data"]
        outcome = d.get("outcome", "unknown")
        color = _green if outcome == "neutralized" else _red if outcome == "devastating" else _gold
        print(f"\n  {color('Outcome: ' + outcome)}")
        print(f"  {d.get('reason', '')}")

    def _do_choice(self):
        desc = self._prompt("  What event? ")
        if not desc:
            return
        fork = narrative.dharmic_fork(desc, [
            {"label": "Act with dharma", "guna_shift": {"sattva": 0.05, "rajas": 0.02}},
            {"label": "Act with passion", "guna_shift": {"rajas": 0.08, "tamas": 0.02}},
            {"label": "Withdraw and wait", "guna_shift": {"tamas": 0.05, "sattva": 0.02}},
        ])
        options = fork["data"]["options"]
        for i, opt in enumerate(options, 1):
            shifts = opt.get("guna_shift", {})
            shift_str = ", ".join(f"{k}+{v:.0%}" for k, v in shifts.items() if v)
            print(f"  [{i}] {opt['label']}  {_dim(shift_str)}")

        choice = self._prompt("  Choose (1-3): ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                chosen = options[idx]
                self.sk.make_choice(
                    f"choice_{len(self.sk.choices)}",
                    desc,
                    chosen["label"],
                    chosen.get("guna_shift", {}),
                    chosen.get("consequences", [])
                )
                print(f"\n  {_gold('You chose: ' + chosen['label'])}")
                self._show_guna()
        except (ValueError, IndexError):
            print("  Invalid choice.")

    def run(self):
        print(f"\n{'═' * 60}")
        print(f"  {_bold('P U R A N I C   A D V E N T U R E')}")
        print(f"  {_dim('Powered by the Sutradhar knowledge graph')}")
        print(f"{'═' * 60}")

        name = self._prompt("\n  What is your name, seeker? ") or "Seeker"
        self.sk.name = name
        print(f"\n  {_gold(f'Welcome, {name}. The cosmos awaits.')}")
        self._show_guna()

        # find starting locations
        locs = world.list_locations(self.mem)["data"]["locations"]
        start_locs = [l for l in locs[:50] if l["chapters"] >= 5]
        if start_locs:
            print(f"\n  {_cyan('Choose your starting location:')}")
            shown = start_locs[:8]
            for i, l in enumerate(shown, 1):
                print(f"  [{i}] {l['name']} ({l['kind']}, {l['chapters']} chapters)")
            loc_choice = self._prompt("  Enter number or name: ")
            try:
                idx = int(loc_choice) - 1
                if 0 <= idx < len(shown):
                    self.sk.current_location = shown[idx]["name"]
            except ValueError:
                self.sk.current_location = loc_choice or shown[0]["name"]
        else:
            self.sk.current_location = "Ayodhya"

        self.sk.move_to(self.sk.current_location)

        while self.running:
            self._show_location(self.sk.current_location)

            print(f"\n  {_bold('Actions:')}")
            print("  [l]ook around   [t]alk to someone   [m]editate")
            print("  [c]hoice        [f]ight              [j]ourney (follow a character)")
            print("  [g]o somewhere  [s]tatus             [q]uit")

            cmd = self._prompt("\n  ").lower()

            if cmd in ("q", "quit", "exit"):
                print(f"\n  {_gold('The cosmos remembers you, ' + self.sk.name + '.')}")
                self.running = False

            elif cmd in ("l", "look"):
                pass  # location is re-shown at top of loop

            elif cmd in ("t", "talk"):
                who = self._prompt("  Talk to whom? ")
                if who:
                    self._show_character(who)

            elif cmd in ("m", "meditate"):
                self._do_meditate()

            elif cmd in ("c", "choice"):
                self._do_choice()

            elif cmd in ("f", "fight"):
                self._do_combat()

            elif cmd in ("j", "journey"):
                who = self._prompt("  Follow whose journey? ")
                if who:
                    r = world.character_journey(who, self.mem, limit=10)
                    if r["success"] and r["data"]["locations"]:
                        char_path = r['data']['character'] + "'s path:"
                        print(f"\n  {_cyan(char_path)}")
                        for i, loc in enumerate(r["data"]["locations"][:8], 1):
                            print(f"  [{i}] {loc['name']} ({loc['kind']}, {loc['shared_chapters']} chapters)")
                        pick = self._prompt("  Go to which? ")
                        try:
                            idx = int(pick) - 1
                            jlocs = r["data"]["locations"][:8]
                            if 0 <= idx < len(jlocs):
                                dest = jlocs[idx]["name"]
                                self.sk.move_to(dest)
                                self.sk.current_location = dest
                        except (ValueError, IndexError):
                            pass
                    else:
                        print(f"  {_dim('That character is unknown to the texts.')}")

            elif cmd in ("g", "go"):
                dest = self._prompt("  Where to? ")
                if dest:
                    r = world.location_detail(dest, self.mem)
                    if r["success"]:
                        self.sk.move_to(dest)
                        self.sk.current_location = dest
                    else:
                        print(f"  {_dim('That place is unknown to the texts.')}")

            elif cmd in ("s", "status"):
                print(f"\n  {_bold(self.sk.name)}")
                print(f"  Location: {self.sk.current_location}")
                print(f"  Visited: {len(self.sk.visited_locations)} places")
                self._show_guna()
                if self.sk.tapasya:
                    print(f"\n  {_cyan('Tapasya:')}")
                    for deity, tap in self.sk.tapasya.items():
                        print(f"    • {deity}: {tap.accumulated:.1f} ({tap.sessions} sessions)")
                if self.sk.boons:
                    print(f"\n  {_green('Boons:')}")
                    for b in self.sk.boons:
                        print(f"    • {b['name']} from {b['source']}")
                if self.sk.curses:
                    print(f"\n  {_red('Curses:')}")
                    for c in self.sk.curses:
                        print(f"    • {c['name']} from {c['source']}")
                if self.sk.choices:
                    print(f"\n  {_gold('Dharmic choices:')}")
                    for ch in self.sk.choices[-5:]:
                        print(f"    • {ch.description}: {ch.choice}")

            else:
                if cmd:
                    print(f"  {_dim('Unknown command. Try l/t/m/c/f/j/g/s/q')}")


def main():
    if not os.path.exists(_GRAPH):
        print(f"Graph not found at {_GRAPH}")
        return 1

    mem = Memory.load(_GRAPH, _RAM)
    print(f"Loaded: {len(mem.entities)} entities, {len(mem.edges)} edges")

    adventure = Adventure(mem)
    adventure.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
