# Samanvaya — समन्वय (Multi-Agent Coordination Protocol)

> # Git tells you a file was touched. Samanvaya tells you whether the touch matters to your work.

---

## Terminology Map (Vedic → Tech)

Every concept has a standard engineering equivalent. The Vedic name is the
canonical term in this codebase; the bracket shows what it maps to:

| Vedic Term | Tech Equivalent | What It Means Here |
|------------|----------------|---------------------|
| **Samanvaya** (समन्वय) | Multi-Agent Coordination Protocol | The system itself — agents coordinate through layer declarations |
| **Manas** (मनस्) | Retrieval Layer / RAG Pipeline | Surfaces facts from the corpus. Owns `search.py`, `hybrid_search` |
| **Buddhi** (बुद्धि) | Synthesis Layer / Reasoning Engine | Discriminates, resolves, synthesizes. Owns `buddhi.py`, prompt templates |
| **Mahat** (महत्) | Knowledge Graph / Structural Intelligence | Cross-domain relationships. Owns `graph_memory.py`, `recall.py`, RAM keys |
| **Puruṣa** (पुरुष) | Query Understanding / Intent Router | The witnessing attention. Owns `query_processor.py` expansion, seeker context |
| **Brahman** (ब्रह्मन्) | Corpus / Embedding Store / Training Data | The ground. Owns `data/chunks/`, embeddings, raw texts |
| **Granthi** (ग्रन्थि) | Stage / Phase / Gate | Work progresses through three visible gates |
| **Brahma-granthi** | Declaration Phase / Intent Registration | Agent declares intent. No code yet. Visible to all. |
| **Vishnu-granthi** | Publication Phase / Branch Push | Code on branch. Visible for review. |
| **Rudra-granthi** | Verification Phase / Merge + Lineage Record | Verified, merged, lineage recorded. |
| **Lineage** (परम्परा) | File Ownership Registry / Code Owners | Who last touched each file, at what layer |
| **MANIFEST.json** | Coordination State / Agent Registry | Single source of truth for all active work |

---

## How It Works

The difference in one example:

```
Agent A: layer=buddhi (Synthesis Layer),  touches=["main.py:1956-1994"]
Agent B: layer=mahat (Knowledge Graph),   touches=["main.py:1936-1949"]

Git says:  "main.py modified by both → CONFLICT RISK"
Samanvaya: "Different layers, different sections → SAFE. Proceed."
```

Git's answer is always "maybe not — resolve it manually" because git has no
semantic information — it only sees lines, not *why* those lines were changed.
Samanvaya adds the layer declaration (semantic boundary / concern boundary).
The layer tells you whether two changes to the same file can actually collide.

---

## The Verification Mechanism (How We Know Declarations Are Correct)

A declaration is a claim. The agent SAYS it will touch lines X-Y at layer Z.
The `verify` command (diff audit / declaration checker) cross-references the
actual git diff against the declared scope:

```bash
python -m tools.samanvaya.check verify --id agent-alpha
```

Checks performed:

1. **File scope check** — Did the agent touch files outside declared scope? (scope violation detection)
2. **Line range check** — Did the agent touch lines outside declared ranges? (range violation detection)
3. **Layer consistency check** — Do the actual changes match the layer's natural territory? (layer boundary enforcement)

Output:
```
✅ agent-alpha VERIFIED
   Declared:  backend/main.py:1956-1994
   Actual:    backend/main.py [+41 lines at 1956-1994]
   Files outside scope: none       ← no scope violation
   Lines outside range: none       ← no range violation

⚠️  agent-alpha DISCREPANCY
   Declared:  backend/main.py:1956-1994
   Actual:    backend/main.py [+41 lines],
              backend/query_processor.py [+12 lines]   ← UNDECLARED FILE
   → Scope violation. Declaration was incomplete.
```

MANIFEST.json (coordination state) is tracked in git. Every verification is
public. An agent whose diff doesn't match their declaration is visible to all
other agents. This creates the incentive to declare accurately (declaration
honesty via public audit trail).

---

## Conflict Resolution: The Mediator (Auto-Merge Engine)

When two agents at the same layer (semantic boundary) touch the same file,
the mediator (conflict classification engine) reads both diffs and classifies:

```
PROXIMITY CONFLICT (adjacent-line collision)
  → Lines don't semantically overlap (<5 lines shared)
  → AUTO-MERGE: git handles this mechanically
  → No coordination needed

SEMANTIC CONFLICT (same-logic collision)
  → Lines overlap on >5 lines in the same logic area
  → AI RESOLVE: mediator generates a structured LLM prompt
  → Feed prompt to any LLM → merged code produced
```

```bash
python -m tools.samanvaya.mediator scan           # detect all same-layer collisions
python -m tools.samanvaya.mediator resolve --file backend/main.py  # classify + resolve
python -m tools.samanvaya.mediator ai-resolve-prompt --file x.py  # generate LLM prompt
```

---

## Full Agent Lifecycle (CI/CD for AI Agents)

```
┌─ Brahma-granthi (Declaration Phase) ─────────────────────┐
│  agent start --layer buddhi --touches "..."              │
│  → Checks for same-layer collisions (conflict pre-check) │
│  → Adds entry to MANIFEST.json (agent registry)          │
│  → Intent visible to all other agents                    │
├─ Vishnu-granthi (Publication Phase) ─────────────────────┤
│  agent code --files "remote:local,..."                   │
│  → Creates blobs on GitHub via API (direct-to-remote)    │
│  → Creates tree → commit → updates branch ref            │
│  → Zero local git operations                             │
├─ Rudra-granthi (Verification Phase) ─────────────────────┤
│  agent finish                                            │
│  → verify: diff audit against declaration                │
│  → mediate: classify + auto-merge or AI-resolve          │
│  → complete: move to completed, record lineage           │
└──────────────────────────────────────────────────────────┘
```

## Commands

```bash
# Coordination (check.py — agent registry + safety checks)
python -m tools.samanvaya.check declare --layer buddhi --id agent-x \
    --touches "backend/buddhi.py,backend/main.py:1956-1994"
python -m tools.samanvaya.check safe --file backend/main.py
python -m tools.samanvaya.check status
python -m tools.samanvaya.check progress --id agent-x --granthi vishnu
python -m tools.samanvaya.check complete --id agent-x
python -m tools.samanvaya.check verify --id agent-x

# Full pipeline (agent.py — start → code → finish)
python -m tools.samanvaya.agent start --layer buddhi --touches "..."
python -m tools.samanvaya.agent code --message "..." --files "remote:local,..."
python -m tools.samanvaya.agent finish

# Mediation (mediator.py — conflict detection + resolution)
python -m tools.samanvaya.mediator scan
python -m tools.samanvaya.mediator resolve --file backend/main.py
python -m tools.samanvaya.mediator ai-resolve-prompt --file backend/main.py
```

## Dashboard (Live Visualization)

```bash
cd tools/samanvaya && python3 -m http.server 8765
# Open http://localhost:8765/dashboard.html
```

Shows all active agents organized by layer (semantic boundary), file conflict
status (cross-layer = safe/green, same-layer = warn/orange), granthi stages
(phase indicators), and lineage (file ownership registry). Auto-refreshes
every 5 seconds.
