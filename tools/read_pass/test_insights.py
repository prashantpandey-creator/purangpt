"""Tests-first for the INSIGHT layer — emergent understanding from the connected graph.

This is the layer daddy asked for: "what about the knowledge we get AFTER we
connect all this?" Not extraction, not cleaning — THINKING. The reasoning model
reads the connected graph and produces insights that no single chapter contains:

  - Pattern detection: "avatars for knowledge vs avatars for destruction"
  - Cross-text reconciliation: "Bhagavata and Vishnu Purana disagree on X because..."
  - Karmic chain tracing: curse in ch12 → incarnation in ch30 → liberation in ch87
  - Theological synthesis: "the Puranic position on free will vs divine grace"

The insight layer operates on the GRAPH, not on source text. It's the only stage
that genuinely needs the reasoning model to THINK, not just classify or cluster.

Run: venv/bin/python -m tools.read_pass.test_insights   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import insights


_GRAPH_SUMMARY = {
    "n_entities": 2256,
    "n_edges": 2484,
    "narrative_hubs": [
        {"name": "Krishna", "n_predicates": 137, "sample_preds": ["killed", "teaches", "married_to", "avatar"]},
        {"name": "Brahma", "n_predicates": 59, "sample_preds": ["created", "teaches", "cursed"]},
    ],
    "cross_chapter_chains": [
        {"curse": "Sages cursed Jaya & Vijaya", "chapter": "16",
         "consequences": [
             {"event": "Born as Hiranyaksha & Hiranyakashipu", "chapter": "3"},
             {"event": "Born as Ravana & Kumbhakarna", "chapter": "10"},
             {"event": "Liberated by Krishna as Shishupala & Dantavakra", "chapter": "14"}]},
    ],
    "avatar_actions": [
        {"avatar": "Kapila", "source": "Vishnu", "actions": ["teaches Devahūti"]},
        {"avatar": "Narasimha", "source": "Vishnu", "actions": ["killed Hiranyakashipu"]},
    ],
    "teaching_clusters": [
        {"core_truth": "Surrender/devotion is the supreme path", "n_instances": 47},
        {"core_truth": "Material world is illusory/temporary", "n_instances": 33},
    ],
}


def _fake_reasoner(prompt, model, key):
    return json.dumps({
        "insights": [
            {"type": "pattern",
             "title": "Two classes of avatars: Knowledge-givers vs Protectors",
             "insight": "Vishnu's avatars serve two distinct functions in the Bhagavata: "
                        "knowledge-transmission (Kapila teaches Devahūti, Vyāsa compiles "
                        "the Vedas) and cosmic-protection (Narasimha kills Hiranyakashipu, "
                        "Varaha lifts the Earth). The Bhagavata privileges the teaching "
                        "avatars — they get full philosophical discourses while the warrior "
                        "avatars get narrative action sequences.",
             "evidence": ["Kapila-Devahūti dialogue spans 7 chapters (3.25-3.33)",
                          "Narasimha episode is 2 chapters (7.8-7.9)"],
             "confidence": "high",
             "cross_references": ["Vishnu Purana lists the same avatars but without "
                                  "this structural asymmetry"]},
            {"type": "karmic_chain",
             "title": "The Jaya-Vijaya triple incarnation cycle",
             "insight": "The curse on Vaikuntha's gatekeepers (BhP 3.16) generates a "
                        "3-birth redemption arc that IS the Bhagavata's narrative spine: "
                        "Hiranyaksha/Hiranyakashipu → Ravana/Kumbhakarna → Shishupala/"
                        "Dantavakra. Each pair is killed by a progressively more intimate "
                        "form of Vishnu (Varaha/Narasimha → Rama → Krishna), culminating "
                        "in liberation through direct personal encounter with the Supreme.",
             "evidence": ["BhP 3.16: curse", "BhP 7.1: first birth", "BhP 10.87: final liberation"],
             "confidence": "high",
             "cross_references": []},
        ],
        "meta_observation": "The Bhagavata Purana is not a chronicle — it is a "
                           "theological argument structured as narrative. Every major "
                           "story arc demonstrates a single thesis: the supremacy of "
                           "bhakti over jnana and karma."
    })


def test_insight_generation_produces_typed_insights():
    result = insights.generate_insights(_GRAPH_SUMMARY, "fake-key",
                                        caller=_fake_reasoner)
    assert result["success"]
    ins = result["data"]["insights"]
    assert len(ins) >= 2
    types = {i["type"] for i in ins}
    assert "pattern" in types or "karmic_chain" in types


def test_insights_carry_evidence_and_confidence():
    result = insights.generate_insights(_GRAPH_SUMMARY, "fake-key",
                                        caller=_fake_reasoner)
    for i in result["data"]["insights"]:
        assert "evidence" in i and isinstance(i["evidence"], list)
        assert "confidence" in i


def test_meta_observation_present():
    result = insights.generate_insights(_GRAPH_SUMMARY, "fake-key",
                                        caller=_fake_reasoner)
    assert result["data"].get("meta_observation")


def test_insight_prompt_includes_graph_evidence():
    prompt = insights.build_prompt(_GRAPH_SUMMARY)
    assert "Krishna" in prompt
    assert "137" in prompt  # predicate count
    assert "Jaya" in prompt or "curse" in prompt.lower()


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
