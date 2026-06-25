"""graph_rebuild — tests-first (Rule 0, precondition A).

Tests the manifest rebuild pipeline: load real records -> graph.build() ->
apply identity merges -> prune isolates -> write manifest.

Run: venv/bin/python -m tools.graph_rebuild.test_check   (from purangpt/ repo root)
"""
from __future__ import annotations

import sys

from tools.graph_rebuild.check import (
    apply_identity_merges,
    apply_curated_facts,
    prune_isolates,
    scrub_hallucinated_cites,
    run,
)


def _make_entities():
    return [
        {"id": "krishna", "name": "Krishna", "kind": "deity",
         "all_forms": ["Krishna", "Achyuta"], "chapters": ["Ch 1", "Ch 2"], "verse_ranges": []},
        {"id": "krsna", "name": "Kṛṣṇa", "kind": "deity",
         "all_forms": ["Kṛṣṇa", "Vāsudeva"], "chapters": ["Ch 3"], "verse_ranges": []},
        {"id": "arjuna", "name": "Arjuna", "kind": "king",
         "all_forms": ["Arjuna"], "chapters": ["Ch 1"], "verse_ranges": []},
        {"id": "lonely", "name": "Lonely", "kind": "place",
         "all_forms": ["Lonely"], "chapters": ["Ch 9"], "verse_ranges": []},
    ]


def _make_edges():
    return [
        {"src": "krishna", "rel": "teaches", "dst": "arjuna",
         "src_name": "Krishna", "dst_name": "Arjuna",
         "chapters": ["Ch 1"], "verse_ranges": ["bg_02.47"]},
        {"src": "krsna", "rel": "avatar", "dst": "arjuna",
         "src_name": "Kṛṣṇa", "dst_name": "Arjuna",
         "chapters": ["Ch 3"], "verse_ranges": ["bhp_10.01"]},
    ]


def _make_identity_edges():
    return [
        {"src": "krishna", "dst": "krsna", "type": "same_as",
         "evidence": "name variant: Krishna = Kṛṣṇa"},
    ]


def test_identity_merge_reduces_entities():
    entities = _make_entities()
    edges = _make_edges()
    ie = _make_identity_edges()
    new_ents, new_edges, stats = apply_identity_merges(entities, edges, ie)
    assert stats["merges_applied"] == 1
    krishna_ids = [e["id"] for e in new_ents if "krishna" in e["id"] or "krsna" in e["id"]]
    assert len(krishna_ids) == 1, f"should be merged into one, got {krishna_ids}"
    merged = next(e for e in new_ents if e["id"] == krishna_ids[0])
    assert "Krishna" in merged["all_forms"]
    assert "Kṛṣṇa" in merged["all_forms"] or "Vāsudeva" in merged["all_forms"]
    assert "Ch 3" in merged["chapters"]


def test_identity_merge_rewires_edges():
    entities = _make_entities()
    edges = _make_edges()
    ie = _make_identity_edges()
    new_ents, new_edges, stats = apply_identity_merges(entities, edges, ie)
    srcs = {e["src"] for e in new_edges}
    dsts = {e["dst"] for e in new_edges}
    all_ids = srcs | dsts
    assert "krsna" not in all_ids, "krsna should be rewritten to krishna in edges"


def test_prune_isolates():
    entities = _make_entities()
    edges = _make_edges()
    pruned_ents, n_pruned = prune_isolates(entities, edges)
    assert n_pruned == 1
    assert not any(e["id"] == "lonely" for e in pruned_ents)
    assert any(e["id"] == "arjuna" for e in pruned_ents)


def test_prune_keeps_connected():
    entities = _make_entities()
    edges = _make_edges()
    pruned_ents, _ = prune_isolates(entities, edges)
    connected_ids = {e["id"] for e in pruned_ents}
    assert "krishna" in connected_ids
    assert "arjuna" in connected_ids


