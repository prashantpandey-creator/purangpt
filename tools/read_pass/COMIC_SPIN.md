# Puranas Comic — Idea Spin & Pick-Up

> **The impulse:** we read the Puranas through Sharma's Kriya-Yoga lens and the engine produced a mountain of distilled meaning — but we've made nothing *tangible or fun* out of it. Let's make a comic. Just for fun. Then go back to the real project.
> **Where to resume:** read "Why this is closer than it looks" → "Relationship to Katha" → dump into the SPIN ZONE.

---

## Why this is closer than it looks

The killer insight: **the engine already produced 523 ready-made comic beats.** We are not authoring from scratch — there's a populated, resolvable pipeline sitting on disk.

**File:** `/Users/badenath/projects/vedic puran/purangpt/tools/read_pass/out/bhagavata_teaching_synthesis_v2.json` (JSON envelope; clusters at `data.clusters[]`, `data.n_clusters: 523`, compressed from 1343 raw teachings, 2.6× ratio).

**Schema of one cluster — exactly 4 fields:**

| Field | Type | Meaning for the comic |
|---|---|---|
| `core_truth` | string | the one-sentence "beat" — the strip's premise/punchline |
| `supporting_teachings` | list[int] | indices into a flat 1517-entry teaching list; each → `{teaching, lens_note, verse_ranges}` |
| `lens_synthesis` | string | a paragraph reading the truth through Sharma's Kriya lens — the "deeper meaning" panel |
| `verse_citations` | list[str] | keys like `bhp_01.01.002` that round-trip to **real Sanskrit on disk** |

**Real example (`data.clusters[0]`):**
```json
{
  "core_truth": "The Srimad Bhagavatam is the ultimate spiritual literature, the sweetened essence of all Vedas, in which Dharma took shelter...",
  "supporting_teachings": [0, 1, 3, 11, 14, 15],
  "lens_synthesis": "The Srimad Bhagavatam is the ripened fruit of the Vedic desire-tree, made even sweeter by the touch of Shukadeva's lips...",
  "verse_citations": ["bhp_01.01.002","bhp_01.01.003","bhp_01.01.009", ...]
}
```

Every cluster gives a full 3-layer chain: **distilled beat → source teachings (each with its own lens gloss) → exact verses → real Sanskrit text** (verified: `bhp_01.01.002` → `"dharmaḥ projjhitakaitavo 'tra paramo..."`, resolvable from `data/chunks/bhagavata.jsonl`). So a panel can cite a verse AND surface its authentic Sanskrit with zero new authoring. (Text is GRETIL transliteration, not English — for English verse text, render from `core_truth`/`teaching`/`lens_note` and keep the Sanskrit as the citation.)

**Three clusters that'd make great first strips** (dramatic, visual, self-contained, with a built-in Kriya "twist" panel):
1. **Cluster 63 — Kurukshetra as the inner war.** The battlefield *is* you; blind king Dhritarashtra = the attached mind. Instant visual metaphor; `lens_synthesis` already supplies the decode.
2. **Cluster 104 — The futile sacrifice.** Before/after gag: priest at the altar (wrong) vs. yogi offering the breath into inner fire / Kundalini (right). Punchy.
3. **Cluster 341 — The Lord as protector / demon-slayer.** 10 verse citations, hero shielding the devotee, demons routed. The crowd-pleaser splash opener.
   *(Bench: cluster 83 Dhruva, 289 transcending death by penance, 20 the thumb-sized soul of light.)*

There's also a second file — `bhagavata_insights_v2.json` (`data.insights[]`): typed cross-arc findings (`theological_synthesis`, `pattern`, `karmic_chain`, `cross_text`) with `evidence[]` and `cross_references[]` — better for **multi-panel arc strips** than single gags.

---

## Relationship to Katha (this EXTENDS, doesn't duplicate)

Per the Smriti architecture rule, a comic is **best understood as a *visual mode of Katha*** — which is itself a spoiler-gated narration **mode of Marga, not a standalone app.** The comic owns no intelligence; it drinks from the same comprehension trunk (Sutradhar) and adds *only* a presentation layer. That's the only framing that doesn't fork the brain.

