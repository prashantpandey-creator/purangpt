# traverse — multi-hop path finder over the graph (CONSCIOUSNESS_ROADMAP STEP 3, axis C)

Walks the real graph edges to assemble **whole multi-hop paths** —
`Krishna --[avatar]--> Vishnu --[wields]--> Sudarshana Chakra` — that `recall.py`'s
one-hop expansion structurally cannot produce. This is the consciousness bar
(memory `consciousness-over-rag`): the query daddy wants — *"which weapons were
god-given, by whom?"* — is a two-hop pattern, not a passage you can retrieve.
recall **clusters** a seed's neighbours; traverse **reasons** across hops.

Pure Rule-0 decision tree: zero LLM, zero network. Resolve start → bounded
depth-first walk → record terminal paths → report grounding.

## Usage

```bash
# all multi-hop chains from an entity (✓ marks the verse-grounded ones)
venv/bin/python -m tools.read_pass.traverse --symbol Krishna --hops 2 --json

# only chains you can defend with a verse
venv/bin/python -m tools.read_pass.traverse --symbol Vishnu --hops 2 --grounded-only

# constrain which relations a walk may follow (repeatable --rel)
venv/bin/python -m tools.read_pass.traverse --symbol Krishna --rel killed --hops 2
```

Programmatic (the same Memory recall/factsheet use; composes additively under decode):

```python
from tools.read_pass.recall import Memory
from tools.read_pass import traverse
mem = Memory.load("tools/read_pass/out/graph_manifest.json",
                  "tools/read_pass/out/guruji_ram.json")
env = traverse.traverse("Krishna", mem, max_hops=2, max_paths=50,
                        grounded_only=False)   # -> {success, data, metadata, errors}
env["data"]["paths"][0]   # {"hops":[{src_name,rel,dst_name,cites,...}], "length":2, "grounded":True}
```

## Why depth-first, and why "terminal-only"

A hub is huge (Krishna has 649 out-edges, ~4,461 two-hop chains). Under a bounded
result set, a **breadth-first** order lets the hub's hundreds of immediate
neighbours flood the budget before a single multi-hop chain completes — `max_paths`
fills with length-1 paths and the chains that are the whole point never appear.
So traverse goes **depth-first** and records a path only when it is **terminal**
(reached `max_hops`, or hit a dead end). Asking for `max_hops=2` therefore yields
2-hop reasoning, not a list of neighbours; `max_hops=1` still yields single-hop
paths (the "what did X kill?" query).

## The honesty discipline (why this is trustworthy)

Two guards make a path a *fact*, not a plausible story:
1. **Identity edges are not hops.** `alias` / `is` / `identical_to` / `same_as` /
   `aka` are cross-text IDENTITY (axis B, the merge logic's job) — a "path" made of
   aliases is one node wearing different names. They are skipped as traversal hops.
2. **Every hop's cites are verify-gated** (via `factsheet._grounded_cites`) — bare-
   number chunking garbage is dropped. Measured on the real graph, **only ~46% of
   paths are fully grounded** (43% have an uncited hop, 10% none). So each path
   carries a `grounded` flag (True iff *every* hop is verse-cited), `metadata`
   reports `n_grounded`/`n_paths`, and `grounded_only=True` returns solely the gold.
   A chain you can't cite is not handed back as if it were defensible.

No cycles: a path never revisits a node (the graph is full of loop-backs like
`Krishna --killed--> Putana --attempted_to_kill--> Krishna`).

## Failure modes

| Condition | `success` | `data.found` | Behavior |
|-----------|-----------|--------------|----------|
| empty/whitespace symbol | `false` | — | `errors:[{code:"empty"}]` — a misuse, not a fact about the graph |
| symbol not in graph | `true` | `false` | clean "don't know" — `paths:[]` |
| alias collision | `true` | `true` | start resolves to most-connected node (shared `factsheet._resolve` heuristic) |
| start has no walkable neighbours | `true` | `true` | `paths:[]` — nothing to traverse (all edges identity/filtered) |
| `grounded_only` but no grounded paths within budget | `true` | `true` | `paths:[]`, `n_grounded:0` — honest emptiness, not a fabricated cite |
| graph file missing (CLI) | raises at `Memory.load` | — | caller's problem (matches factsheet) |

## Contract

`input_schema`: `{symbol: str, memory: recall.Memory, max_hops: int=2, max_paths: int=50, rel_filter: set[str]|None, grounded_only: bool=False}`
`output_schema`: `data: {found: bool, start: str|null, paths: [{hops: [{src, rel, dst, src_name, dst_name, cites[]}], length: int, grounded: bool}]}`; `metadata: {max_hops, max_paths, rel_filter, grounded_only, start, n_paths, n_grounded}`

## Tests

`venv/bin/python -m tools.read_pass.test_traverse` (exit 0) — 15 assertions against
the REAL graph: envelope shape, a genuine 2-hop chain one-hop can't make, chain
connectivity, no cycles, identity-edges-not-hops, depth bound, rel filter, bounded
fan-out, grounded-cites-only, the per-path `grounded` flag matches reality,
`grounded_only`, and the metadata grounding counts.