def test_curated_adds_missing_entity_and_edge():
    """The decode missed Satyacharan (Guruji's real guru) — curated overlay must
    inject the entity AND the guru edge so the lineage is complete.
    """
    entities = [
        {"id": "tinkori lahiri", "name": "Tinkori Lahiri", "kind": "sage",
         "all_forms": ["Tinkori Lahiri"], "chapters": [], "verse_ranges": []},
        {"id": "shailendra sharma", "name": "Shailendra Sharma", "kind": "sage",
         "all_forms": ["Shailendra Sharma"], "chapters": [], "verse_ranges": []},
    ]
    edges = []
    curated = {
        "entities": [
            {"id": "satyacharan lahiri", "name": "Satyacharan Lahiri", "kind": "sage",
             "all_forms": ["Satyacharan Lahiri", "Satyacharan"]},
        ],
        "lineage_edges": [
            {"src": "tinkori lahiri", "rel": "guru_of", "dst": "satyacharan lahiri",
             "src_name": "Tinkori Lahiri", "dst_name": "Satyacharan Lahiri"},
            {"src": "satyacharan lahiri", "rel": "guru_of", "dst": "shailendra sharma",
             "src_name": "Satyacharan Lahiri", "dst_name": "Shailendra Sharma"},
        ],
    }
    new_ents, new_edges, stats = apply_curated_facts(entities, edges, curated)
    ids = {e["id"] for e in new_ents}
    assert "satyacharan lahiri" in ids, "curated entity must be added"
    assert stats["entities_added"] == 1
    assert stats["edges_added"] == 2
    rels = {(e["src"], e["rel"], e["dst"]) for e in new_edges}
    assert ("satyacharan lahiri", "guru_of", "shailendra sharma") in rels


def test_curated_removes_wrong_edge():
    """The decode wrongly put Yogananda in Guruji's chain — curated overlay must
    remove edges matching the removal pattern.
    """
    entities = [
        {"id": "lahiri mahasaya", "name": "Lahiri Mahasaya", "kind": "sage",
         "all_forms": [], "chapters": [], "verse_ranges": []},
        {"id": "paramahansa yogananda", "name": "Paramahansa Yogananda", "kind": "sage",
         "all_forms": [], "chapters": [], "verse_ranges": []},
    ]
    edges = [
        {"src": "lahiri mahasaya", "rel": "disciple", "dst": "paramahansa yogananda",
         "src_name": "Lahiri Mahasaya", "dst_name": "Paramahansa Yogananda"},
        {"src": "lahiri mahasaya", "rel": "father_of", "dst": "tinkori lahiri",
         "src_name": "Lahiri Mahasaya", "dst_name": "Tinkori Lahiri"},
    ]
    curated = {
        "remove_edges": [
            {"src_contains": "lahiri", "rel": "disciple", "dst_contains": "yogananda",
             "reason": "Yogananda is on the parallel branch, not Guruji's chain"},
        ],
    }
    _, new_edges, stats = apply_curated_facts(entities, edges, curated)
    assert stats["edges_removed"] == 1
    rels = {(e["src"], e["rel"], e["dst"]) for e in new_edges}
    assert ("lahiri mahasaya", "disciple", "paramahansa yogananda") not in rels
    assert ("lahiri mahasaya", "father_of", "tinkori lahiri") in rels, "unrelated edge survives"


def test_curated_entity_survives_prune_via_curated_edge():
    """A curated entity connected only by a curated edge must NOT be pruned as an
    isolate — that was the original bug (Satyacharan pruned for lack of edges).
    """
    entities = [
        {"id": "shailendra sharma", "name": "Shailendra Sharma", "kind": "sage",
         "all_forms": [], "chapters": [], "verse_ranges": []},
    ]
    edges = []
    curated = {
        "entities": [
            {"id": "satyacharan lahiri", "name": "Satyacharan Lahiri", "kind": "sage"},
        ],
        "lineage_edges": [
            {"src": "satyacharan lahiri", "rel": "guru_of", "dst": "shailendra sharma",
             "src_name": "Satyacharan Lahiri", "dst_name": "Shailendra Sharma"},
        ],
    }
    new_ents, new_edges, _ = apply_curated_facts(entities, edges, curated)
    pruned, n_pruned = prune_isolates(new_ents, new_edges)
    pruned_ids = {e["id"] for e in pruned}
    assert "satyacharan lahiri" in pruned_ids, "curated entity must survive prune"
    assert n_pruned == 0


