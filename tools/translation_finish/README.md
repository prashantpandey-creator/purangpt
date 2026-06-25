# translation_finish

Finish a **batch-translated book**: gather the windows already translated by the
parallel agent batches, translate ONLY the missing windows (the ones whose batch
died), splice all windows back in strict order, assemble the `.md`, and gate on a
healthy EN/RU character ratio. Replaces the manual decision-tree of "which
windows are missing? translate just those, re-stitch, sanity-check the length,
swap." Born from the bio re-translation where 2 of 12 batches died (24 holes) and
the Gita was never batched at all.

## Tool descriptor

```json
{
  "tool_name": "translation_finish",
  "input_schema": {
    "type": "object",
    "properties": {
      "src_path":  { "type": "string", "description": "Russian source .txt" },
      "out_dir":   { "type": "string", "description": "dir containing agent_batches/*_OUT.json" },
      "out_md":    { "type": "string", "description": "where to write the assembled English .md" },
      "caller":    { "type": "object", "description": "RU→EN translator fn (injected; DeepSeek in CLI). None → only-gather (every window is 'missing' if no caller can fill it)" },
      "api_key":   { "type": "string" },
      "model":     { "type": "string", "default": "deepseek-chat" },
      "max_chars": { "type": "integer", "default": 12000, "description": "window size; MUST match the size the batches used or indices misalign" },
      "min_ratio": { "type": "number", "default": 0.4, "description": "assembled EN/RU ratio floor; below this = still-gutted, success=false" }
    },
    "required": ["src_path", "out_dir", "out_md"]
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "out_md":           { "type": "string" },
      "n_windows_total":  { "type": "integer" },
      "missing_indices":  { "type": "array", "items": { "type": "integer" } },
      "n_translated_now": { "type": "integer" },
      "gaps_remaining":   { "type": "integer" },
      "ratio":            { "type": "number" },
      "src_chars":        { "type": "integer" },
      "out_chars":        { "type": "integer" }
    },
    "required": ["out_md", "n_windows_total", "missing_indices", "gaps_remaining", "ratio"]
  }
}
```

## Output envelope

```json
{ "success": true,
  "data": { "out_md": ".../the_awakener_EN_v2.md", "n_windows_total": 120,
            "missing_indices": [10,11,...,89], "n_translated_now": 24,
            "gaps_remaining": 0, "ratio": 0.81, "src_chars": 1359347, "out_chars": 1103750 },
  "metadata": { "model": "deepseek-chat" }, "errors": [] }
```

`success` is true **only when** `gaps_remaining == 0` AND `ratio >= min_ratio` AND
no window hard-failed. Otherwise the `.md` is still written (so you can inspect)
but `success=false` — do NOT swap it over the original.

## Usage

```bash
# from purangpt/ repo root — fill the bio's dead-batch holes via DeepSeek
venv/bin/python -m tools.translation_finish.check \
  --src data/raw_texts/sharma_ru/mossin_awakener_ru.txt \
  --out-dir tools/read_pass/translations \
  --out-md  tools/read_pass/translations/the_awakener_EN_v2.md \
  --json

# full fresh translation (empty out-dir → every window 'missing')
venv/bin/python -m tools.translation_finish.check \
  --src data/raw_texts/sharma_ru/gita_ru.txt \
  --out-dir tools/read_pass/translations/gita_finish \
  --out-md  tools/read_pass/translations/yogeshwari_gita_EN_v2.md --json
```

As a library (inject any caller — Gemini, a stub, etc.):

```python
from tools.translation_finish.check import run
from tools.read_pass import translate
caller = translate.make_openai_caller(base_url="https://api.deepseek.com/v1")
env = run(src_path=src, out_dir=d, out_md=out, caller=caller, api_key=key)
if env["success"]:   # zero gaps + healthy ratio → safe to swap
    ...
```

## Failure modes

| Condition | Behavior |
|-----------|----------|
| Source file missing/unreadable | `success=false`, `errors=[{code:"read_error"}]`, exit 2 |
| Source empty | `success=false`, `errors=[{code:"empty_source"}]`, exit 2 |
| A missing window can't be translated honestly (cyrillic echo / truncation / no caller) | that window stays a `[[TRANSLATION GAP i]]`; `errors+=[{code:"window_failed","message":"win i: ..."}]`; `gaps_remaining>0`; `success=false`, exit 1 |
| Assembled EN/RU ratio `< min_ratio` | `errors+=[{code:"ratio_too_low"}]`; `.md` written for inspection but `success=false`, exit 1 |
| `out_md` dir unwritable | `success=false`, `errors=[{code:"write_error"}]`, exit 2 |
| All windows filled + ratio healthy | `success=true`, exit 0 — safe to swap |

**Index alignment is load-bearing:** `max_chars` MUST equal the value the batches
used (12000 for the bio) or `make_windows` produces different boundaries and the
gathered good windows land in the wrong slots. Verified once that
`make_windows(12000)[10]` == `bio_batch_01.windows[0]` before trusting the splice.

## Tests

`venv/bin/python -m tools.translation_finish.test_check` (exit 0) — 9 tests over
tempdir fixtures + a fake caller (no network): missing-index diff, good-windows-
reused-not-retranslated, order integrity, the ratio gate, honest-gap-on-failure,
empty-dir = all-missing, clean failure on missing source.
