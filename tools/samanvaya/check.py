#!/usr/bin/env python3
"""
Samanvaya — Multi-Agent Coordination via Vedic Layer Architecture.

Git merges lines. Samanvaya prevents semantic conflicts before they reach git.
Each agent declares its layer before touching code. Layers are the boundary.

Usage:
  python -m tools.samanvaya.check declare --layer buddhi --id my-session \\
      --touches "backend/buddhi.py,backend/main.py:1956-1994"

  python -m tools.samanvaya.check status

  python -m tools.samanvaya.check safe --file backend/main.py

  python -m tools.samanvaya.check progress --id my-session --granthi vishnu

  python -m tools.samanvaya.check complete --id my-session
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "MANIFEST.json"


def _load():
    return json.loads(MANIFEST_PATH.read_text())


def _save(data):
    MANIFEST_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def cmd_declare(args):
    """Register active work. Other agents see this and know what layer you're at."""
    layer = args.layer
    agent_id = args.id or f"agent-{os.getpid()}"
    touches = [t.strip() for t in (args.touches or "").split(",") if t.strip()]

    data = _load()
    layers = data["_layers"]
    if layer not in layers:
        print(f"❌ Unknown layer '{layer}'. Valid layers: {list(layers.keys())}")
        sys.exit(1)

    data["active"][agent_id] = {
        "layer": layer,
        "since": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "touches": touches,
        "granthi": "brahma",
    }
    _save(data)

    print(f"✅ Declared: {agent_id}")
    print(f"   Layer: {layer} — {layers[layer]['function']}")
    print(f"   Touches: {touches or '(none specified)'}")
    print(f"   Granthi: brahma (intent visible, no code yet)")
    print()
    _show_conflict_summary(data, agent_id)


def cmd_status(_args):
    """Show all active work, organized by layer."""
    data = _load()

    if not data["active"]:
        print("No active work. The field is clear.")
        return

    print("Active work by layer:")
    for layer_name, layer_info in data["_layers"].items():
        agents_in_layer = {k: v for k, v in data["active"].items() if v["layer"] == layer_name}
        if not agents_in_layer:
            continue
        print(f"\n  {layer_name} — {layer_info['function']}")
        for agent_id, entry in agents_in_layer.items():
            g = entry["granthi"]
            touches_str = ", ".join(entry["touches"][:4]) if entry["touches"] else "no files declared"
            print(f"    [{g}] {agent_id}")
            print(f"         since {entry['since']}")
            print(f"         touches: {touches_str}")

    if data["completed"]:
        print(f"\n  Completed: {', '.join(data['completed'][-5:])}")

    if data["lineage"]:
        print(f"\n  File lineage (last modifier):")
        for fpath, owner in list(data["lineage"].items())[-8:]:
            print(f"    {fpath} → {owner}")


def cmd_safe(args):
    """Check if a file is safe to touch — returns layer info, not just yes/no."""
    target = args.file
    data = _load()

    conflicts = []
    for agent_id, entry in data["active"].items():
        for touch in entry.get("touches", []):
            touched_file = touch.split(":")[0] if ":" in touch else touch
            if touched_file == target or (":" in touch and target == touch.split(":")[0]):
                conflicts.append((agent_id, entry))

    if not conflicts:
        print(f"✅ {target} is free. No active agent has declared it.")
        lineage_owner = data["lineage"].get(target)
        if lineage_owner:
            print(f"   Lineage: last touched by {lineage_owner}")
        return

    for agent_id, entry in conflicts:
        my_layer = entry["layer"]
        print(f"⚠️  {target} is declared by {agent_id}")
        print(f"   Their layer: {my_layer} — {data['_layers'][my_layer]['function']}")
        print(f"   Granthi stage: {entry['granthi']}")
        print(f"   Their touches: {', '.join(entry['touches'][:5])}")
        print()
        print(f"   → If YOU are at a DIFFERENT layer and touching a DIFFERENT section,")
        print(f"     this is safe. Layers are the boundary, not files.")
        print(f"   → If you are at the SAME layer ({my_layer}), coordinate before proceeding.")