def test_curated_split_forms_moves_epithets_off_host():
    """split_forms: epithet-level conflation (Parashurama/Balarama epithets stuck
    inside the Rama node) must be MOVED to the rightful node. The bare-name guard in
    graph.py can't catch these — they arrive as distinct epithets, not the bare name.
    """
    entities = [
        {"id": "rama", "name": "Rama", "kind": "deity",
         "all_forms": ["Rama", "Raghava", "Halayudha", "Jamadagnyamahadarpadalana"],
         "chapters": [], "verse_ranges": []},
        {"id": "balarama", "name": "Balarama", "kind": "deity",
         "all_forms": ["Balarama"], "chapters": [], "verse_ranges": []},
        {"id": "parashurama", "name": "Parashurama", "kind": "sage",
         "all_forms": ["Parashurama"], "chapters": [], "verse_ranges": []},
    ]
    curated = {
        "split_forms": [
            {"from_id": "rama", "to_id": "balarama", "forms": ["Halayudha"],
             "reason": "Halayudha is a Balarama epithet"},
            {"from_id": "rama", "to_id": "parashurama",
             "forms": ["Jamadagnyamahadarpadalana"],
             "reason": "Jamadagni's-son epithet = Parashurama"},
        ],
    }
    new_ents, _, stats = apply_curated_facts(entities, [], curated)
    by_id = {e["id"]: e for e in new_ents}
    assert "Halayudha" not in by_id["rama"]["all_forms"], "epithet must leave host"
    assert "Jamadagnyamahadarpadalana" not in by_id["rama"]["all_forms"]
    assert "Halayudha" in by_id["balarama"]["all_forms"], "epithet joins rightful node"
    assert "Jamadagnyamahadarpadalana" in by_id["parashurama"]["all_forms"]
    assert "Raghava" in by_id["rama"]["all_forms"], "legit Rama epithet stays"
    assert stats.get("forms_moved", 0) == 2


def test_envelope_shape():
    env = run(dry_run=True)
    assert "success" in env
    assert "data" in env
    assert "metadata" in env
    assert "errors" in env
    if env["success"]:
        d = env["data"]
        assert "n_entities_before" in d
        assert "n_entities_after" in d
        assert "n_edges_before" in d
        assert "n_edges_after" in d
        assert "merges_applied" in d
        assert "isolates_pruned" in d


def _make_records_with_cites():
    return [
        {
            "entities": [
                {"name": "Arjuna", "verse_ranges": ["bhp_01.01.001", "bg_02.47"]},
                {"name": "Krishna", "verse_ranges": ["bhp_10.01.002"]},
            ],
            "relationships": [
                {"source": "Krishna", "target": "Arjuna", "verse_ranges": ["99", "100"]},
            ],
            "teachings": [],
            "_provenance": {"chapter_label": "Ch 1"},
        }
    ]


def test_scrub_blanks_when_no_source_markers():
    records = _make_records_with_cites()
    scrubbed, stats = scrub_hallucinated_cites(records, "mahabharata_v1", {})
    for node in scrubbed[0]["entities"]:
        assert node["verse_ranges"] == [], f"should be blank, got {node['verse_ranges']}"
    assert stats["stripped_cites"] > 0


def test_scrub_keeps_own_prefix():
    records = _make_records_with_cites()
    source_prefixes = {"bhagavata": {"bhp"}}
    scrubbed, stats = scrub_hallucinated_cites(records, "bhagavata_v2", source_prefixes)
    arjuna = scrubbed[0]["entities"][0]
    assert "bhp_01.01.001" in arjuna["verse_ranges"]


def test_scrub_strips_foreign_prefix():
    records = _make_records_with_cites()
    source_prefixes = {"brahma": {"brp"}}
    scrubbed, stats = scrub_hallucinated_cites(records, "brahma_v1", source_prefixes)
    arjuna = scrubbed[0]["entities"][0]
    assert "bhp_01.01.001" not in arjuna["verse_ranges"], "bhp_ on brahma should be stripped"
    assert stats["stripped_cites"] > 0


def test_scrub_strips_bare_numbers():
    records = _make_records_with_cites()
    source_prefixes = {"brahma": {"brp"}}
    scrubbed, stats = scrub_hallucinated_cites(records, "brahma_v1", source_prefixes)
    rel = scrubbed[0]["relationships"][0]
    assert rel["verse_ranges"] == [], f"bare numbers should be stripped, got {rel['verse_ranges']}"


