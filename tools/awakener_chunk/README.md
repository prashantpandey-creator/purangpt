# awakener_chunk

Chunk **The Awakener** (Katya Mossin's authorized biography of Shailendra Sharma)
into the SAME chunk shape as the Puranic corpus, with inline `awk_CH.PARA` markers
so `verify.py` can ground the citations the decoder emits.

**Why it exists:** Guruji's story is the *continuation* of the Puranas, not a
separate biography (the book's own thesis: "the story of Kriya does not end
there"). So it must become corpus — same chunks, same schema, same graph — so
Babaji / Lahiri Mahasaya / Sharma become first-class entities alongside Krishna /
Vyasa, linked by the same lineage edges. See memory
`guruji-story-continues-puranas`.

**Marker scheme:** prose has no canonical verse numbers, so markers are keyed to
`awk_<chapter-index>.<paragraph-seq-within-chapter>`. The marker maps to a REAL
paragraph in the source (verify.py can confirm it exists) without fabricating
verse numbers. The format matches verify.py's `_MARKER_RE`
(`[A-Za-z]{1,6}_\d+(?:[.\-]\d+)*`).

## Failure modes

| Condition | `success` | `errors[].code` | Meaning / fix |
|-----------|-----------|-----------------|---------------|
| Source `.md` missing | `false` | `missing_source` | The translation isn't where expected — run `translation_finish` first, or pass `--src`. |
| Source has no narrative paragraphs | `false` | `no_chunks` | The file is empty/all-TOC/all-blockquote — check the source. |
| Source OK | `true` | — | `data` = `{n_chunks, n_chapters, total_markers, out_path}`. |

**Known wart (not a failure):** the source markdown's `##` headings are
incomplete — the front and back thirds of the book are flat prose, so most chunks
land in `chapter 0` ("Front Matter") and the final heading's chapter. `group.py`'s
`MAX_WINDOW_CHUNKS=80` sub-windows these into digestible pieces, so the decode
still works; only the precise chapter LABEL is lost for those sections. If exact
chapter attribution becomes important, drive boundaries off the TOC titles.

## Run

```bash
# Chunk into data/chunks/awakener_chunks.jsonl (default target 1500 chars/chunk)
venv/bin/python -m tools.awakener_chunk.check --json

# Preview without writing
venv/bin/python -m tools.awakener_chunk.check --dry-run --json

# Then decode through the standard pipeline (same as any Purana):
DEEPSEEK_API_KEY=... venv/bin/python -m tools.read_pass.run \
  --input data/chunks/awakener_chunks.jsonl --tag awakener --provider deepseek --json
```

Tests: `venv/bin/python -m tools.awakener_chunk.test_check` (must exit 0).