def cmd_progress(args):
    """Advance through the three granthis (declare → publish → merge)."""
    agent_id = args.id
    granthi = args.granthi

    if granthi not in ("brahma", "vishnu", "rudra"):
        print(f"❌ Invalid granthi '{granthi}'. Valid: brahma, vishnu, rudra")
        sys.exit(1)

    data = _load()
    if agent_id not in data["active"]:
        print(f"❌ '{agent_id}' not found in active work. Run 'declare' first.")
        sys.exit(1)

    data["active"][agent_id]["granthi"] = granthi
    _save(data)

    granthi_meanings = {
        "brahma": "intent declared, no code yet",
        "vishnu": "code published on branch, visible for review",
        "rudra": "verified, ready for merge to main",
    }
    print(f"✅ {agent_id} → {granthi} ({granthi_meanings[granthi]})")


def cmd_complete(args):
    """Finish work. Move active → completed, update file lineage."""
    agent_id = args.id
    data = _load()

    if agent_id not in data["active"]:
        print(f"❌ '{agent_id}' not found in active work.")
        sys.exit(1)

    entry = data["active"].pop(agent_id)
    data["completed"].append(agent_id)

    # Update lineage: record this agent as the last modifier of each touched file
    for touch in entry.get("touches", []):
        fpath = touch.split(":")[0] if ":" in touch else touch
        data["lineage"][fpath] = f"{agent_id} ({entry['layer']})"

    _save(data)

    print(f"✅ {agent_id} completed.")
    print(f"   Layer: {entry['layer']}")
    print(f"   Files registered in lineage: {', '.join(entry.get('touches', [])[:5]) or 'none'}")
    print(f"   Remaining active agents: {len(data['active'])}")


def cmd_verify(args):
    """Verify an agent's actual diff against their declared touches.

    Takes the agent's declared scope from MANIFEST, pulls the real git diff,
    and checks: did they touch files outside scope? Lines outside range?"""
    import subprocess

    agent_id = args.id
    commit = getattr(args, "commit", "HEAD")

    data = _load()

    # Find the agent in active or completed
    entry = data["active"].get(agent_id)
    source = "active"
    if not entry:
        # Check completed list
        if agent_id in data["completed"]:
            # Use lineage to reconstruct what they touched
            entry = {
                "layer": "unknown",
                "touches": [f"{f}:ALL" for f in data["lineage"] if agent_id in data["lineage"].get(f, "") or agent_id in str(data["lineage"].get(f, ""))],
            }
            source = "completed (reconstructed from lineage)"
        else:
            # Try lineage directly
            declared_files = [f for f, owner in data["lineage"].items() if agent_id in owner]
            if declared_files:
                entry = {"layer": "unknown", "touches": declared_files}
                source = "lineage"
            else:
                print(f"❌ '{agent_id}' not found in active, completed, or lineage.")
                sys.exit(1)

    declared_files = set()
    declared_ranges = {}  # file → [(start, end), ...]
    for touch in entry.get("touches", []):
        if ":" in touch:
            fpath, range_str = touch.split(":", 1)
            declared_files.add(fpath)
            declared_ranges.setdefault(fpath, [])
            try:
                if "-" in range_str:
                    s, e = range_str.split("-")
                    declared_ranges[fpath].append((int(s), int(e)))
                else:
                    declared_ranges[fpath].append((int(range_str), int(range_str)))
            except ValueError:
                pass
        else:
            declared_files.add(touch)

    if not declared_files:
        print(f"❌ No declared files found for '{agent_id}'.")
        sys.exit(1)

    print(f"🔍 Verifying {agent_id} [{source}]")
    print(f"   Layer: {entry.get('layer', 'unknown')}")
    print(f"   Declared touches: {', '.join(entry.get('touches', [])[:8])}")
    print()

    # Get actual diff
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", f"{commit}~1", commit] if commit != "HEAD" else ["git", "diff", "--stat", "HEAD~1", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent.parent
        )
        diff_stat = result.stdout.strip()
    except Exception:
        print("⚠️  Could not get git diff. Is this a git repository?")
        sys.exit(1)

    if not diff_stat:
        print("⚠️  No diff found. Nothing to verify.")
        return

    # Parse diff stat: "file.py | 12 +++"
    actual_files = set()
    for line in diff_stat.split("\n"):
        if "|" in line:
            fpath = line.split("|")[0].strip()
            actual_files.add(fpath)

    # Check 1: files outside declared scope
    undeclared = actual_files - declared_files
    declared_but_untouched = declared_files - actual_files

    # Check 2: line ranges (approximate from diff)
    line_range_ok = True
    if declared_ranges:
        try:
            range_diff = subprocess.run(
                ["git", "diff", f"{commit}~1", commit, "--"] + list(declared_files),
                capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent.parent
            )
            # Parse @@ -old,new +new,count @@ headers
            import re
            actual_lines = {}  # file → set of line numbers touched
            current_file = None
            for line in range_diff.stdout.split("\n"):
                if line.startswith("+++ b/"):
                    current_file = line[6:]
                    actual_lines.setdefault(current_file, set())
                elif line.startswith("@@") and current_file:
                    m = re.search(r'\+(\d+)(?:,(\d+))?', line)
                    if m:
                        start = int(m.group(1))
                        count = int(m.group(2)) if m.group(2) else 1
                        for ln in range(start, start + count):
                            actual_lines[current_file].add(ln)

            for fpath, ranges in declared_ranges.items():
                if fpath not in actual_lines:
                    continue
                actual_set = actual_lines[fpath]
                for d_start, d_end in ranges:
                    declared_set = set(range(d_start, d_end + 1))
                    # We check: are there lines declared that weren't touched? (fine)
                    # Are there lines touched that weren't declared? (flag)
                    touched_outside = actual_set - declared_set
                    if touched_outside and len(touched_outside) > 3:  # small tolerance
                        line_range_ok = False
                        sample = sorted(touched_outside)[:5]
                        print(f"   ⚠️  {fpath}: touched lines outside declared range {d_start}-{d_end}")
                        print(f"       Undeclared lines: {sample}...")
        except Exception:
            pass  # Range check is best-effort

    # Report
    if not undeclared and not declared_but_untouched and line_range_ok:
        print("✅ VERIFIED — declaration matches actual diff")
        print(f"   Files changed: {len(actual_files)}")
        for f in sorted(actual_files):
            print(f"      {f}")
    else:
        print("⚠️  DISCREPANCY — declaration doesn't match actual diff")
        if undeclared:
            print(f"   Files touched but NOT declared: {', '.join(sorted(undeclared))}")
        if declared_but_untouched:
            print(f"   Files declared but NOT touched: {', '.join(sorted(declared_but_untouched))}")
        if not line_range_ok:
            print(f"   Line ranges: declared ranges do not cover all touched lines")
        print()
        print("   → Other agents may have relied on inaccurate scope declarations.")
        print("   → Update the manifest or narrow your changes.")


