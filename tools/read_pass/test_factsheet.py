"""Tests-first for factsheet — the deterministic graph-fact assembler that
grounds decode() in literal reality (Rule 0 precond A).

The Gandiva problem: decode("Gandiva") floats into pure mysticism because it
never consults the graph that ALREADY knows Gandiva is Arjuna's bow demanded by
Agni. factsheet(symbol, memory) is the zero-LLM decision tree that resolves the
symbol to its entity and assembles the LITERAL layer — identity (name + forms +
kind), its grounded verse cites, and its named relationships — for decode() to
read BEFORE it generates.

Honesty discipline (the whole point): the graph's verse_ranges are POLLUTED with
bare-number garbage ('17', '5-6', '61.4') that lost its marker prefix during
chunking. factsheet MUST pass every cite through verify.extract grammar and keep
ONLY canonical markers — never cite 'verse 17' of nothing. A fact with zero
grounded cites is reported but flagged ungrounded; decode must not state it as
hard fact.

Run: venv/bin/python -m tools.read_pass.test_factsheet   (exit 0)
"""
from __future__ import annotations
import json
import os

from tools.read_pass import factsheet
from tools.read_pass import recall as R

HERE = os.path.dirname(__file__)
GRAPH = os.path.join(HERE, "out", "graph_manifest.json")
RAM = os.path.join(HERE, "out", "guruji_ram.json")


def _memory():
    """The real brain. factsheet runs against the same Memory recall uses."""
    return R.Memory.load(GRAPH, RAM)


# ── envelope shape (precond B) ────────────────────────────────────────────
def test_envelope_shape():
    env = factsheet.factsheet("Gandiva", _memory())
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert isinstance(env["errors"], list)


def test_empty_symbol_is_clean_failure_not_raise():
    env = factsheet.factsheet("", _memory())
    assert env["success"] is False
    assert env["data"] in (None, {}, {"found": False})
    assert env["errors"] and env["errors"][0].get("code")


# ── resolution (the cross-text identity win) ──────────────────────────────
def test_resolves_via_shared_normalizer_and_aliases():
    """'Gandiva', 'Gāṇḍīva' (diacritics), 'gāṇḍīvam' and case/whitespace noise all
    resolve to the one node — the cross-text-identity capability RAG can't match."""
    for cue in ["Gandiva", "Gāṇḍīva", "gāṇḍīvam", "  GANDIVA  "]:
        env = factsheet.factsheet(cue, _memory())
        assert env["success"] is True, f"failed to resolve {cue!r}"
        assert env["data"]["found"] is True
        assert factsheet._norm(env["data"]["identity"]["canonical"]) == "gandiva"


def test_unknown_symbol_returns_found_false_not_crash():
    env = factsheet.factsheet("Zxqwybflorp", _memory())
    # clean "I don't know this" — success True (the query ran), found False
    assert env["success"] is True
    assert env["data"]["found"] is False
    assert env["data"].get("relationships", []) == []


# ── the literal layer (the Gandiva fix itself) ────────────────────────────
def test_identity_carries_forms_and_kind():
    d = factsheet.factsheet("Gandiva", _memory())["data"]
    idy = d["identity"]
    assert idy["kind"]  # concept
    forms = " ".join(idy.get("forms", [])).lower()
    assert "gāṇḍīv" in forms, \
        "Gandiva identity must carry its literal Sanskrit forms (Gāṇḍīva / gāṇḍīvam)"


def test_named_relationships_are_resolved_not_ids():
    """Edges must render with src_name/dst_name (Arjuna, Agni) — never raw ids.
    This is the literal event-knowledge decode was missing."""
    d = factsheet.factsheet("Gandiva", _memory())["data"]
    rels = d["relationships"]
    assert rels, "Gandiva must have named relationships in the graph"
    for r in rels:
        assert r.get("src_name") and r.get("dst_name"), f"unresolved edge: {r}"
        assert "->" not in r["src_name"] and r["src_name"] != r.get("src")
    names = {r["src_name"] for r in rels} | {r["dst_name"] for r in rels}
    joined = " ".join(names).lower()
    assert "arjuna" in joined, "Arjuna must appear among Gandiva's relations"


# ── HONESTY: the cite-pollution gate (the discipline that earns trust) ─────
def test_cites_are_canonical_markers_only_no_bare_number_garbage():
    """The graph's verse_ranges hold '17','5-6','61.4' garbage beside real
    'bhp_10.89.032' markers. factsheet MUST drop the garbage — a literal layer
    that cites 'verse 17' of nothing is a liar, not a mind."""
    from tools.read_pass import verify
    d = factsheet.factsheet("Gandiva", _memory())["data"]
    for c in d["identity"].get("cites", []):
        assert verify._MARKER_RE.fullmatch(c) or verify._MARKER_RE.match(c), \
            f"non-canonical cite leaked into factsheet: {c!r}"
    # and at least one REAL canonical marker survives the filter — Gandiva is a
    # Mahabharata weapon, so its markers are mbh_*, never bhp_ (Bhagavata).
    cites = d["identity"].get("cites", [])
    assert cites and any(verify._MARKER_RE.match(c) for c in cites), \
        "all real Gandiva markers were wrongly filtered out"


def test_ungrounded_facts_are_flagged_not_silently_asserted():
    """metadata must tell decode how solid the literal layer is, so a thin-cite
    symbol doesn't get stated with false confidence."""
    md = factsheet.factsheet("Gandiva", _memory())["metadata"]
    assert "grounded_cites" in md and "raw_cites" in md
    assert md["grounded_cites"] <= md["raw_cites"]  # filtering only removes


# ── the prose decode() actually reads ─────────────────────────────────────
def test_literal_brief_is_nonempty_human_prose_with_a_cite():
    """decode() injects data['brief'] into its prompt. It must be a short factual
    sentence naming what the symbol literally IS, anchored to a real marker."""
    d = factsheet.factsheet("Gandiva", _memory())["data"]
    from tools.read_pass import verify
    brief = d["brief"]
    assert isinstance(brief, str) and len(brief) > 20
    assert verify._MARKER_RE.search(brief), \
        "brief must anchor its claim to a real verse marker"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
