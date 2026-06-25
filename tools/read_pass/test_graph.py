"""Tests-first for the graph-merge layer (Rule 0 precond A).

Turns the flat per-chapter records into ONE interconnected graph: merges entity
mentions by canonical name + alias closure, normalizes relationship verbs into
canonical predicates, and exposes lineages/curses/who-did-whom as queryable
slices. ZERO LLM calls — pure deterministic merge.

Run: venv/bin/python -m tools.read_pass.test_graph   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import graph


_TWO_RECORDS = [
    {
        "_provenance": {"chapter_label": "Chapter 1", "seq_start": 1},
        "entities": [
            {"name": "Krishna", "kind": "deity",
             "aliases": ["Krsna", "Govinda", "Mādhava"], "verse_ranges": ["1"]},
            {"name": "Vyasa", "kind": "sage", "verse_ranges": ["2"]},
        ],
        "relationships": [
            {"src": "Vyasa", "rel": "father of", "dst": "Shuka", "verse_ranges": ["2"]},
            {"src": "Vyasa", "rel": "is_author_of", "dst": "Bhagavata",
             "verse_ranges": ["3"]},
        ],
        "teachings": [],
        "story": {"title": "Open", "arc": "x"},
    },
    {
        "_provenance": {"chapter_label": "Chapter 10", "seq_start": 100},
        "entities": [
            # SAME Krishna via alias overlap
            {"name": "Kṛṣṇa", "kind": "deity",
             "aliases": ["Govinda", "Hari", "Mukunda"], "verse_ranges": ["100"]},
            # Vishnu shares Hari with Krishna (avatar theology, both real)
            {"name": "Vishnu", "kind": "deity",
             "aliases": ["Hari", "Narayana"], "verse_ranges": ["101"]},
            {"name": "Shuka", "kind": "sage", "verse_ranges": ["102"]},
            # Cursed person — narrative event
            {"name": "Parikshit", "kind": "king", "verse_ranges": ["103"]},
        ],
        "relationships": [
            {"src": "Shuka", "rel": "son_of", "dst": "Vyasa", "verse_ranges": ["102"]},
            {"src": "Rishi's son", "rel": "cursed", "dst": "Parikshit",
             "verse_ranges": ["103"]},
            {"src": "Krishna", "rel": "is_avatar_of", "dst": "Vishnu",
             "verse_ranges": ["104"]},
        ],
        "teachings": [],
        "story": {"title": "Curse", "arc": "y"},
    },
]


def test_entity_merge_collapses_aliases_into_one_node():
    g = graph.build(_TWO_RECORDS)
    # Krishna + Kṛṣṇa + Krsna + Govinda + Mādhava + Mukunda → ONE node
    krishna = g.find_entity("krishna")
    assert krishna is not None, "Krishna node missing"
    forms = {f.lower() for f in krishna["all_forms"]}
    assert "govinda" in forms and "kṛṣṇa" in forms and "mukunda" in forms, forms
    # node tracks every chapter it appeared in
    assert len(krishna["chapters"]) == 2


def test_shared_alias_keeps_both_nodes_but_records_overlap():
    # Hari is claimed by both Krishna and Vishnu (real in the tradition).
    # We must NOT collapse them — they're distinct nodes with a known overlap.
    g = graph.build(_TWO_RECORDS)
    krishna = g.find_entity("krishna")
    vishnu = g.find_entity("vishnu")
    assert krishna is not None and vishnu is not None
    assert krishna["id"] != vishnu["id"], "must not merge Krishna and Vishnu"
    # the overlap is exposed for inspection
    overlap = g.alias_overlaps()
    pair = tuple(sorted([krishna["id"], vishnu["id"]]))
    assert pair in overlap, f"overlap missing: {overlap}"
    assert "hari" in {a.lower() for a in overlap[pair]}


def test_relationships_normalize_direction():
    # "Vyasa father of Shuka" stays Vyasa->Shuka; "Shuka son_of Vyasa" reverses
    # to Vyasa->Shuka too. Different roots (father vs son) but BOTH point
    # parent->child after direction normalization.
    g = graph.build(_TWO_RECORDS)
    vyasa = g.find_entity("vyasa")
    shuka = g.find_entity("shuka")
    v2s = [e for e in g.edges
           if e["src"] == vyasa["id"] and e["dst"] == shuka["id"]]
    # at least one edge points the lineage direction Vyasa -> Shuka
    assert v2s, f"expected a Vyasa->Shuka edge, got {[ (e['src_name'],e['rel'],e['dst_name']) for e in g.edges]}"
    # and both descendant-queryable
    assert shuka["id"] in {n["id"] for n in g.descendants_of("vyasa")}


def test_lineage_query_returns_descendants():
    g = graph.build(_TWO_RECORDS)
    desc = g.descendants_of("vyasa")
    names = {d["name"].lower() for d in desc}
    assert "shuka" in names


def test_curse_query_returns_curse_events():
    g = graph.build(_TWO_RECORDS)
    curses = g.curses()
    assert len(curses) >= 1
    found = [c for c in curses if c["dst_name"].lower() == "parikshit"]
    assert found, f"Parikshit curse not surfaced: {curses}"


def test_who_did_whom_query_with_predicate_filter():
    g = graph.build(_TWO_RECORDS)
    # "is_avatar_of" mechanically canonicalizes to root "avatar"
    avatars = g.edges_of_kind("avatar")
    assert len(avatars) >= 1, f"predicates seen: {g.predicates()}"
    src = avatars[0]["src_name"].lower()
    assert "krishna" in src or "krsna" in src or "kṛṣṇa" in src


def test_kind_guard_prevents_deity_king_merge():
    # "Hari" is shared by Vishnu (deity) and some king in another text.
    # They must NOT merge because their kinds are incompatible.
    recs = [
        {"_provenance": {"chapter_label": "Ch 1"},
         "entities": [
             {"name": "Vishnu", "kind": "deity", "aliases": ["Hari", "Narayana"], "verse_ranges": []},
         ],
         "relationships": [], "teachings": [], "story": {}},
        {"_provenance": {"chapter_label": "Ch 2"},
         "entities": [
             {"name": "Hari the king", "kind": "king", "aliases": ["Hari"], "verse_ranges": []},
         ],
         "relationships": [], "teachings": [], "story": {}},
    ]
    g = graph.build(recs)
    vishnu = g.find_entity("Vishnu")
    king = g.find_entity("Hari the king")
    assert vishnu is not None and king is not None
    assert vishnu["id"] != king["id"], "deity and king must not merge via shared alias"


def test_macron_preserves_gender_krsna_vs_krsna():
    # Kṛṣṇa (masc, deity) and Kṛṣṇā (fem, Draupadī) MUST remain separate.
    # The macron on the final vowel is a gender marker in Sanskrit.
    recs = [
        {"_provenance": {"chapter_label": "Ch 71"},
         "entities": [
             {"name": "Kṛṣṇa", "kind": "deity", "aliases": ["Govinda"], "verse_ranges": ["1"]},
             {"name": "Draupadī", "kind": "queen", "aliases": ["Kṛṣṇā", "Pāñcālī"], "verse_ranges": ["2"]},
         ],
         "relationships": [], "teachings": [], "story": {}},
    ]
    g = graph.build(recs)
    krishna = g.find_entity("Kṛṣṇa")
    draupadi = g.find_entity("Draupadī")
    assert krishna is not None and draupadi is not None
    assert krishna["id"] != draupadi["id"], \
        f"Kṛṣṇa and Draupadī merged! ids: {krishna['id']}, {draupadi['id']}"
    assert "Govinda" in krishna["all_forms"]
    assert "Pāñcālī" in draupadi["all_forms"]


# ── deity-epithet guard: the Buddha-blob fix (manifest mode) ────────────────
# The bug: supreme deities DELIBERATELY share hundreds of epithets (Hari, Ishwar,
# Bhagavan, Narayana...). Naive alias-union chains Buddha→Vishnu→Hari→Krishna→
# Brahma into ONE 688-form blob. Manifest mode: a shared *supreme epithet*
# between two DEITIES must NOT drive a merge — it becomes an identity EDGE
# (drawn by identity.py), and the manifest nodes stay distinct.

_DEITY_CHAIN = [
    {"_provenance": {"chapter_label": "Ch A"},
     "entities": [
         # Each deity lists the NEXT as an epithet/alias — the classic chain.
         {"name": "Buddha", "kind": "deity", "aliases": ["Vishnu"], "verse_ranges": ["1"]},
         {"name": "Vishnu", "kind": "deity", "aliases": ["Hari", "Narayana"], "verse_ranges": ["2"]},
         {"name": "Hari", "kind": "deity", "aliases": ["Krishna"], "verse_ranges": ["3"]},
         {"name": "Krishna", "kind": "deity", "aliases": ["Govinda", "Madhava"], "verse_ranges": ["4"]},
     ],
     "relationships": [], "teachings": [], "story": {}},
]


def test_manifest_mode_breaks_the_deity_epithet_blob():
    # In manifest mode the four supreme deities must NOT collapse into one node.
    g = graph.build(_DEITY_CHAIN, manifest_mode=True)
    buddha = g.find_entity("Buddha")
    krishna = g.find_entity("Krishna")
    vishnu = g.find_entity("Vishnu")
    assert buddha is not None and krishna is not None and vishnu is not None
    ids = {buddha["id"], krishna["id"], vishnu["id"]}
    assert len(ids) == 3, f"blob! deities merged into ids={ids}"
    # no single node should have swallowed the whole chain's forms
    for e in g.entities:
        assert len(e["all_forms"]) < 6, \
            f"{e['name']} blobbed {len(e['all_forms'])} forms: {e['all_forms']}"


def test_manifest_mode_still_merges_pure_spelling_variants():
    # Manifest mode must NOT over-correct: Krishna/Kṛṣṇa/Krsna (same name,
    # transliteration variants, NOT a supreme epithet) still merge to one node.
    recs = [
        {"_provenance": {"chapter_label": "Ch 1"},
         "entities": [
             {"name": "Krishna", "kind": "deity", "aliases": ["Krsna", "Govinda"], "verse_ranges": ["1"]},
         ], "relationships": [], "teachings": [], "story": {}},
        {"_provenance": {"chapter_label": "Ch 2"},
         "entities": [
             {"name": "Kṛṣṇa", "kind": "deity", "aliases": ["Govinda"], "verse_ranges": ["2"]},
         ], "relationships": [], "teachings": [], "story": {}},
    ]
    g = graph.build(recs, manifest_mode=True)
    k1 = g.find_entity("Krishna")
    k2 = g.find_entity("Kṛṣṇa")
    assert k1 is not None and k2 is not None
    assert k1["id"] == k2["id"], "spelling variants must still merge in manifest mode"


def test_peer_proper_name_confusion_does_not_merge():
    # The decoder sometimes lists a DISTINCT being as an alias of another because
    # they share a name-fragment: "Rama" gets "Balarama" and "Parashurama" as
    # aliases. Each is independently substantial (its own records + edges). They
    # must NOT merge into one node — that conflation is the bug the workers flagged.
    recs = [
        # Rama (Ramayana) — substantial, and the decoder wrongly tags peers as aliases
        {"_provenance": {"chapter_label": "R 1"},
         "entities": [{"name": "Rama", "kind": "king",
                       "aliases": ["Raghava", "Balarama", "Parashurama"], "verse_ranges": ["1"]}],
         "relationships": [{"src": "Rama", "rel": "wields", "dst": "Kodanda"}],
         "teachings": [], "story": {}},
        # Balarama — independently substantial (own records + own edges)
        {"_provenance": {"chapter_label": "BhP 10.1"},
         "entities": [{"name": "Balarama", "kind": "king",
                       "aliases": ["Baladeva", "Sankarshana"], "verse_ranges": ["2"]}],
         "relationships": [{"src": "Balarama", "rel": "brother", "dst": "Krishna"}],
         "teachings": [], "story": {}},
        {"_provenance": {"chapter_label": "BhP 10.2"},
         "entities": [{"name": "Balarama", "kind": "king", "aliases": ["Halayudha"], "verse_ranges": ["3"]}],
         "relationships": [{"src": "Balarama", "rel": "wields", "dst": "Plough"}],
         "teachings": [], "story": {}},
        # Parashurama — independently substantial
        {"_provenance": {"chapter_label": "MBh 3.1"},
         "entities": [{"name": "Parashurama", "kind": "sage",
                       "aliases": ["Bhargava", "Jamadagnya"], "verse_ranges": ["4"]}],
         "relationships": [{"src": "Parashurama", "rel": "wields", "dst": "Axe"}],
         "teachings": [], "story": {}},
    ]
    g = graph.build(recs, manifest_mode=True)
    rama = g.find_entity("Rama")
    bala = g.find_entity("Balarama")
    parashu = g.find_entity("Parashurama")
    assert rama and bala and parashu, "all three beings must exist as nodes"
    ids = {rama["id"], bala["id"], parashu["id"]}
    assert len(ids) == 3, f"peer-name confusion merged distinct beings: ids={ids}"
    # Rama must not have swallowed the peers' names into its forms
    assert "Balarama" not in rama["all_forms"], f"Rama swallowed Balarama: {rama['all_forms']}"
    assert "Parashurama" not in rama["all_forms"], f"Rama swallowed Parashurama: {rama['all_forms']}"


def test_weak_alias_does_not_override_strong_identity():
    # A name mentioned as an alias ONCE must not absorb an entity that stands on its
    # own across many records. (Asymmetry: Balarama's 2 own records + edges outweigh
    # a single stray "alias" mention inside a Rama record.)
    recs = [
        {"_provenance": {"chapter_label": "A"},
         "entities": [{"name": "Indra", "kind": "deity", "aliases": ["Shakra", "Shahindra"], "verse_ranges": ["1"]}],
         "relationships": [], "teachings": [], "story": {}},
    ] + [
        {"_provenance": {"chapter_label": f"S{i}"},
         "entities": [{"name": "Shahindra", "kind": "king", "aliases": [], "verse_ranges": [str(i)]}],
         "relationships": [{"src": "Shahindra", "rel": "rules", "dst": "City"}],
         "teachings": [], "story": {}}
        for i in range(5)
    ]
    g = graph.build(recs, manifest_mode=True)
    indra = g.find_entity("Indra")
    shah = g.find_entity("Shahindra")
    assert indra and shah
    assert indra["id"] != shah["id"], "weak alias mention merged two distinct beings"


def test_manifest_mode_records_severed_epithet_as_overlap():
    # The severed link isn't lost — it's recorded as an overlap so identity.py
    # can later type it (avatar_of / aspect_of / same_as via the reasoner).
    g = graph.build(_DEITY_CHAIN, manifest_mode=True)
    buddha = g.find_entity("Buddha")
    vishnu = g.find_entity("Vishnu")
    overlap = g.alias_overlaps()
    pair = tuple(sorted([buddha["id"], vishnu["id"]]))
    assert pair in overlap, f"Buddha-Vishnu epithet link not recorded: {list(overlap)[:5]}"


def test_default_mode_unchanged_legacy_behavior():
    # Back-compat: default (manifest_mode=False) keeps the original behavior so
    # nothing downstream that relied on the old build breaks silently.
    g_default = graph.build(_TWO_RECORDS)
    g_explicit = graph.build(_TWO_RECORDS, manifest_mode=False)
    assert len(g_default.entities) == len(g_explicit.entities)


def test_graph_envelope_serializable():
    g = graph.build(_TWO_RECORDS)
    env = graph.run(_TWO_RECORDS)
    assert env["success"] is True
    d = env["data"]
    assert d["n_entities"] == len(g.entities)
    assert d["n_edges"] == len(g.edges)
    # round-trips as JSON
    assert json.dumps(env)


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
