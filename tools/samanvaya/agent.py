#!/usr/bin/env python3
"""
Samanvaya Agent — Complete Multi-Agent Workflow.

The full pipeline for an AI agent working on this repo:

  1. DECLARE  → add entry to MANIFEST.json (layer, files, intent)
  2. SAFE?    → check if declared files have same-layer collisions
  3. CODE     → write code directly to git via GitHub API (no local fs)
  4. PUBLISH  → push to feature branch, advance to vishnu granthi
  5. VERIFY   → check actual diff against declared touches
  6. MEDIATE  → if same-layer conflict, classify + auto-merge or AI-resolve
  7. COMPLETE → merge to main, record lineage

Usage:
  python -m tools.samanvaya.agent start --layer buddhi \\
      --touches "backend/buddhi.py,backend/main.py:1956-1994"

  python -m tools.samanvaya.agent code --message "feat: add synthesis layer" \\
      --files "backend/buddhi.py:./local/buddhi.py,backend/main.py:./local/main.py"

  python -m tools.samanvaya.agent finish
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "MANIFEST.json"

AGENT_ID = os.environ.get("SAMANVAYA_AGENT_ID", f"agent-{os.getpid()}")
OWNER = "prashantpandey-creator"
REPO = "purangpt"


# ── Manifest helpers ───────────────────────────────────────────

def _load():
    return json.loads(MANIFEST_PATH.read_text())


def _save(data):
    MANIFEST_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ── Step 1: DECLARE ────────────────────────────────────────────

def cmd_start(args):
    """Declare intent before touching any file."""
    layer = args.get("layer", "")
    touches = [t.strip() for t in (args.get("touches", "") or "").split(",") if t.strip()]

    data = _load()
    layers = data.get("_layers", {})
    if layer not in layers:
        print(f"❌ Unknown layer '{layer}'. Valid: {list(layers.keys())}")
        sys.exit(1)

    # Check for same-layer collisions BEFORE declaring
    active = data.get("active", {})
    same_layer_hits = []
    for agent_id, entry in active.items():
        if entry["layer"] != layer:
            continue
        their_files = set(t.split(":")[0] if ":" in t else t for t in entry.get("touches", []))
        my_files = set(t.split(":")[0] if ":" in t else t for t in touches)
        shared = their_files & my_files
        if shared:
            same_layer_hits.append((agent_id, list(shared)))

    if same_layer_hits:
        print(f"⚠️  SAME-LAYER COLLISION DETECTED")
        for agent_id, shared in same_layer_hits:
            print(f"   {agent_id} also touches: {', '.join(shared)}")
        print()
        print(f"   Options:")
        print(f"   1. Proceed anyway — mediator will resolve at merge time")
        print(f"   2. Wait for {same_layer_hits[0][0]} to complete")
        print(f"   3. Narrow your scope to avoid these files")

        choice = input("   Choice [1/2/3]: ").strip() if sys.stdin.isatty() else "1"
        if choice == "2":
            print("   Waiting... re-run 'start' when the other agent completes.")
            sys.exit(0)
        elif choice == "3":
            print("   Narrow your --touches and re-run.")
            sys.exit(0)
        # choice 1: proceed — mediator handles it later

    data["active"][AGENT_ID] = {
        "layer": layer,
        "since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "touches": touches,
        "granthi": "brahma",
    }
    _save(data)

    print(f"✅ {AGENT_ID} declared at layer '{layer}'")
    print(f"   Touches: {touches}")
    print(f"   Granthi: brahma — intent visible, safe to start coding.")
    print(f"   Next: agent code --message '...' --files 'file1:local1,file2:local2'")


# ── Step 2: CODE (direct to git via API) ────────────────────────

def cmd_code(args):
    """Write files directly to GitHub via Git Data API. No local fs.

    --files format: "remote_path:local_path,remote_path:local_path"
    Each local_path is read, base64-encoded, and sent as a blob to GitHub.
    A new tree + commit is created on the specified branch."""
    message = args.get("message", "feat: agent commit via Samanvaya")
    files_arg = args.get("files", "")
    branch = args.get("branch", f"feat/{AGENT_ID}")
    base_branch = args.get("base", "main")

    if not files_arg:
        print("❌ --files required. Format: 'remote:local,remote:local'")
        sys.exit(1)

    pairs = []
    for pair in files_arg.split(","):
        parts = pair.strip().split(":", 1)
        if len(parts) == 2:
            pairs.append((parts[0].strip(), parts[1].strip()))

    if not pairs:
        print("❌ No valid file pairs.")
        sys.exit(1)

    print(f"📡 Coding directly to GitHub via API — zero local writes")
    print(f"   Branch: {branch} (from {base_branch})")
    print(f"   Files: {len(pairs)}")

    # Step A: Get base tree SHA
    import base64 as b64

    # Get the base ref SHA
    try:
        base_sha_result = subprocess.run(
            ["gh", "api", f"repos/{OWNER}/{REPO}/git/refs/heads/{base_branch}",
             "--jq", ".object.sha"],
            capture_output=True, text=True, check=True
        )
        base_sha = base_sha_result.stdout.strip()
    except Exception:
        # Try creating from main if base branch doesn't exist
        base_sha_result = subprocess.run(
            ["gh", "api", f"repos/{OWNER}/{REPO}/git/refs/heads/main",
             "--jq", ".object.sha"],
            capture_output=True, text=True, check=True
        )
        base_sha = base_sha_result.stdout.strip()

    base_tree_result = subprocess.run(
        ["gh", "api", f"repos/{OWNER}/{REPO}/git/commits/{base_sha}",
         "--jq", ".tree.sha"],
        capture_output=True, text=True, check=True
    )
    base_tree = base_tree_result.stdout.strip()
    print(f"   Base tree: {base_tree[:12]}...")

    # Step B: Create blobs for each file
    tree_entries = []
    for remote_path, local_path in pairs:
        local_file = Path(local_path)
        if not local_file.exists():
            print(f"   ⚠️  {local_path} not found — skipping")
            continue

        content = local_file.read_bytes()
        encoded = b64.b64encode(content).decode()

        blob_result = subprocess.run(
            ["gh", "api", f"repos/{OWNER}/{REPO}/git/blobs",
             "--method", "POST",
             "-f", f"content={encoded}",
             "-f", "encoding=base64",
             "--jq", ".sha"],
            capture_output=True, text=True, check=True
        )
        blob_sha = blob_result.stdout.strip()
        tree_entries.append({
            "path": remote_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha
        })
        print(f"   📄 {remote_path} → blob {blob_sha[:12]}...")

    if not tree_entries:
        print("❌ No files were successfully blobbed.")
        sys.exit(1)

    # Step C: Create tree
    tree_body = json.dumps({"base_tree": base_tree, "tree": tree_entries})
    tree_result = subprocess.run(
        ["gh", "api", f"repos/{OWNER}/{REPO}/git/trees",
         "--method", "POST", "--input", "-", "--jq", ".sha"],
        input=tree_body, capture_output=True, text=True, check=True
    )
    new_tree = tree_result.stdout.strip()
    print(f"   🌳 Tree: {new_tree[:12]}...")

    # Step D: Create commit
    commit_body = json.dumps({
        "message": message,
        "tree": new_tree,
        "parents": [base_sha]
    })
    commit_result = subprocess.run(
        ["gh", "api", f"repos/{OWNER}/{REPO}/git/commits",
         "--method", "POST", "--input", "-", "--jq", ".sha"],
        input=commit_body, capture_output=True, text=True, check=True
    )
    new_commit = commit_result.stdout.strip()
    print(f"   📝 Commit: {new_commit[:12]}...")

    # Step E: Create or update branch ref
    try:
        subprocess.run(
            ["gh", "api", f"repos/{OWNER}/{REPO}/git/refs/heads/{branch}",
             "--method", "PATCH", "-f", f"sha={new_commit}", "-f", "force=false"],
            capture_output=True, text=True, check=True
        )
        print(f"   🔀 Updated branch: {branch}")
    except Exception:
        # Branch doesn't exist — create it
        subprocess.run(
            ["gh", "api", f"repos/{OWNER}/{REPO}/git/refs",
             "--method", "POST",
             "-f", f"ref=refs/heads/{branch}",
             "-f", f"sha={new_commit}"],
            capture_output=True, text=True, check=True
        )
        print(f"   🔀 Created branch: {branch}")

    # Step F: Update manifest — advance to vishnu
    data = _load()
    if AGENT_ID in data.get("active", {}):
        data["active"][AGENT_ID]["granthi"] = "vishnu"
        data["active"][AGENT_ID]["branch"] = branch
        data["active"][AGENT_ID]["commit"] = new_commit
        _save(data)

    print(f"")
    print(f"✅ Code committed directly to GitHub — no local git operations")
    print(f"   Branch: {branch}")
    print(f"   Commit: {new_commit}")
    print(f"   Next: agent finish")


# ── Step 3: FINISH (verify + mediate + complete) ────────────────

def cmd_finish(args):
    """Verify declaration, mediate conflicts if any, merge, complete."""
    data = _load()
    if AGENT_ID not in data.get("active", {}):
        print(f"❌ {AGENT_ID} not active. Run 'start' first.")
        sys.exit(1)

    entry = data["active"][AGENT_ID]
    branch = entry.get("branch", f"feat/{AGENT_ID}")
    commit = entry.get("commit", "")

    print(f"🏁 Finishing {AGENT_ID}...")
    print(f"   Layer: {entry['layer']}")
    print(f"   Branch: {branch}")

    # Step A: Verify
    print(f"\n── Verification ──")
    from tools.samanvaya.check import cmd_verify as verify
    verify_args = type("Args", (), {"id": AGENT_ID, "commit": commit})()
    try:
        verify(verify_args)
    except SystemExit:
        pass

    # Step B: Mediate — check for same-layer conflicts
    print(f"\n── Mediation ──")
    from tools.samanvaya.mediator import find_same_layer_conflicts, resolve_conflict

    conflicts = find_same_layer_conflicts()
    my_conflicts = [c for c in conflicts if AGENT_ID in c.get("agents", [])]

    if not my_conflicts:
        print("✅ No same-layer conflicts involving this agent.")
    else:
        for c in my_conflicts:
            print(f"⚡ Conflict on {c['file']} with {[a for a in c['agents'] if a != AGENT_ID]}")
            result = resolve_conflict(c["file"])
            if result["status"] == "needs_ai":
                print(f"   ⚠️  Semantic conflict — run 'mediator ai-resolve-prompt --file {c['file']}'")
                print(f"   Feed the prompt to an LLM and commit the resolution.")
                choice = input("   Skip and complete anyway? [y/N]: ").strip().lower() if sys.stdin.isatty() else "n"
                if choice != "y":
                    print("   Aborting. Resolve the conflict first.")
                    sys.exit(0)

    # Step C: Complete
    print(f"\n── Completion ──")
    data = _load()
    entry = data["active"].pop(AGENT_ID, None)
    if entry:
        data["completed"].append(AGENT_ID)
        for touch in entry.get("touches", []):
            fname = touch.split(":")[0] if ":" in touch else touch
            data["lineage"][fname] = f"{AGENT_ID} ({entry['layer']})"
        _save(data)

    print(f"✅ {AGENT_ID} completed.")
    print(f"   Files in lineage: {', '.join(entry.get('touches', [])[:5])}")
    print(f"   Remaining active: {len(data.get('active', {}))}")


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

    commands = {
        "start": cmd_start,
        "code": cmd_code,
        "finish": cmd_finish,
    }

    if cmd not in commands:
        print(f"Unknown: {cmd}. Valid: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[cmd](args)


if __name__ == "__main__":
    main()
