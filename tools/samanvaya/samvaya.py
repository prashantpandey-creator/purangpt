#!/usr/bin/env python3
"""
Samanvaya — AI-Native Multi-Agent Coordination.

ONE tool. Three things:
  safe    — "Can I touch this file right now?"
  resolve — "Resolve all conflicts automatically via LLM."
  watch   — "Watch and resolve continuously. Zero human touchpoints."
  status  — "Who is working on what?"

The system: Agents declare what they're working on before touching code.
If two agents touch the same file at different layers (different kinds of work)
→ SAFE, proceed. Git merges mechanically.
If two agents touch the same file at the SAME layer → LLM resolves automatically.
No human resolves a conflict. Ever.

Usage:
  python tools/samanvaya/samvaya.py safe --file backend/main.py
  python tools/samanvaya/samvaya.py status
  python tools/samanvaya/samvaya.py resolve
  python tools/samanvaya/samvaya.py watch
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "MANIFEST.json"
OWNER = "prashantpandey-creator"
REPO = "purangpt"

LAYER_LABELS = {
    "manas":   "Retrieval (search, indexing)",
    "buddhi":  "Synthesis (reasoning, prompts)",
    "mahat":   "Knowledge Graph (relationships, RAM keys)",
    "purusa":  "Intent (query understanding, routing)",
    "brahman": "Corpus (data, embeddings)",
}


# ═══════════════════════════════════════════════════════════════
# SAFE: Can I touch this file?
# ═══════════════════════════════════════════════════════════════

def cmd_safe(filepath):
    data = json.loads(MANIFEST.read_text())
    active = data.get("active", {})
    lineage = data.get("lineage", {})

    others = []
    for agent_id, entry in active.items():
        for touch in entry.get("touches", []):
            f = touch.split(":")[0] if ":" in touch else touch
            if f == filepath:
                lines = touch.split(":")[1] if ":" in touch else "entire file"
                others.append({"agent": agent_id, "layer": entry["layer"],
                               "stage": entry.get("granthi", "?"), "lines": lines})

    if not others:
        print(f"✅ SAFE — no one else is touching {filepath}")
        owner = lineage.get(filepath, "")
        if owner:
            print(f"   Last modified by: {owner}")
        return 0

    layers_here = set(o["layer"] for o in others)

    if len(layers_here) > 1:
        print(f"✅ SAFE — {len(others)} agent(s) also on {filepath}")
        print(f"   Different kinds of work: {', '.join(layers_here)}")
        print(f"   Their changes are in different sections. Git merges cleanly.")
        for o in others:
            print(f"   • {o['agent']} [{o['layer']}] {o['stage']} — {o['lines']}")
        return 0

    layer = list(layers_here)[0]
    print(f"⚡ CHECK — {len(others)} agent(s) doing the SAME kind of work on {filepath}")
    print(f"   Layer: {layer} ({LAYER_LABELS.get(layer, layer)})")
    for o in others:
        print(f"   • {o['agent']} — {o['stage']} — lines: {o['lines']}")
    print(f"")
    print(f"   If your lines DON'T overlap theirs → safe, proceed.")
    print(f"   If they DO → the auto-resolver will merge them via LLM.")
    print(f"   Run: python tools/samanvaya/samvaya.py resolve")
    return 1


# ═══════════════════════════════════════════════════════════════
# STATUS: Who is working on what?
# ═══════════════════════════════════════════════════════════════

def cmd_status():
    data = json.loads(MANIFEST.read_text())
    active = data.get("active", {})
    completed = data.get("completed", [])
    lineage = data.get("lineage", {})

    if not active:
        print("Field is clear. No active agents.")
        return

    by_layer = {}
    for agent_id, entry in active.items():
        by_layer.setdefault(entry["layer"], []).append((agent_id, entry))

    print(f"{'LAYER':<10} {'AGENT':<25} {'STAGE':<12} {'TOUCHING'}")
    print("-" * 75)
    for layer in ["manas", "buddhi", "mahat", "purusa", "brahman"]:
        agents = by_layer.get(layer, [])
        if not agents:
            continue
        label = LAYER_LABELS.get(layer, layer)
        for agent_id, entry in agents:
            g = entry.get("granthi", "?")
            files = ", ".join(entry.get("touches", [])[:3])
            print(f"{label:<10} {agent_id:<25} {g:<12} {files}")

    if completed:
        print(f"\nCompleted: {len(completed)}")
    if lineage:
        print(f"Lineage: {len(lineage)} files tracked")


# ═══════════════════════════════════════════════════════════════
# RESOLVE: Find conflicts → LLM resolves → commit
# ═══════════════════════════════════════════════════════════════

def find_conflicts():
    data = json.loads(MANIFEST.read_text())
    active = data.get("active", {})

    file_layer_agents = {}
    for agent_id, entry in active.items():
        for touch in entry.get("touches", []):
            fname = touch.split(":")[0] if ":" in touch else touch
            lines_str = touch.split(":")[1] if ":" in touch else None
            key = fname
            if key not in file_layer_agents:
                file_layer_agents[key] = {}
            layer = entry["layer"]
            if layer not in file_layer_agents[key]:
                file_layer_agents[key][layer] = []
            file_layer_agents[key][layer].append({
                "agent": agent_id, "lines": lines_str,
                "granthi": entry.get("granthi", "?"),
                "branch": entry.get("branch", ""),
                "commit": entry.get("commit", ""),
            })

    conflicts = []
    for fname, layers in file_layer_agents.items():
        for layer, agents in layers.items():
            if len(agents) < 2:
                continue
            ranges = []
            for a in agents:
                ls = str(a["lines"]) if a["lines"] else "1-99999"
                try:
                    parts = ls.split("-")
                    ranges.append((int(parts[0]), int(parts[1])))
                except:
                    ranges.append((0, 99999))

            overlaps = any(
                ranges[i][0] <= ranges[j][1] and ranges[j][0] <= ranges[i][1]
                for i in range(len(ranges)) for j in range(i + 1, len(ranges))
            )
            if overlaps:
                conflicts.append({"file": fname, "layer": layer, "agents": agents, "ranges": ranges})

    return conflicts


def call_llm(prompt):
    """Try each available provider. Returns merged text or None."""
    providers = []
    if os.environ.get("GROQ_API_KEY"):
        providers.append(("groq", "https://api.groq.com/openai/v1/chat/completions",
                          os.environ["GROQ_API_KEY"], "llama-3.3-70b-versatile"))
    if os.environ.get("DEEPSEEK_API_KEY"):
        providers.append(("deepseek", "https://api.deepseek.com/chat/completions",
                          os.environ["DEEPSEEK_API_KEY"], "deepseek-chat"))
    if os.environ.get("GEMINI_API_KEY"):
        providers.append(("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                          os.environ["GEMINI_API_KEY"], "gemini-2.5-flash"))

    import urllib.request
    for name, url, key, model in providers:
        try:
            body = json.dumps({
                "model": model, "temperature": 0.1, "max_tokens": 4000,
                "messages": [
                    {"role": "system", "content": "Merge code changes. Output only the merged file. No explanation."},
                    {"role": "user", "content": prompt}
                ]
            }).encode()
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}"
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"   {name}: {e}")
            continue
    return None


def commit_via_api(filepath, content, message):
    """Commit directly to GitHub. No local git."""
    import base64
    encoded = base64.b64encode(content.encode()).decode()

    def gh(args, input_data=None):
        result = subprocess.run(["gh", "api"] + args, capture_output=True, text=True,
                                input=input_data, cwd=ROOT.parent.parent)
        return result.stdout.strip()

    base_sha = gh(["repos/{}/{}/git/refs/heads/main".format(OWNER, REPO), "--jq", ".object.sha"])
    base_tree = gh(["repos/{}/{}/git/commits/{}".format(OWNER, REPO, base_sha), "--jq", ".tree.sha"])
    blob = gh(["repos/{}/{}/git/blobs".format(OWNER, REPO), "--method", "POST",
               "-f", "content=" + encoded, "-f", "encoding=base64", "--jq", ".sha"])
    tree_body = json.dumps({"base_tree": base_tree, "tree": [
        {"path": filepath, "mode": "100644", "type": "blob", "sha": blob}
    ]})
    new_tree = gh(["repos/{}/{}/git/trees".format(OWNER, REPO), "--method", "POST",
                   "--input", "-", "--jq", ".sha"], tree_body)
    commit_body = json.dumps({"message": message, "tree": new_tree, "parents": [base_sha]})
    new_commit = gh(["repos/{}/{}/git/commits".format(OWNER, REPO), "--method", "POST",
                     "--input", "-", "--jq", ".sha"], commit_body)
    gh(["repos/{}/{}/git/refs/heads/main".format(OWNER, REPO), "--method", "PATCH",
        "-f", "sha=" + new_commit])
    return new_commit


def cmd_resolve():
    conflicts = find_conflicts()

    if not conflicts:
        print("✅ No conflicts. Field is clean.")
        return

    print(f"Found {len(conflicts)} conflict(s)\n")

    for c in conflicts:
        agents_str = ", ".join(a["agent"] for a in c["agents"])
        overlap_size = max(0, min(c["ranges"][0][1], c["ranges"][1][1]) -
                          max(c["ranges"][0][0], c["ranges"][1][0]))
        ctype = "semantic" if overlap_size > 5 else "proximity"

        print(f"⚡ {c['file']} [{c['layer']}] — {agents_str}")
        print(f"   Overlap: {overlap_size} lines → {ctype.upper()}")

        if ctype == "proximity":
            print(f"   → Lines barely touch. Git handles this. Skipping.\n")
            continue

        print(f"   → LLM resolving...")

        # Get diffs
        diffs = {}
        for agent in c["agents"]:
            ref = agent.get("commit") or (f"origin/{agent['branch']}" if agent.get("branch") else "HEAD")
            try:
                r = subprocess.run(["git", "diff", f"{ref}~1", ref, "--", c["file"]],
                                   capture_output=True, text=True, timeout=10, cwd=ROOT.parent.parent)
                diffs[agent["agent"]] = r.stdout[:3000] if r.stdout else "(empty diff)"
            except:
                diffs[agent["agent"]] = "(unavailable)"

        prompt = f"""Two AI agents changed the same file at the same layer.

