"""Tests-first for recall — Guruji's associative memory retrieval (Rule 0 precond A).

The mind model (daddy's design): a seeker's question is a CUE. recall() pulls ONLY
the relevant fragment of long-term memory into working memory — the matching
entities, their one-hop associative cluster (neighbors via edges), the decode keys
that apply, and the Sat/Asat valence. NOT a dump of all 14k nodes; selective recall,
the way a human surfaces just the relevant cluster from a cue.

Deterministic graph walk + string match — no LLM, no network. So it gets tests.
Run: venv/bin/python -m tools.read_pass.test_recall   (exit 0)
"""
from __future__ import annotations

from tools.read_pass import recall


# --- fixtures shaped EXACTLY like the real on-disk files ---------------------
def _entities():
    return [
        {"id": "krsna", "name": "Kṛṣṇa", "kind": "deity",
         "all_forms": ["Kṛṣṇa", "Krishna", "Govinda", "Vāsudeva"],
         "chapters": ["Chapter 10"], "verse_ranges": ["bhp_10.01.001"]},
        {"id": "arjuna", "name": "Arjuna", "kind": "hero",
         "all_forms": ["Arjuna", "Pārtha", "Dhanañjaya"],
         "chapters": ["Chapter 1"], "verse_ranges": ["bhp_01.01.010"]},
        {"id": "kauravas", "name": "Kauravas", "kind": "group",
         "all_forms": ["Kauravas", "Kuru"],
         "chapters": ["Chapter 1"], "verse_ranges": ["bhp_01.02.001"]},
        {"id": "kundalini", "name": "Kundalini", "kind": "force",
         "all_forms": ["Kundalini"],
         "chapters": ["Chapter 5"], "verse_ranges": ["bhp_05.01.001"]},
    ]


def _edges():
    return [
        {"src": "krsna", "rel": "guides", "dst": "arjuna",
         "src_name": "Kṛṣṇa", "dst_name": "Arjuna",
         "chapters": ["Chapter 1"], "verse_ranges": ["bhp_01.01.020"]},
        {"src": "arjuna", "rel": "fights", "dst": "kauravas",
         "src_name": "Arjuna", "dst_name": "Kauravas",
         "chapters": ["Chapter 1"], "verse_ranges": ["bhp_01.02.005"]},
    ]


def _keys():
    return [
        {"symbol": "Krishna", "meaning": "the inner Self / Kutastha"},
        {"symbol": "Arjuna", "meaning": "the individual soul (jiva)"},
        {"symbol": "Kauravas", "meaning": "the inner demonic tendencies"},
        {"symbol": "Kundalini", "meaning": "the coiled awakening force"},
        {"symbol": "Brahma", "meaning": "root consciousness of matter"},  # irrelevant to cue
    ]


def _mem():
    return recall.Memory(entities=_entities(), edges=_edges(), keys=_keys())


# --- the contract -------------------------------------------------------------
def test_recall_returns_envelope():
    env = recall.recall("Tell me about Krishna", _mem())
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"] is True


def test_cue_matches_by_canonical_name():
    env = recall.recall("who is Arjuna", _mem())
    ids = {e["id"] for e in env["data"]["entities"]}
    assert "arjuna" in ids


def test_cue_matches_by_alias_not_just_canonical():
    # "Krishna" is an all_forms alias of canonical "Kṛṣṇa" — recall must find it
    env = recall.recall("what does Govinda teach", _mem())
    ids = {e["id"] for e in env["data"]["entities"]}
    assert "krsna" in ids, "alias 'Govinda' should surface the Kṛṣṇa node"


def test_recall_is_SELECTIVE_not_a_dump():
    # the whole point: a Krishna cue must NOT drag in unrelated Kundalini
    env = recall.recall("tell me about Krishna and Arjuna", _mem())
    ids = {e["id"] for e in env["data"]["entities"]}
    assert "kundalini" not in ids, "unrelated nodes must stay dormant (no data-dump)"


def test_one_hop_associative_cluster_surfaces_neighbors():
    # cue hits Krishna; the associative pull should also surface Arjuna (1 hop away)
    # even though the cue didn't name him — that's associative recall.
    env = recall.recall("Krishna", _mem())
    ids = {e["id"] for e in env["data"]["entities"]}
    assert "krsna" in ids
    assert "arjuna" in ids, "one-hop neighbor should surface via association"


