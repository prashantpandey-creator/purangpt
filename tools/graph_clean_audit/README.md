# graph_clean_audit

Quantify the residual **relationship-quality** noise in the knowledge graph after
the interpretation-layer cleaning in `narrative_engine/character.py` (kin + guru
directionality, non-being/artifact filtering). Three hand-picked test entities
prove the fix on those three; this tool proves it across all ~24k edges and turns
"is the graph clean?" into a number plus an actionable worklist.

Pure decision tree over the edge list (Rule 0 → a tested script, not a sub-agent).
It **imports** `character.py`'s predicate sets (`_FAMILY_PREDS`, the guru pred
maps, `_NON_BEING_KINDS`, `_ARTIFACT_NAMES`) as the single source of truth, so it
measures exactly what the engine enforces — never a drifting re-declaration.

## Descriptor

```json
{
  "tool_name": "graph_clean_audit",
  "input_schema": {
    "graph_path": "str (default tools/read_pass/out/graph_manifest.json)",
    "ram_path":   "str (default tools/read_pass/out/guruji_ram.json)",
    "n_samples":  "int (default 5)",
    "edges":      "list|null (inject for fixture tests; else read from graph_path)",
    "entities":   "list|null (inject for fixture tests)"
  },
  "output_schema": {
    "n_edges": "int", "n_entities": "int",
    "kin":  "{n_edges, non_being_relations:{genuine,mistyped,samples_*}, direction_contradictions:{count,samples}}",
    "guru": "{n_edges, non_being_relations:{genuine,mistyped,samples_*}, direction_contradictions:{count,samples}}",
    "retype_candidates": "{count, samples:[{id,name,kind}]}",
    "self_loops": "{count, samples}",
    "summary": "{relationship_edges, violations, clean_pct, retype_candidates}"
  }
}
```

## The one distinction that makes the number mean something

A non-being entity in a relation is **two different problems**:

- **Genuine non-being** — a *practice* (`Kriya Yoga`) or *text* (`Ramayana`) or
  template artifact (`guru --initiates--> Śiṣya`) standing in a guru relation.
  This is real noise: the relation should be dropped. Counts as a **violation**.
- **Mis-typed being** — an entity the decoder typed `concept` that nevertheless
  has a *mother* (`Devaki`) or marries and has children (`Adharma`, a personified
  abstraction). Kin participation proves it is a character; the relation is fine,
  the **kind** is wrong. Counts as a **re-type candidate**, NOT a violation.

The separator is mechanical: *does the non-being entity appear in any kin edge?*
Conflating the two (an earlier version did) reports a misleading ~82% "clean";
splitting them reports the true ~97% plus a ~380-entity re-type worklist. This is
the FINDINGS-style lesson again: a correct envelope around the wrong measurement
is still wrong — validate the scope before trusting the number.

## Usage

```bash
# human summary
venv/bin/python -m tools.graph_clean_audit.check
# → CLEAN: 97.25% (199/7237 GENUINE violations; mis-typed beings excluded)
#   re-type candidates (mistyped beings): 380

# JSON envelope — consume data only (Rule 0)
venv/bin/python -m tools.graph_clean_audit.check --json
```

## Failure modes

| Condition | Envelope | Notes |
|-----------|----------|-------|
| graph manifest missing / unreadable / not JSON | `success:false`, `errors:[{code:"load_failed"}]`, `data:null` | bad `graph_path`; never raises |
| manifest lacks `edges`/`entities` keys | `success:false`, `errors:[{code:"load_failed"}]` | `KeyError` caught and reported |
| empty graph (0 relationship edges) | `success:true`, `summary.clean_pct = 100.0` | division guarded |
| an edge endpoint id not in `entities` | counted as a being (not a non-being) | unknown ≠ provable non-being; never silently drops |

## Tests

`venv/bin/python -m tools.graph_clean_audit.test_check` — synthetic fixtures with
one of each violation class (kin/guru contradiction, genuine non-being, mis-typed
being, self-loop) prove each detector counts correctly, plus a real-graph run
asserts the envelope shape and that the known offender `Kriya Yoga` is caught
while `Devaki` lands in `retype_candidates` (not as a violation).