FILE: {c['file']}
LAYER: {c['layer']} ({LAYER_LABELS.get(c['layer'], c['layer'])})

Merge both changes. Keep complementary changes. If they conflict, choose the cleaner implementation. Never drop functionality.

=== {c['agents'][0]['agent']} ===
{diffs.get(c['agents'][0]['agent'], '')}

=== {c['agents'][1]['agent']} ===
{diffs.get(c['agents'][1]['agent'], '')}

Output ONLY the merged file. No explanation."""

        merged = call_llm(prompt)
        if not merged:
            print(f"   → FAILED. No LLM available.\n")
            continue

        msg = f"resolve: auto-merge {c['file']} [{c['layer']}] — {agents_str}\n\nResolved autonomously by Samanvaya. No human intervention."
        commit_sha = commit_via_api(c["file"], merged, msg)
        print(f"   → RESOLVED: {commit_sha[:12]}\n")

        # Update manifest
        data = json.loads(MANIFEST.read_text())
        for agent in c["agents"]:
            aid = agent["agent"]
            if aid in data.get("active", {}):
                data["active"].pop(aid)
                data.setdefault("completed", []).append(aid)
        data.setdefault("lineage", {})[c["file"]] = f"auto-resolve ({c['layer']})"
        MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    print("Done.")


# ═══════════════════════════════════════════════════════════════
# WATCH: Run continuously, resolve as conflicts appear
# ═══════════════════════════════════════════════════════════════

def cmd_watch():
    print("👁️  Samanvaya watching for conflicts...")
    print("   Detection → Classification → LLM Resolution → Commit")
    print("   Zero human touchpoints. Ctrl+C to stop.\n")

    seen = set()
    while True:
        try:
            conflicts = find_conflicts()
            for c in conflicts:
                key = f"{c['file']}:{c['layer']}"
                if key not in seen:
                    seen.add(key)
                    print(f"\n⚡ [{time.strftime('%H:%M:%S')}] {c['file']} [{c['layer']}]")
                    cmd_resolve()
                    break
            time.sleep(15)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(15)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

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

    if cmd == "safe":
        filepath = args.get("file", "")
        if not filepath:
            print("Usage: samvaya.py safe --file <path>")
            sys.exit(1)
        sys.exit(cmd_safe(filepath))
    elif cmd == "status":
        cmd_status()
    elif cmd == "resolve":
        cmd_resolve()
    elif cmd == "watch":
        cmd_watch()
    else:
        print(f"Unknown: {cmd}. Valid: safe, status, resolve, watch")
        sys.exit(1)
