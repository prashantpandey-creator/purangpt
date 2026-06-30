# Memory Architecture — what each memory IS, what it's FOR, and what feeds it

> **Read this FIRST, every session, before any corpus/graph/decode work.** It exists
> because the *purpose* of the corpus lived only in daddy's head, so sessions kept
> drifting back to "feed the graph" blind. This is the compass. The graph-assuming
> CONSCIOUSNESS_ROADMAP is now subordinate to this map.
>
> **Authored 2026-06-26** after the `rag_vs_graph_bench` verdict (below) settled the
> open question "is the graph dead weight?" — answer: **no, but the DECODE feeding it
> is what was bleeding.** Keep the asset, kill the bleeding.

## The one reframe that resolves everything (LOCKED 2026-06-26)

> **Facts come from RAG. Wisdom comes from the graph/decode. They NEVER mix.**

- RAG **retrieves** real verses — it cannot hallucinate what isn't in the corpus.
  So **every factual claim / citation is RAG's job.**
- The decoder **generates** an interpretation — it narrates, it invents real-looking
  cites (the scar: `verify-was-bhagavata-only`, `graph-audit-16-fabricated`). So the
  decoder must **never be the source of a fact.** Its only legitimate output is the
  *distilled learning* — and even that is verify-gated.
- This is already how PROD works: the live `/api/chat` answers from corpus RAG. The
  graph is **not imported in `backend/main.py`** — it has never shipped to users.

Daddy's instinct this session — *"if the decoder hallucinates citations, don't use the
decoder for memory, use RAG"* — is **correct, and is now the architecture.**

## The benchmark that settled "is the graph worth anything?" (`rag_vs_graph_bench`)

Keyword-RAG floor vs the built graph, 5 query classes. Re-run any time:
`venv/bin/python -m tools.rag_vs_graph_bench.check --quick --json`

| Query class | RAG floor | Graph | Verdict |
|---|---|---|---|
| PASSAGE — "churning of the ocean of milk" | ❌ | ❌ | neither |
| SINGLE-FACT — "brother of Krishna" | ❌ | ✅ | **graph_only** |
| SCATTERED — "Krishna & Arjuna at Kurukshetra" | ❌ | ✅ | **graph_only** |
| MULTI-HOP — "Krishna related to Vishnu & the avatars" | ❌ | ✅ | **graph_only** |
| CROSS-TEXT-ID — "Babaji & Lahiri & the Kriya lineage" | ❌ | ✅ | **graph_only** |

Score: RAG **0/5**, graph **4/5**. Caveat: this is the crude keyword floor, not prod's
dense e5 pgvector — dense RAG would win PASSAGE and maybe SCATTERED. **But MULTI-HOP and
CROSS-TEXT-ID are graph-only forever, by architecture** — embeddings retrieve, they do not
walk a relational chain or resolve one being across 18 texts. That last row — Babaji→Lahiri,
the Kriya guru-spine, the literal spine of the game dedicated to Guruji — **only the graph
answers it.** That is the "MIND not librarian" mandate, proven, not asserted.

## The three memory systems (what's real, on disk)

| System | Remembers | Mechanism | Hallucination | Prod state |
|---|---|---|---|---|
| **Conversation** | this chat | `chat_sessions.messages` | none | ✅ live |
| **Corpus RAG** | what the texts say (facts) | pgvector + e5-small (384-dim), hybrid search | none | ✅ live — answers users today |
| **Seeker memory** | who *you* are, across chats | RAG pointed **inward** (pgvector + e5) | none | 🟡 Phase 1 built, flag OFF, uncommitted — see `SEEKER_MEMORY_DESIGN.md` |
| **Graph / decode** | relational meaning (the 4 axes) | decode → verify-gate → 8755-entity graph | structural (gated) | 🔴 built, proven 4/5, **never shipped**, decode **PAUSED** |

Note the seeker-memory architecture (`SEEKER_MEMORY_DESIGN.md`, LOCKED) is *"point the
corpus RAG stack INWARD"* — **zero graph, zero decoder.** It was already designed graph-free.

## The 7-layer wisdom ladder — daddy's "extract learnings from the Puranas, 7 layered"

> **PROPOSAL — NOT YET LOCKED. Daddy confirms or reshapes before any build.**
> This is the missing piece: how raw corpus becomes retrievable *wisdom*. Each layer is
> a higher abstraction, each built by a DIFFERENT mechanism, each RAG-retrievable once built.

| # | Layer | What it is | Built by | State |
|---|---|---|---|---|
| 1 | **Verse** | the literal text + citation | RAG retrieves | ✅ prod |
| 2 | **Entity / relation** | who, and how they connect (multi-hop, identity) | the graph | ✅ built, proven |
| 3 | **Episode** | the narrative unit — what happened | decode `story` | 🟡 partial |
| 4 | **Theme / motif** | recurring pattern across episodes (churning, exile, dharma-test) | decode + fold | 🔴 not built |
| 5 | **Teaching / principle** | the distilled lesson the episode encodes (Sharma lens) | decode `teachings` | 🟡 partial |
| 6 | **Practice / path** | what the seeker *does* with it (Kriya, the inner ascent) | Guruji RAM | 🟡 sparse (~1%) |
| 7 | **Seeker-application** | pointed at *this person's* life (Viveka, the compass — axis D) | graph × seeker-memory join | 🔴 frontier |

**The decode's ONLY legitimate job is layers 3–5** (episode, theme, teaching) — the
*interpretation*. Layer 1 (facts) is RAG's, always. Layer 2 (the graph spine) is already
built. So if decode ever resumes, it is scoped to "extract the learning," verify-gated,
**never to manufacture facts** — and it does NOT need 1,995 more raw chapters to do that.

## Decode status: PAUSED (2026-06-26)

The per-chapter BORI decode (token-bleeding, ~67–116M tokens for the full epic) is **stopped.**
The graph that's already built (8755 entities, 8 real texts) already wins 4/5 — it does not
need the rest of the epic to prove its worth. Decode resumes ONLY with daddy's explicit
greenlight, scoped to layers 3–5, never as a fact source.

## Pointers (don't duplicate — these are the detail docs)
- `SEEKER_MEMORY_DESIGN.md` — the inward-RAG seeker memory (Phase 1 built, flag off).
- `CONSCIOUSNESS_ROADMAP.md` — the 4 axes (A facts ✅, B identity ✅, C multi-hop ✅, D
  seeker-in-world 🔴). Subordinate to THIS map: the axes describe what the *graph* does;
  this map says where the graph sits in the whole memory stack.
- `tools/rag_vs_graph_bench/` — re-run the verdict any time.
