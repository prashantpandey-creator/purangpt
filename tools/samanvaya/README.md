# Samanvaya — AI-Native Multi-Agent Coordination

> **Git tells you a file was changed. Samanvaya tells you whether that change matters to your work — and if it does, an LLM resolves it automatically.**

---

## The Problem

8 AI agents work on the same codebase. They all touch `main.py`. Git sees "same file modified → conflict risk" and can't tell the difference between two agents changing completely unrelated sections vs. two agents editing the exact same function.

The result: agents hesitate, humans get pulled in to resolve "conflicts" that git would have merged cleanly, and real conflicts still need manual resolution.

## The Solution

Before touching any file, an agent asks one question: **"Is anyone else working on this?"**

```
$ python tools/samanvaya/samvaya.py safe --file backend/main.py

✅ SAFE — 3 agent(s) also on backend/main.py
   Different kinds of work: manas, mahat, buddhi
   Their changes are in different sections. Git merges cleanly.
   Proceed.
```

Three agents on the same file. Zero coordination needed. Because they're doing **different kinds of work** at **different line ranges.** Git handles it mechanically.

When two agents DO touch the same section:

```
⚡ CHECK — 2 agents doing the SAME kind of work on backend/buddhi.py
   Lines 1956-1994 overlap with 1950-1970 → SEMANTIC conflict
   → LLM resolves automatically. No human needed.
```

## How It Works

```
Agent declares: "I'm working on main.py:1956-1994, layer=buddhi (synthesis code)"
                │
                ▼
Other agent:    samvaya.py safe --file main.py
                → "3 agents here, all different layers → SAFE"
                → Proceeds immediately. No wait. No coordination.
                │
                ▼
If same-layer:  samvaya.py resolve
                → LLM reads both diffs
                → Merges complementary changes
                → Commits resolution directly to GitHub
                → Zero human touchpoints
```

## Layers = Kinds of Work

"Layer" just means **what kind of code you're writing.** It's not philosophy — it's file sections.

| Layer | What it means | Example files |
|-------|--------------|---------------|
| **manas** | Retrieval code | `search.py`, RAG pipeline |
| **buddhi** | Synthesis code | `buddhi.py`, prompt templates |
| **mahat** | Graph code | `graph_memory.py`, RAM keys |
| **purusa** | Intent code | `query_processor.py`, routing |
| **brahman** | Data code | `data/chunks/`, embeddings |

Two agents in different layers can touch the same file safely because they're working on different *concerns.* A retrieval change and a synthesis change in `main.py` don't collide — they're in different sections, doing different things.

## Commands

```bash
# Before touching any file
python tools/samanvaya/samvaya.py safe --file backend/main.py

# See all active agents
python tools/samanvaya/samvaya.py status

# Resolve all conflicts via LLM (automatic)
python tools/samanvaya/samvaya.py resolve

# Watch continuously — resolve conflicts as they appear
python tools/samanvaya/samvaya.py watch
```

## Dashboard

```bash
cd tools/samanvaya && python3 -m http.server 8765
# Open http://localhost:8765/dashboard.html
```

Shows agents by layer, active conflicts, and resolution status. Auto-refreshes.

## What Makes This Different

| Traditional Git Workflow | Samanvaya |
|--------------------------|-----------|
| `git status` → see modified files → guess if safe | `safe --file` → instant yes/no |
| Discover conflicts at merge time | Same-layer collisions flagged at declaration |
| Human resolves every conflict | LLM resolves automatically, commits via API |
| No way to know who's working on what | MANIFEST.json is the live coordination state |
| Passive — you check when you remember | `watch` mode — resolves continuously |

## The Core Insight

**Most "conflicts" in a multi-agent codebase aren't real conflicts.** They're just multiple agents touching the same file at different places for different reasons. Git can't distinguish these from real conflicts because git is semantically blind. Samanvaya adds one piece of information — the layer (kind of work) — and that single addition eliminates most coordination overhead.

For the conflicts that ARE real (same kind of work, same section), an LLM resolves them. No human in the loop.
