# Samanvaya (समन्वय)

> # Git tells you a file was touched. Samanvaya tells you whether the touch matters to your work.

---

The difference in one example:

```
Agent A declares: layer=buddhi,  touches=["main.py:1956-1994"]
Agent B declares: layer=mahat,   touches=["main.py:1936-1949"]

Git says:  "main.py modified by both → CONFLICT RISK"
Samanvaya: "Different layers, different sections → SAFE. Proceed."
```

Git's answer is always "maybe not — resolve it manually" because git doesn't know *why* a line was changed. Samanvaya adds the one thing git lacks: **the layer.** The layer tells you whether two changes to the same file can actually collide or not. Same layer touching same section → coordinate. Different layers touching different sections → git was always going to merge it cleanly anyway.

---

## How We Know the Decision Is Correct

A declaration is a claim. The agent SAYS it will touch lines X-Y at layer Z. But how do we verify this claim before it causes damage?

### The Verify Command

```bash
python -m tools.samanvaya.check verify --id agent-alpha
```

This takes the agent's declared touches from MANIFEST, pulls their actual git diff, and checks:

1. **Did they touch files outside their declared scope?** → If yes, flag it. The declaration was incomplete.
2. **Did they touch lines outside their declared ranges?** → If yes, flag it. Other agents may have relied on those lines being untouched.
3. **Did they stay within their layer's natural territory?** → Cross-reference actual changes against the layer's defined scope.

Output:
```
✅ agent-alpha VERIFIED
   Declared:  backend/main.py:1956-1994
   Actual:    backend/main.py [+41 lines at 1956-1994]
   Files outside scope: none
   Lines outside range: none
   Layer consistency: buddhi changes are in buddhi territory

Or:

⚠️  agent-alpha DISCREPANCY
   Declared:  backend/main.py:1956-1994
   Actual:    backend/main.py [+41 lines at 1956-1994],
              backend/query_processor.py [+12 lines at 175-185]
   Files outside scope: backend/query_processor.py
   → Agent touched a file they didn't declare. Declaration was incomplete.
```

### The Verification Is Public

MANIFEST.json is tracked in git. Every agent's declaration is committed alongside their code. Other agents can run `verify` against any completed entry and see whether the agent did what they said they would. A discrepancy is visible to everyone. This creates the incentive to declare accurately.

### The Layer Boundary Is Enforced by Git

The layer system doesn't replace git's merge — it sits on top of it. If two agents at the same layer touch the same lines, git correctly flags a conflict and a human resolves it. If two agents at different layers touch different lines, git merges cleanly and Samanvaya confirms the merge was safe. The verification step catches the case where an agent's declaration was wrong — before the wrong declaration causes another agent to make a bad decision.

---

## The Layers

| Layer | Function | Natural territory |
|-------|----------|-------------------|
| **Manas** | Retrieval, search, indexing | `search.py`, RAG orchestration, query embedding |
| **Buddhi** | Synthesis, reasoning, prompts | `buddhi.py`, prompt templates, synthesis block |
| **Mahat** | Graph, relationships, RAM keys | `graph_memory.py`, `recall.py`, RAM management |
| **Puruṣa** | Query understanding, intent | `query_processor.py` expansion, seeker context |
| **Brahman** | Corpus, embeddings, data | `data/chunks/`, embeddings, raw texts |

## The Three Granthis

```
Brahma (declare) → Vishnu (publish on branch) → Rudra (merge + verify)
```

## Commands

```bash
python -m tools.samanvaya.check declare --layer buddhi --id agent-x \
    --touches "backend/buddhi.py,backend/main.py:1956-1994"

python -m tools.samanvaya.check safe --file backend/main.py

python -m tools.samanvaya.check status

python -m tools.samanvaya.check progress --id agent-x --granthi vishnu

python -m tools.samanvaya.check complete --id agent-x

python -m tools.samanvaya.check verify --id agent-x
```
