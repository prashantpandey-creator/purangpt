# persona_extractor

Assemble a **talkable persona** for the chat/`talk-to-the-gods` path from the
knowledge-graph layers — the graph-grounded replacement for the hand-written
`GURUJI_PERSONALITY` constant in `backend/main.py`. Guruji is entity #1 in the
same machine that voices Krishna, Shiva, Vyasa, Hanuman, …

**One extractor, N personas.** Substance (identity / lineage / kin / deeds) comes
from the graph edges; the inner/esoteric layer comes from the 613-key Guruji RAM
codex; the VOICE/register is carried separately by injecting the persona's own
retrieved passages into `{context}` (the `voice` field is that retrieval scope).

## Descriptor

```json
{
  "tool_name": "persona_extractor",
  "input_schema":  { "persona_id": "string (registry slug, or '' for the roster)" },
  "output_schema": {
    "persona_id": "string", "display": "string", "epithet": "string",
    "identity": { "name": "string", "kind": "string", "aliases": ["string"], "chapters": "int" },
    "lineage": [ { "name": "string", "role": "guru|disciple" } ],
    "kin":     [ { "name": "string", "relation": "string (POV-normalized)" } ],
    "deeds":   [ { "name": "string", "relation": "string", "as": "outgoing|incoming" } ],
    "inner_meaning": "string|null",
    "voice":   { "corpus_type": "guruji|scripture" },
    "block":   "string (prompt-ready text for the {personality} slot)"
  }
}
```

Envelope is always `{success, data, metadata, errors}`.

## Why a curated registry (the load-bearing decision)

Free-text resolution over 9,006 entities mis-casts. `recall("Shailendra Sharma")`
matched the **mountain** Shailendra (father of Ganga, husband of Menaka) on the
shared name fragment — it would hand Guruji a mountain's persona. `REGISTRY` pins
each persona to an **exact entity id**, which both fixes resolution and doubles as
the curated god-roster the UI renders. Adding a god = one registry row (verify the
`entity_id` exists in the graph first).

## Usage

```bash
# the roster (what the UI lists)
venv/bin/python -m tools.persona_extractor.check --json

# one persona, full envelope
venv/bin/python -m tools.persona_extractor.check --persona shiva --json

# human-readable prompt block
venv/bin/python -m tools.persona_extractor.check --persona guruji

# tests (real-graph fixtures)
venv/bin/python -m tools.persona_extractor.test_check
```

In-process (how `backend/main.py` should call it — pass the already-loaded graph
singleton so it never re-reads 9 MB):

```python
from tools.persona_extractor.check import run
env = run("krishna", memory=graph_singleton)   # consume env["data"]["block"]
```

## Failure modes

| Condition | Envelope | code |
|---|---|---|
| `persona_id` not in `REGISTRY` | `success:false`, `data:null` | `unknown_persona` |
| graph file missing / won't load | `success:false`, `data:null` | `no_graph` |
| registry `entity_id` absent from graph | `success:false`, `data:null` | `entity_not_found` |
| RAM symbol is a placeholder ("Not mentioned…") | `success:true`, `inner_meaning:null` | — (filtered, not an error) |
| kin edge in reciprocal convention (Parvati as "husband") | `success:true`, relation POV-normalized to "wife" | — (corrected) |

## Known data warts (graph-side, not tool bugs)

- Guruji's node carries a stray alias **"Lord of the Mountains"** (mountain bleed
  from a merge) and his mother appears as two un-merged nodes (Gyani Devi /
  Shrimati Gyani Devi Sharma). Identity-merge cleanup, tracked separately.
- `deeds` direction is associative only (the rel verb is shown but not POV-fixed);
  `render_persona_block` drops deed direction to avoid asserting a wrong arrow.
