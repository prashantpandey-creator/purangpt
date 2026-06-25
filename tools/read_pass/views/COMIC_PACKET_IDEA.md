# Comic Packet — idea bank (NOT a priority, do not let it shape the core graph)

> **Status: IDEA ONLY.** Captured so it's not lost. The core knowledge-graph
> system (`graph.py`) must be built for correctness and generality first — comic
> needs do NOT drive the graph schema. This is one *downstream view* that will
> sit on top of the finished graph, not a feature inside it. Build it later, or
> when a comic requirement forces a small graph change (and if it does, make the
> change generally, not comic-specifically).

## What it is

Project #2 of daddy's three: turn the Puranas into readable, public-facing comics.
A comic needs a *connected, timeline-aware, cited story packet* — not raw scripture.
The graph is the engine; the comic packet is what rolls off it.

## Why the graph is essential to it

A story is only a good comic if it carries its **setup** and **payoff**, which
usually live in *different chapters*. Example the graph already found:
- **Setup** (BhP 10.9): Narada curses Nalakubara & Manigriva to become trees.
- **Payoff** (BhP 10.10): infant Krishna uproots the trees, freeing them.

A flat per-chapter summary can't connect these. The *graph* can (same entities,
the cause→consequence chain across chapters). That cross-chapter linking is the
whole value.

## Target output shape (sketch — refine when actually building)

```json
{
  "title": "The Twin Trees of Gokula",
  "setup":   { "event": "Narada curses Nalakubara & Manigriva to become trees",
               "chapter": "10.9", "why": "arrogance and drunkenness" },
  "payoff":  { "event": "Infant Krishna uproots the trees, freeing them",
               "chapter": "10.10" },
  "cast":    [ {"name": "Krishna", "forms": ["Govinda", "Madhava", ...],
                "role": "liberator"},
               {"name": "Narada", "role": "curser"} ],
  "teaching": "even a curse from a sage is grace in disguise",
  "citations": ["bhp_10.09.xxx", "bhp_10.10.xxx"]
}
```

## How it would be built (later)

A JSON-contract script `views/comic_packet.py` that, given a seed event or entity,
walks the graph for: (1) the story arc(s) involving it, (2) the cause chain that
set it up, (3) the consequence it triggers, (4) the cast with canonical name-forms,
(5) the teaching + verse citations. Pure graph traversal, zero LLM (or one optional
LLM polish pass to phrase the panel captions — that's the only place a model helps).

## Sibling views (same engine, different slice)

- **Trivia view** — entity + predicate + verse_range, sliced as Q&A with citations.
- **Guruji reasoning view** — the graph injected as `{knowledge_context}` at query
  time (Phase 4, the live-product integration).

All three consume the SAME graph. None of them changes how the graph is built.
