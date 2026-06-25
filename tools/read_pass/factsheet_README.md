# factsheet — literal-layer assembler for decode()

Resolves a symbol to its graph entity and returns the **literal layer** — identity
(name, forms, kind), grounded verse cites, and named relationships — for `decode()`
to consult BEFORE it generates. This is the Gandiva fix: decode no longer floats
into pure mysticism ignorant of the fact that Gandiva is Arjuna's bow.

Pure Rule-0 decision tree: zero LLM, zero network. Resolve → gather → filter → assemble.

## Usage

```bash
venv/bin/python -m tools.read_pass.factsheet --symbol Gandiva --json
```

Programmatic (how `decode.py` uses it):

```python
from tools.read_pass.recall import Memory
from tools.read_pass import factsheet
mem = Memory.load("tools/read_pass/out/graph_manifest.json",
                  "tools/read_pass/out/guruji_ram.json")
env = factsheet.factsheet("Gandiva", mem)   # -> {success, data, metadata, errors}
env["data"]["brief"]   # "Literally, Gandiva (Arjuna's bow, Dhanur...) — Arjuna wields Gandiva [bhp_01.01.008]..."
```

## The honesty discipline (why this is trustworthy)

The graph's `verse_ranges` are **polluted** with bare-number garbage (`17`, `5-6`,
`61.4`) that lost its marker prefix during chunking. factsheet runs every cite
through `verify._MARKER_RE` and keeps ONLY canonical markers. A literal layer that
cited "verse 17" of nothing would be a confident liar. `metadata.raw_cites` vs
`metadata.grounded_cites` reports how much was dropped.

## Failure modes

| Condition | `success` | `data.found` | Behavior |
|-----------|-----------|--------------|----------|
| empty/whitespace symbol | `false` | — | `errors:[{code:"empty"}]` |
| symbol not in graph | `true` | `false` | clean "don't know" — empty identity/relationships, `brief:""` |
| alias collision (e.g. "Bharata") | `true` | `true` | resolves to most-connected node; heuristic, `metadata.resolution` flags it |
| entity has only polluted cites | `true` | `true` | `grounded_cites:0`; brief still names identity but carries no marker — decode must not over-assert |
| graph file missing (CLI) | raises at `Memory.load` | — | caller's problem; decode's `_literal_facts` swallows it → ungrounded mode |

## Contract

`input_schema`: `{symbol: str, memory: recall.Memory}`
`output_schema`: `data: {found: bool, query: str, identity: {canonical, kind, forms[], cites[], id} | null, relationships: [{src_name, rel, dst_name, cites[]}], brief: str}`
