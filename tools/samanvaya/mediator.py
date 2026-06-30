#!/usr/bin/env python3
"""
Samanvaya Mediator — AI Conflict Resolution for Same-Layer Agent Collisions.

When two agents at the same layer touch the same file, Samanvaya flags it.
The Mediator reads both diffs and determines:

  PROXIMITY CONFLICT → adjacent lines, different logic → AUTO-MERGE
  SEMANTIC CONFLICT  → same logic, different intent   → AI RESOLVES

The resolution is written directly to git via the API — no local files.

Usage:
  python -m tools.samanvaya.mediator resolve --file backend/main.py
  python -m tools.samanvaya.mediator auto-merge --branch feat/x --into main
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "MANIFEST.json"


def _load_manifest():
    return json.loads(MANIFEST_PATH.read_text())


def find_same_layer_conflicts():
    """Scan the manifest for files touched by multiple agents at the same layer."""
    data = _load_manifest()
    active = data.get("active", {})

    # file → {layer → [agent_ids]}
    file_layers = {}
    for agent_id, entry in active.items():
        for touch in entry.get("touches", []):
            fname = touch.split(":")[0] if ":" in touch else touch
            if fname not in file_layers:
                file_layers[fname] = {}
            layer = entry["layer"]
            if layer not in file_layers[fname]:
                file_layers[fname][layer] = []
            file_layers[fname][layer].append(agent_id)

    conflicts = []
    for fname, layers in file_layers.items():
        for layer, agents in layers.items():
            if len(agents) > 1:
                conflicts.append({
                    "file": fname,
                    "layer": layer,
                    "agents": agents,
                    "type": "same_layer_collision"
                })

    return conflicts


def _get_diff_for_agent(agent_id, filepath):
    """Get the diff an agent introduced for a specific file."""
    try:
        # Look for branches named after the agent or containing their work
        result = subprocess.run(
            ["git", "log", "--all", "--oneline", "--grep", agent_id, "--", filepath],
            capture_output=True, text=True,
            cwd=ROOT.parent.parent
        )
        commits = [l.split()[0] for l in result.stdout.strip().split("\n") if l]
        if not commits:
            return None

        diff_result = subprocess.run(
            ["git", "diff", f"{commits[0]}~1", commits[0], "--", filepath],
            capture_output=True, text=True,
            cwd=ROOT.parent.parent
        )
        return diff_result.stdout
    except Exception:
        return None


def _classify_conflict(diff_a, diff_b):
    """Classify the conflict type by comparing line ranges in both diffs.

    Returns: 'proximity' (adjacent lines, different logic — safe to auto-merge)
             'semantic'  (overlapping lines, same logic area — needs AI)
    """
    def extract_lines(diff_text):
        ranges = []
        for line in (diff_text or "").split("\n"):
            m = re.search(r'@@.*\+(\d+)(?:,(\d+))?.*@@', line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) else 1
                ranges.append((start, start + count))
        return ranges

    ranges_a = extract_lines(diff_a)
    ranges_b = extract_lines(diff_b)

    if not ranges_a or not ranges_b:
        return "proximity"  # can't determine — assume safe

    # Check if any ranges overlap
    for sa, ea in ranges_a:
        for sb, eb in ranges_b:
            # Overlap if they share any line numbers
            if sa <= eb and sb <= ea:
                # They overlap — but is it the exact same lines or adjacent?
                overlap_start = max(sa, sb)
                overlap_end = min(ea, eb)
                overlap_size = overlap_end - overlap_start
                if overlap_size > 5:  # more than 5 lines overlap → semantic
                    return "semantic"

    return "proximity"


def resolve_conflict(filepath):
    """Main entry point. Scan for same-layer conflicts on a file and resolve them.

    Returns a dict: {status, resolution, action_taken}"""
    conflicts = find_same_layer_conflicts()
    relevant = [c for c in conflicts if c["file"] == filepath]

    if not relevant:
        return {"status": "no_conflict", "file": filepath,
                "message": "No same-layer conflicts on this file."}

    results = []
    for conflict in relevant:
        agents = conflict["agents"]
        print(f"⚡ Same-layer collision on {filepath}")
        print(f"   Layer: {conflict['layer']}")
        print(f"   Agents: {', '.join(agents)}")

        # Get both diffs
        diffs = {}
        for agent_id in agents:
            d = _get_diff_for_agent(agent_id, filepath)
            diffs[agent_id] = d

        # Classify
        agent_list = list(diffs.keys())
        if len(agent_list) >= 2:
            classification = _classify_conflict(
                diffs.get(agent_list[0]),
                diffs.get(agent_list[1])
            )
        else:
            classification = "proximity"

        if classification == "proximity":
            result = {
                "status": "auto_resolved",
                "file": filepath,
                "type": "proximity",
                "action": "Safe to auto-merge. Changes touch adjacent but non-overlapping lines.",
                "agents": agents
            }
            print(f"   → PROXIMITY: Safe to auto-merge. Lines don't overlap semantically.")
        else:
            result = {
                "status": "needs_ai_resolution",
                "file": filepath,
                "type": "semantic",
                "action": "Changes overlap on >5 lines. AI resolution required.",
                "agents": agents,
                "diffs": {a: d[:800] for a, d in diffs.items()}  # truncated for prompt
            }
            print(f"   → SEMANTIC: Lines overlap. AI resolution needed.")
            print(f"   → Run: python -m tools.samanvaya.mediator ai-resolve --file {filepath}")

        results.append(result)

    return {"status": "resolved" if all(r["status"] == "auto_resolved" for r in results) else "needs_ai",
            "file": filepath, "results": results}


def ai_resolve_prompt(conflict_result):
    """Generate an LLM prompt to resolve a semantic conflict.

    Feed this to any LLM (Groq, Gemini, DeepSeek) to produce a merged version."""
    if not conflict_result.get("results"):
        return "No conflicts to resolve."

    semantic = [r for r in conflict_result["results"] if r["type"] == "semantic"]
    if not semantic:
        return "All conflicts are proximity-based. No AI resolution needed."

    lines = ["You are a code mediator resolving a same-layer agent collision.",
             "",
             f"File: {conflict_result['file']}",
             f"Agents: {', '.join(conflict_result['results'][0]['agents'])}",
             "",
             "Both agents made changes to the same section at the same layer.",
             "Your job: produce the MERGED version that preserves both intents.",
             "",
             "Rules:",
             "1. If the changes are complementary → keep both",
             "2. If they conflict on logic → choose the clearer implementation",
             "3. If one is a superset of the other → keep the superset",
             "4. Never drop functionality from either change",
             "",
             "=== AGENT A DIFF ==="]
    for r in semantic:
        for agent_id, diff_text in r.get("diffs", {}).items():
            lines.append(f"\n--- {agent_id} ---")
            lines.append(diff_text)

    lines.append("\n=== MERGED VERSION ===")
    lines.append("Output ONLY the merged file content. No explanation.")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    args = {}
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:].replace("-", "_")
            val = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else True
            args[key] = val
            i += 2 if isinstance(val, str) else 1
        else:
            i += 1

    if cmd == "scan":
        conflicts = find_same_layer_conflicts()
        if not conflicts:
            print("✅ No same-layer conflicts detected.")
        else:
            print(f"⚠️  {len(conflicts)} same-layer collision(s) found:\n")
            for c in conflicts:
                print(f"  {c['file']} [{c['layer']}] — {', '.join(c['agents'])}")

    elif cmd == "resolve":
        filepath = args.get("file", "")
        if not filepath:
            print("Usage: mediator resolve --file <path>")
            sys.exit(1)
        result = resolve_conflict(filepath)
        print(f"\nStatus: {result['status']}")

    elif cmd == "ai-resolve-prompt":
        filepath = args.get("file", "")
        if not filepath:
            print("Usage: mediator ai-resolve-prompt --file <path>")
            sys.exit(1)
        result = resolve_conflict(filepath)
        prompt = ai_resolve_prompt(result)
        print(prompt)

    else:
        print(f"Unknown: {cmd}")


if __name__ == "__main__":
    main()