**So the comic should reuse, not reinvent:**
- **The `first_seen` spoiler gate, verbatim.** Same cursor-clamp Katha uses (`first_seen ≤ cursor`) — don't redesign panel-reveal logic.
- **The read-model graph:** `arcs[]` for panel sequencing, `entities[]` (with `aliases`, `appearances[]`) for character art refs, `relationships[].evidence` verse_ranges for provenance, `teachings[]` for captions.
- **The locked rule:** *no view edits the graph.* Comic is a read-only sibling view, same as chat / storyteller / trivia.
- **The storage path:** JSON artifact for J1 → migrate to `purangpt-pgvector` at J3 (sink swap, not a rewrite).
- **Transport:** if it ever goes live, it rides the existing `/api/chat` SSE path as a new `QueryMode` (added to BOTH `api.ts` and `main.py`'s `PROMPTS` in sync) — not a new transport.

**Design doc to align to:** `/Users/badenath/projects/vedic puran/purangpt/tools/read_pass/JARVIS_DESIGN.md`. The comic stub it references is `/Users/badenath/projects/vedic puran/purangpt/tools/read_pass/views/COMIC_PACKET_IDEA.md` — align to *that* (the "one trunk + sibling views" framing), NOT the obsolete §3/§4 framing.

**The one real engine gap (shared with Katha):** `graph.py` tracks `chapters` as an *unordered set* but NOT ordered first-appearance. The spoiler gate needs **`first_seen: {segment, order}`** on every entity/relationship node. **It is UNBUILT** — a small surgical add to Pass 1/Pass 2, ~30 lines, no schema/downstream change. Add it **generally, not view-specifically.** Without it, neither Katha nor the comic can know whether a character has been introduced yet relative to the cursor.

**Status reality check:** the *substrate* is BUILT & tested — comprehension engine + read model, 22 corpora comprehended, shipped in PR #5, plus the 523 Bhagavata clusters above. **Katha itself is UNBUILT (design only).** The comic is even earlier — idea only. So we're standing on a real, populated pipeline, blocked only by `first_seen` + the J2 state machine if we want spoiler-safety.

---

## Possible shapes (all UNPICKED)

1. **One hand-made strip, just for fun.** Pick cluster 63 or 104, draw/write 3-4 panels by hand. *Pro:* fastest, zero infra, pure fun, ships today. *Con:* not reusable, doesn't touch the pipeline.
2. **AI-illustrated pipeline (cluster → panels).** `core_truth` = premise panel, `lens_synthesis` = decode panel, `verse_citations` = provenance footer; feed to an image model. *Pro:* scales to all 523, reuses everything, becomes a real "comic mode." *Con:* needs art-style consistency + the `first_seen` gate if order matters; real build, not a one-afternoon thing.
3. **Printable zine** — a curated handful (the 3 first-strip clusters + a few from the bench) laid out as a small booklet. *Pro:* tangible artifact, shareable, natural Prachar/marketing crossover. *Con:* layout work; one-off unless templated.

---

## What we'd need

- **Art-style decision.** Hand-drawn vs AI-illustrated; line-art vs painterly; the visual register (it should feel of-a-piece with the violet/indigo Bindu register, or deliberately not). TODO(daddy).
- **Panel/script format.** A fixed cluster→panels mapping (e.g. premise / scene / Kriya-twist / verse-footer) so any of the 523 clusters drops in uniformly. TODO(daddy).
- **Image model — optional.** **ComfyUI is already on this machine** (`/Users/badenath/ComfyUI/`, Python-based, custom-node workflows) — a ready local option for the AI-illustrated path. Whether to use it (vs hand-art vs a hosted model) is TODO(daddy).

---

## Scope guard

This is the **fun side-quest** — time-box it, make one tangible thing, then back to the real roadmap (Phase 4 brain wiring, Marga, Katha). Do **not** let it grow its own narrative-ordering logic or become a standalone app — that forks the brain, which the architecture rule forbids. Visual layer only, on top of the existing spine.

---

## SPIN ZONE (pick up here)

### ✅ FIRST STRIP DRAWN — "The War Was Always Inside" (2026-06-23)

Took Shape #1 (one tangible thing, time-boxed). Picked the inner-war beat. Rendered
as a real 4-panel SVG → `views/strip_01_kurukshetra.svg`. Open it in a browser.

**Reality check that shaped it (verified against the data, not the doc):**
- **Cluster 63's `verse_citations` are placeholders (`[1]`,`[2]`), NOT real `bhp_` keys** —
  zero round-trippable verses. The doc oversold it. The *metaphor* is still the best opener,
  so I kept cluster 63 as the spine but anchored provenance elsewhere.
- **Anchor teaching = cluster 193** ("Atman is eternal, unaffected by the body; the wise do
  not grieve") — 36 real verses, keys `bhp_06.16.004`–`bhp_06.16.009`. This is *exactly* the
  battlefield consolation, so it fuses perfectly with the Kurukshetra frame.
- **`bhp_` keys live INSIDE the chunk `text` body** (e.g. `…dhīmahi । bhp_01.01.001*`), not
  as the JSONL `id` (which is `bhagavata-1-1`). That's the real round-trip path — note it for
  any future pipeline. Resolved `bhp_01.01.001` Sanskrit from disk for the footer flourish.

**Panel mapping used (the reusable template, proven on one strip):**
| Panel | Source field | Content |
|---|---|---|
| 1 — Premise | `core_truth` (c63) | The two armies face off; caption names the real stakes |
| 2 — Scene | `core_truth` decode | Pull back: the battlefield IS the body; Dhritarashtra = blind mind |
| 3 — Kriya twist | `lens_synthesis` (c63+c193) | Pandavas = upward life-force, Kauravas = downward desire; the witness watches |
| 4 — Verse footer | cluster 193 + real Sanskrit | "The wise do not grieve" + `bhp_06.16.004–009` cite + `bhp_01.01.001` Sanskrit |

**Next pick-ups (still unbuilt, deliberately):**
- Strip 2: cluster 104 (futile sacrifice — before/after gag) has 2 real verses — usable.
- Strip 3 splash: cluster 341 (demon-slayer) has **10** real verses — strongest provenance,
  best crowd-pleaser opener if this ever becomes a zine.
- If it scales past ~3 strips, THEN build the cluster→panels tool (Shape #2) with the mapping
  table above as its fixed contract. Not before — scope guard holds.

---

### 📕 PDF DESIGN NOTE — comic/story booklet generator (NEXT SESSION starts here)

> **One job:** a read-only renderer that turns chapter `story` objects into printable
> pages. Owns no intelligence. Drinks from `.records.jsonl`. Same "one trunk, sibling
> view" rule as chat/storyteller — it never edits the graph.

**Read FROM `out/<corpus>_v{1,2}.records.jsonl`, NOT the synthesis clusters.**
(Verified: the squeezed `synthesis_v2` index degrades real `bhp_xx.yy.zzz` keys into
`[1]`/`[2]` placeholders. The records keep real keys. Don't repeat the cluster-63 mistake.)

**The database, verified (2026-06-23):**
- **10,492 story chapters across 23 corpora** (22 usable; `bhagavata_proof` = 8-line test scrap, skip it).
- **10,255 have a `comic_potential` field the engine wrote itself** — use it to rank pages.
- 154K entities · 74K relationships · 39K teachings, every node carries `verse_ranges`.

**Schema → page mapping (the fixed contract — build the tool against THIS):**

| Source field (per chapter record) | PDF page element |
|---|---|
| `story.title` | page heading |
| `story.arc` | the narrative prose block |
| `story.characters[]` | "dramatis personae" line / art refs |
| `story.timeline_note` | era caption (e.g. "Set in Kali Yuga…") |
| `story.comic_potential` | ranking signal + optional "why this scene" margin note |
| `teachings[].teaching` + `teachings[].lens_note` | the **Sharma decode** sidebar/callout |
| `entities[].name` + `aliases` | character glossary |
| `relationships[]` (`src → rel → dst`) | optional relationship map |
| `_provenance.chunk_ids[]` | → resolve to real Sanskrit footer (see below) |

**Sanskrit round-trip (VERIFIED working):** `_provenance.chunk_ids` are the `id` field in
`data/chunks/<corpus>.jsonl`. Build `{id: text}` once, look up. Confirmed:
`bhagavata-1-2` → `"dharmaḥ projjhitakaitavo 'tra paramo nirmatsarāṇāṃ satāṃ…"`.
- Corpus name maps directly to chunk file (`vamana` → `data/chunks/vamana.jsonl`), with two
  renames to handle: `linga` → `linga_1.jsonl`, `hatha_yoga` → `hatha_yoga_pradipika.jsonl`.
- The `bhp_` style markers ALSO live inline in the chunk `text` body (`…dhīmahi । bhp_01.01.001*`)
  — use `chunk_ids` for resolution, those inline markers only for display citations.

**Build shape (Rule 0 — tests-first, JSON envelope):**
1. `cp -r tools/_template tools/story_pdf` → a tool that takes `{corpus, chapter_range|top_n_by_comic_potential}`
   and emits a JSON manifest of resolved pages (`{title, arc, decode, sanskrit, cite}`).
2. Test against a captured `.records.jsonl` fixture (real-input-in → page-manifest-out). Assert
   the round-trip resolves real Sanskrit, not a placeholder.
3. Render step (HTML→PDF via existing pdf skill, or ComfyUI for illustrated panels) consumes the
   manifest. Renderer is dumb; all selection/resolution logic is in the tested tool.

**First booklet candidates (dramatic, self-contained, decode lands):** Dhruva (boy → Pole Star),
Narasimha (the no-loophole death), Vritra (demon who wanted to be a servant). Full treatments
written above this session — reuse them as the prose for pages 1-3.

**Scope guard still holds:** visual/print layer only. No narrative-ordering intelligence in the
PDF tool. If page sequencing needs spoiler-safety, that's the shared `first_seen` gate (still
UNBUILT) — don't reinvent it inside the renderer.

---

_Below: still empty on purpose. Dump raw ideas — panel sketches, captions, art refs, ComfyUI workflow notes, anything._