def test_rel_is_merges_rejected():
    """Theological 'Shiva is Vishnu' (evidence 'rel: is') must NOT merge entities —
    that collapses the whole pantheon into one blob. Only name-variant same_as
    merges are real entity identity.
    """
    entities = [
        {"id": "shiva", "name": "Shiva", "kind": "deity",
         "all_forms": ["Shiva"], "chapters": [], "verse_ranges": []},
        {"id": "vishnu", "name": "Vishnu", "kind": "deity",
         "all_forms": ["Vishnu"], "chapters": [], "verse_ranges": []},
        {"id": "krsna", "name": "Kṛṣṇa", "kind": "deity",
         "all_forms": ["Kṛṣṇa"], "chapters": [], "verse_ranges": []},
        {"id": "krishna", "name": "Krishna", "kind": "deity",
         "all_forms": ["Krishna"], "chapters": [], "verse_ranges": []},
    ]
    edges = [
        {"src": "shiva", "rel": "teaches", "dst": "vishnu",
         "src_name": "Shiva", "dst_name": "Vishnu", "chapters": [], "verse_ranges": []},
        {"src": "krsna", "rel": "teaches", "dst": "vishnu",
         "src_name": "Kṛṣṇa", "dst_name": "Vishnu", "chapters": [], "verse_ranges": []},
    ]
    ie = [
        {"src": "shiva", "dst": "vishnu", "type": "same_as", "evidence": "rel: is"},
        {"src": "krishna", "dst": "krsna", "type": "same_as",
         "evidence": "name variant: Krishna = Kṛṣṇa"},
    ]
    new_ents, _, stats = apply_identity_merges(entities, edges, ie)
    ids = {e["id"] for e in new_ents}
    # Shiva and Vishnu must stay SEPARATE (rel: is rejected)
    shiva = next(e for e in new_ents if e["id"] == "shiva")
    assert "Vishnu" not in shiva["all_forms"], "Shiva must NOT absorb Vishnu via 'rel: is'"
    assert "vishnu" in ids and "shiva" in ids, "both deities must survive as distinct"
    # but Krishna/Kṛṣṇa (name variant) SHOULD merge
    krishna_nodes = [e for e in new_ents if e["id"] in ("krishna", "krsna")]
    assert len(krishna_nodes) == 1, "name-variant Krishna/Kṛṣṇa should still merge"
    assert stats["merges_applied"] == 1, "only the name-variant merge counts"


def test_scrub_keeps_mbh_on_mahabharata():
    records = [
        {
            "entities": [
                {"name": "Arjuna", "verse_ranges": ["mbh_01.001.001", "bhp_01.01.001"]},
            ],
            "relationships": [],
            "teachings": [],
        }
    ]
    source_prefixes = {"mahabharata": {"mbh"}}
    scrubbed, stats = scrub_hallucinated_cites(records, "mahabharata_v1", source_prefixes)
    arjuna = scrubbed[0]["entities"][0]
    assert "mbh_01.001.001" in arjuna["verse_ranges"], "own mbh_ prefix should be kept"
    assert "bhp_01.01.001" not in arjuna["verse_ranges"], "foreign bhp_ should be stripped"
    assert stats["stripped_cites"] == 1


def test_scrub_keeps_mbh_on_bori_suffix_key():
    """The decode tag 'mahabharata_bori' must still map to the 'mahabharata'
    prefix set — the corpus-source suffix (_bori/_gretil/_leiden) must be
    stripped, or all the clean mbh_ cites get wrongly blanked.
    """
    records = [
        {
            "entities": [
                {"name": "Bhishma", "verse_ranges": ["mbh_06.023.001"]},
            ],
            "relationships": [],
            "teachings": [],
        }
    ]
    source_prefixes = {"mahabharata": {"mbh"}}
    scrubbed, stats = scrub_hallucinated_cites(records, "mahabharata_bori", source_prefixes)
    bhishma = scrubbed[0]["entities"][0]
    assert "mbh_06.023.001" in bhishma["verse_ranges"], "BORI mbh_ cites must survive"
    assert stats["stripped_cites"] == 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