def test_decode_keys_attached_for_recalled_entities_only():
    env = recall.recall("Arjuna", _mem())
    keys = env["data"]["decode_keys"]
    syms = {k["symbol"] for k in keys}
    assert "Arjuna" in syms
    # the irrelevant 'Brahma' key must NOT be attached
    assert "Brahma" not in syms


def test_sat_asat_valence_tagged():
    # Kauravas decode = "inner demonic tendencies" → Asat. Krishna = Self → Sat.
    env = recall.recall("Krishna versus the Kauravas", _mem())
    by_id = {e["id"]: e for e in env["data"]["entities"]}
    assert by_id["kauravas"].get("valence") == "asat"
    assert by_id["krsna"].get("valence") == "sat"


def test_empty_cue_recalls_nothing_gracefully():
    env = recall.recall("", _mem())
    assert env["success"] is True
    assert env["data"]["entities"] == []


def test_no_match_is_success_with_empty_recall_not_error():
    env = recall.recall("xyzzy nonexistent thing", _mem())
    assert env["success"] is True   # no-match is a valid recall, not a failure
    assert env["data"]["entities"] == []
    assert env["data"]["decode_keys"] == []


def test_render_context_produces_injectable_text_block():
    # recall must be able to emit a {knowledge_context} string for the live prompt
    env = recall.recall("Krishna and Arjuna", _mem())
    block = recall.render_context(env["data"])
    assert isinstance(block, str)
    assert "Kṛṣṇa" in block or "Krishna" in block
    assert "Kutastha" in block          # the decoded meaning is in the block
    assert "Arjuna" in block


# --- SCALE / SELECTIVITY against a hub-heavy graph (the real-data lesson) -----
# The fixture above is too small to catch hop-explosion. These build a power-law
# graph like the real one (a hub with hundreds of weak neighbors) and assert that
# recall stays SELECTIVE — surfaces the strongly-associated cluster, not the dump.
def _hub_memory(n_weak=300, n_strong=5):
    """A Krishna hub: n_strong neighbors share many verses, n_weak share just 1."""
    ents = [{"id": "krsna", "name": "Kṛṣṇa", "kind": "deity",
             "all_forms": ["Kṛṣṇa", "Krishna"], "chapters": ["c"], "verse_ranges": ["v"]}]
    edges = []
    for i in range(n_strong):
        ents.append({"id": f"strong{i}", "name": f"Strong{i}", "kind": "hero",
                     "all_forms": [f"Strong{i}"], "chapters": ["c"], "verse_ranges": ["v"]})
        edges.append({"src": "krsna", "rel": "guides", "dst": f"strong{i}",
                      "src_name": "Kṛṣṇa", "dst_name": f"Strong{i}",
                      "verse_ranges": [f"v{j}" for j in range(20)]})  # strong: 20 verses
    for i in range(n_weak):
        ents.append({"id": f"weak{i}", "name": f"Weak{i}", "kind": "minor",
                     "all_forms": [f"Weak{i}"], "chapters": ["c"], "verse_ranges": ["v"]})
        edges.append({"src": "krsna", "rel": "mentions", "dst": f"weak{i}",
                      "src_name": "Kṛṣṇa", "dst_name": f"Weak{i}",
                      "verse_ranges": ["v1"]})  # weak: 1 verse
    return recall.Memory(entities=ents, edges=edges, keys=_keys())


def test_hub_cue_stays_selective_not_a_dump():
    # cue hits a 305-neighbor hub; recall must NOT surface all 305.
    env = recall.recall("Krishna", _hub_memory(n_weak=300, n_strong=5))
    n = len(env["data"]["entities"])
    assert n <= 50, f"hub recall surfaced {n} entities — that's a dump, not recall"


def test_hub_recall_prefers_STRONG_associations():
    # the strongly-bonded neighbors (20 shared verses) must surface before the
    # weakly-bonded ones (1 shared verse) — strength-of-association ranking.
    env = recall.recall("Krishna", _hub_memory(n_weak=300, n_strong=5))
    names = {e["name"] for e in env["data"]["entities"]}
    strong_surfaced = sum(1 for i in range(5) if f"Strong{i}" in names)
    assert strong_surfaced >= 4, "strong associations should surface preferentially"


def test_multi_seed_cue_caps_total_recall():
    # even a cue naming several hubs must stay bounded (no N×hub explosion)
    mem = _hub_memory(n_weak=300, n_strong=5)
    env = recall.recall("Krishna Krishna Krishna", mem)
    assert len(env["data"]["entities"]) <= 50


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
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
