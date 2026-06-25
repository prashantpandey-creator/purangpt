# The Consciousness Roadmap

> **Reconstructed from disk truth, 2026-06-26.** This file is named in the long-
> running `/loop` but had never actually existed on disk (confirmed: absent from
> the working tree AND from all git history). It was an *aspiration*, not a lost
> file. This is its first real authoring — written by auditing what the Sutradhar
> engine (`tools/read_pass/`) actually contains, against the locked bar in memory
> `consciousness-over-rag` and the master map `smriti-vision-and-names`.
>
> **Re-derive, don't trust this blind.** A roadmap is a point-in-time photograph.
> Before acting on any "DONE" below, confirm the cited commit / `file:line` still
> holds. The audit commands that produced this file are listed at the bottom —
> re-run them to refresh state.

## The bar this roadmap is judged against

Daddy's locked decision (memory `consciousness-over-rag`, 2026-06-23): **build the
MIND, not the librarian.** For a single-entity lookup, plain RAG does ~80% of the
job cheaper. The graph (10,496+ comprehension passes) only earns its cost on the
**four things RAG structurally cannot do** — these are the axes of "consciousness",
and every step below maps to one:

| # | Axis | What it means | Status |
|---|------|---------------|--------|
| A | **Verifiable literal facts** | `Agni --[demands]--> Gandiva`, verse-cited, `verify.py`-checkable — not a vector blob | ✅ **grounded** |
| B | **Cross-text identity** | Partha/Dhananjaya/Vijaya all = ONE Arjuna node; not split across alias strings | ✅ **grounded** (with a hard-won merge guard) |
| C | **Multi-hop / pattern** | "which weapons were god-given, by whom?" — an edge-traversal query, not a passage that exists to retrieve | ✅ **traverse() shipped** |
| D | **Seeker-in-the-world** | model the *seeker's* standing relative to the characters — a world you can be *placed inside* | 🔴 **frontier — unbuilt** |

**The winning design is graph-grounded RAG** (graph for who/what/how-connected +
verifiable identity; RAG/source-windows for the actual words) — never either alone.
Judge every decode/recall change against this table. A change that only improves
single-entity lookup is under-built for what daddy asked.

---

## STEP 1 — Literal grounding (axis A): decode() consults the graph before it generates ✅ DONE

**The Gandiva problem it solved:** `decode("Gandiva")` used to float into pure
mysticism ("time-realization…") because it never consulted the graph that ALREADY
knows the literal truth — Gandiva is Arjuna's bow, demanded by Agni, cited at
`bhp_10.89`. The inner reading replaced the fact instead of sitting on top of it.

**Shipped** (the "Gandiva fix", memory `gandiva-fix-decode-grounding`):
- `tools/read_pass/factsheet.py` — the zero-LLM literal-layer assembler. Resolves a
  symbol → one entity (shared `_norm` + alias match), gathers its grounded cites and
  named edges, builds a short factual `brief`. JSON envelope.
- **The honesty discipline that makes it a mind not a bullshitter:** every cite is
  run through `verify._MARKER_RE`; bare-number chunking garbage (`'17'`, `'61.4'`)
  is dropped — a literal layer that cited "verse 17 of nothing" would be a confident
  liar. `metadata` reports `raw_cites` vs `grounded_cites` so decode knows how solid
  the floor is. (`factsheet.py:34-54`.)
- **Wired & live:** `decode.py:275` calls `_literal_facts()` → `factsheet.factsheet()`
  BEFORE generating; the literal block is injected as grounding the model must HONOR
  not invent (`decode.py:160-193`), and surfaced back additively as
  `data["literal"]` (`decode.py:305`).
- **Verified:** 36 tests green across `test_decode.py` + `test_factsheet.py`.

*This was "STEP 1" in the original /loop prompt. It is genuinely complete — the loop
should NOT re-do it.*

## STEP 2 — Cross-text identity (axis B): one entity per being, across every text ✅ DONE (load-bearing, scar tissue)

Identity merging is built and **hardened by two real incidents** — this axis cost
more than any other and the guards must not be regressed:
- `identity.py` + `graph.py` merge name-variants into one node with `all_forms`.
- **Merge-bug #1** (memory `identity-merge-rel-is-blob`): `rel: is` edges ("Shiva is
  Vishnu" — theological non-dualism) were treated as entity equality → blobbed the
  whole pantheon into one 2458-alias Vishnu. Fixed: `rel: is` routes to `aspect_of`
  edges, **never** merges.
- **Merge-bug #2** (memory `peer-name-confusion-merge`): the decoder listed DISTINCT
  beings as aliases via a shared name-fragment (Rama ← Balarama/Parashurama). Fixed
  with a peer-name guard in `graph.py` (sever the union AND drop the bare name from
  `all_forms`). ~3411 false-merges → 10 legit synonyms. Manifest now **8755 entities**.
- ⚠️ Do **not** "fix" this with an app-side avatar filter — that would nuke real
  Matsya↔Vishnu avatar links. The fix lives in the merge logic, correctly.

## STEP 3 — Multi-hop reasoning (axis C): let the mind reach further than one step ✅ DONE

**The problem it solved:** `recall.py` reaches exactly **one hop** —
`_expand_one_hop` (`recall.py:140`) keeps each seed's top-K strongest neighbours,
the *associative cluster* around a cue. It can surface the weapons OR the deities
near a seed, but never the *path* that ties giver→gift→wielder. The canonical
consciousness query — *"which weapons were god-given, by whom?"* — is a two-hop
pattern `(deity) --[gives]--> (weapon) --[wielded_by]--> (hero)` that one-hop
recall structurally cannot assemble.

