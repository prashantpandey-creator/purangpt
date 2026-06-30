# linkify_check

Loads the **real** `linkifyTerms()` / `GLOSSARY` from
`src/lib/sanskritGlossary.ts` (transpiled in-memory with the TS compiler — no
re-implementation) and reports which Sanskrit terms a given answer would get
auto-linked. Pins the "organic, meaningful" highlighting rules so they can't
silently regress.

## Tool descriptor

```json
{
  "tool_name": "linkify_check",
  "input_schema": {
    "type": "object",
    "properties": { "markdown": { "type": "string" } },
    "required": ["markdown"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "linked":   { "type": "array", "items": {
        "type": "object",
        "properties": { "term": {"type":"string"}, "slug": {"type":"string"} } } },
      "count":    { "type": "integer" },
      "maxLinks": { "type": "integer" },
      "output":   { "type": "string" }
    },
    "required": ["linked", "count", "maxLinks", "output"]
  }
}
```

## The rules it guards

- **Common-vocab words are never auto-linked** — `yoga`, `karma`, `om`, `guru`,
  `dharma`, `maya`, `samsara`, `chakra`, `kundalini`, `mantra`, `avatar`,
  `nirvana`, `moksha`, `ananda`, `shakti` (flagged `common: true` in the
  glossary). A seeker already knows them; linking them is noise.
- **Only genuinely unfamiliar terms link** — `vairagya`, `viveka`, `santosha`,
  `prakriti`, `purusha`, `sadhana`, … the words that actually expand vocabulary.
- **Hard cap of `MAX_LINKS` (3) per answer.** Invitation, not index.
- **One link per term**, and **code spans / existing links are untouched.**

## Usage

```bash
# from purangpt-next/ repo root
node tools/linkify_check/linkify_check.mjs --text "Your dharma needs vairagya."
node tools/linkify_check/linkify_check.mjs --text "..." --json
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| `markdown` not a string | `success=false`, `errors=[{code:"bad_input"}]`, exit 2 |
| Normal | `success=true`, exit 0 |

## Tests

`node tools/linkify_check/test_linkify_check.mjs` — must exit 0. Asserts:
common-only text links nothing, esoteric terms do link, the density cap holds,
each term links once, protected spans are left verbatim, and a realistic mixed
answer glows only its unfamiliar words.