def _show_conflict_summary(data, current_agent):
    """After declare, show any same-layer agents touching the same files."""
    me = data["active"].get(current_agent)
    if not me:
        return

    my_layer = me["layer"]
    my_files = set(t.split(":")[0] if ":" in t else t for t in me.get("touches", []))

    for agent_id, entry in data["active"].items():
        if agent_id == current_agent:
            continue
        their_files = set(t.split(":")[0] if ":" in t else t for t in entry.get("touches", []))
        shared = my_files & their_files

        if shared and entry["layer"] == my_layer:
            print(f"⚠️  SAME-LAYER overlap with {agent_id}:")
            print(f"   Shared files: {', '.join(shared)}")
            print(f"   Both at layer '{my_layer}'. Coordinate before proceeding.")
        elif shared:
            print(f"ℹ️  CROSS-LAYER overlap with {agent_id}:")
            print(f"   Shared files: {', '.join(shared)}")
            print(f"   You: {my_layer}  |  Them: {entry['layer']}")
            print(f"   Different layers → safe. Git will merge mechanically.")


# ── CLI ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    # Parse --key value args
    args = type("Args", (), {})()
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:].replace("-", "_")
            val = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else True
            setattr(args, key, val)
            i += 2 if isinstance(val, str) else 1
        else:
            i += 1

    commands = {
        "declare": cmd_declare,
        "status": cmd_status,
        "safe": cmd_safe,
        "progress": cmd_progress,
        "complete": cmd_complete,
        "verify": cmd_verify,
    }

    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print(f"Valid: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[cmd](args)


if __name__ == "__main__":
    main()