**Shipped:** `tools/read_pass/traverse.py` (flat module, matching `factsheet.py`) +
`test_traverse.py` (**15 assertions, green**) + `traverse_README.md`.
`traverse(symbol, memory, max_hops, max_paths, rel_filter, grounded_only)` walks the
real graph (8755 entities / 24474 edges) and returns whole paths. Live proof:
`Krishna --[avatar]--> Vishnu --[wields]--> Sudarshana Chakra` — a chain recall
cannot make. Rule-0: zero-LLM, JSON envelope, tested against the real `out/` manifest.

**The discipline that makes a path a fact (tests pin all of it):**
- **No cycles** — a path never revisits a node (the graph is full of loop-backs:
  `Krishna --killed--> Putana --attempted_to_kill--> Krishna`).
- **Identity edges are not hops** — `alias`/`is`/`identical_to`/`same_as`/`aka` are
  axis B's job (cross-text identity); a "path" made of aliases is one node in
  disguise. Skipped as traversal hops.
- **Depth-first, terminal-only** — a hub's 649 immediate neighbours would flood a
  bounded result set before any 2-hop chain completes under breadth-first order, so
  traverse goes deep first and records only terminal paths. `max_hops=2` yields
  reasoning, not a neighbour list.
- **Verify-gated cites + a grounding signal** — this surfaced a **major honest
  finding**: only **~46%** of real multi-hop paths are fully verse-grounded (43%
  have an uncited hop, 10% none). So each path carries a `grounded` flag (True iff
  every hop is cited), `metadata` reports `n_grounded`/`n_paths`, and
  `grounded_only=True` returns solely the verse-defensible gold. A chain you can't
  cite is never handed back as if it were.

**Not yet wired into decode().** traverse stands alone and tested; the additive
hook into `decode()`/`recall()` (the way `factsheet` is wired at `decode.py:275`) is
deliberately a separate, smaller step — do it when a doorway needs multi-hop, so the
wiring is driven by a real consumer rather than speculative.

## STEP 4 — Seeker-in-the-world (axis D): the layer daddy most wants 🔴 FRONTIER — design-only

Memory `consciousness-over-rag`: *"model the SEEKER's standing relative to
characters; RAG returns verses, it doesn't hold a world you can be placed inside.
This layer does NOT exist yet — it's the frontier."* On disk this is confirmed: a
**design doc only** (`SEEKER_MEMORY_DESIGN.md`), no module. Two faces of it:
- **Viveka, the life-compass** (memory `sat-asat-life-compass`, the flagship): point
  `decode()` OUTWARD at the seeker's own actions — *"compass, not gavel."* Same
  operator, pointed at a life instead of a Puranic symbol. ⚠️ NOT a Sat/Asat valence
  score — that keyword classifier was deliberately REMOVED (`valence-axis-removed`);
  Viveka runs on decode's rich inner meanings.
- **The narrative seeker** (memories `puranas-continuation-frame`,
  `game-dedicated-to-guruji`): the seeker walks ONE unbroken timeline
  (Mahapuranas → Kriya line → Sharma), placed *inside* the entity universe.

This is the largest unbuilt thing and the highest-value. It is gated on STEP 3 being
solid (you cannot place a seeker in a world the mind can only walk one step into) and
on the corpus being more complete (see the cross-cutting work below).

---

## Cross-cutting: the mind is built from a HALF-READ corpus

Independent of the four axes, the comprehension itself is **~half done**. The only
honest count (never hand-count — memory `decode-audit-the-only-true-count`):

```
tools.decode_audit  →  total_pending: 2946 chapters across 32 texts (2026-06-26)
```

Every axis above gets *stronger automatically* as more of the corpus is decoded into
the graph (memory `inhouse-decode-engine` — comprehend on Claude itself via Workflow
fan-out when Gemini quota is hit). Decoding more is not a "step" with an end; it is the
background that makes A–D richer. **Gate:** every new record MUST pass `verify.py`
(memory `verify-was-bhagavata-only` — the decoder hallucinates narration but cites
real markers; verify is the only thing that catches it). Decoding without the verify
gate poisons the mind faster than it grows it.

## The honest order of work

1. ✅ **STEP 1 — literal grounding** (axis A). DONE — commit history + 36 tests.
2. ✅ **STEP 2 — cross-text identity** (axis B). DONE — hardened by two merge incidents.
3. ✅ **STEP 3 — multi-hop `traverse()`** (axis C). DONE — `traverse.py` + 15 tests,
   green. Surfaced that only ~46% of paths are verse-grounded (a grounding signal
   now reports it). Optional follow-up: wire it into `decode()` when a consumer needs it.
4. 🔴 **STEP 4 — seeker-in-the-world / Viveka** (axis D). **← now the top-unchecked.**
   Frontier; gated on corpus depth + the grounding reality (the seeker's world is
   only as defensible as the chains under it — prefer `grounded_only` paths). Highest
   value, largest build.
5. ♾️ **Cross-cutting — keep decoding** (2946 pending), every record verify-gated.
   *Now doubly motivated:* 54% of multi-hop paths lack a full citation largely
   because the source edges came from un- or thinly-decoded chapters — more decoding
   directly raises the grounded-path fraction.

## Audit commands (re-run to refresh this file's claims)

```bash
# from purangpt/ — the true backlog (filenames/labels lie; this is the only count)
venv/bin/python -m tools.decode_audit.check --json

# prove STEP 1 is still wired (decode → factsheet, the Gandiva fix)
grep -n "factsheet\|_literal_facts" tools/read_pass/decode.py

# the engine's actual reach today (one-hop expansion)
grep -n "_expand_one_hop\|def recall\|traverse\|multi_hop" tools/read_pass/recall.py

# is the seeker layer still design-only? (expect: only SEEKER_MEMORY_DESIGN.md)
ls tools/read_pass/ | grep -iE "seeker|world|compass|viveka"
```
