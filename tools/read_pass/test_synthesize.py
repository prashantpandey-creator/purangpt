"""Tests-first for teaching synthesis via reasoning model (Rule 0 precond A).

1,340+ raw teachings across 338 Bhagavata chapters are mostly restatements of
~50 core truths. A reasoning model clusters them, distills the essence, and
preserves the nuance — something a chat model or mechanical dedup can't do
because "surrender to the Lord" and "take shelter of Hari's lotus feet" are
the SAME teaching expressed differently, but "surrender to the Lord" and
"the Lord surrenders to His devotee" are DIFFERENT.

Run: venv/bin/python -m tools.read_pass.test_synthesize   (exit 0)
"""
from __future__ import annotations
import json

from tools.read_pass import synthesize


_RAW_TEACHINGS = [
    {"teaching": "Surrender to the Supreme Lord is the highest dharma.",
     "lens_note": "In Kriya-Yoga, surrender means dissolving the ego in samadhi.",
     "verse_ranges": ["1.2.6"]},
    {"teaching": "Taking shelter of Hari's lotus feet purifies the heart.",
     "lens_note": "The lotus feet represent the base chakra; purification is kundalini ascent.",
     "verse_ranges": ["1.2.17"]},
    {"teaching": "The holy name of the Lord destroys all sins.",
     "verse_ranges": ["6.2.14"]},
    {"teaching": "Devotion to Vishnu transcends all material bondage.",
     "lens_note": "",
     "verse_ranges": ["1.2.20"]},
    {"teaching": "The cycle of birth and death ceases only through God-realization.",
     "verse_ranges": ["3.25.33"]},
]


def _fake_reasoner(prompt, model, key):
    return json.dumps({
        "clusters": [
            {"core_truth": "Surrender/devotion to the Supreme Lord is the ultimate path to liberation.",
             "supporting_teachings": [0, 1, 3],
             "lens_synthesis": "In Kriya-Yoga, surrender = ego-dissolution in samadhi; "
                               "lotus feet = base chakra; purification = kundalini ascent.",
             "verse_citations": ["1.2.6", "1.2.17", "1.2.20"]},
            {"core_truth": "The holy name alone can destroy all karma.",
             "supporting_teachings": [2],
             "lens_synthesis": "",
             "verse_citations": ["6.2.14"]},
            {"core_truth": "Liberation from samsara requires direct God-realization.",
             "supporting_teachings": [4],
             "lens_synthesis": "",
             "verse_citations": ["3.25.33"]},
        ]
    })


def test_synthesize_clusters_related_teachings():
    result = synthesize.synthesize_teachings(_RAW_TEACHINGS, "fake-key",
                                            caller=_fake_reasoner)
    assert result["success"]
    clusters = result["data"]["clusters"]
    # 5 teachings collapsed to 3 clusters (the first cluster merged 3 similar)
    assert len(clusters) == 3
    assert clusters[0]["supporting_teachings"] == [0, 1, 3]


def test_synthesize_preserves_lens_notes():
    result = synthesize.synthesize_teachings(_RAW_TEACHINGS, "fake-key",
                                            caller=_fake_reasoner)
    c0 = result["data"]["clusters"][0]
    # lens synthesis should merge the individual lens notes
    assert "kundalini" in c0["lens_synthesis"] or "samadhi" in c0["lens_synthesis"]


def test_synthesize_envelope_shape():
    result = synthesize.synthesize_teachings(_RAW_TEACHINGS, "fake-key",
                                            caller=_fake_reasoner)
    assert set(result.keys()) == {"success", "data", "metadata", "errors"}
    assert result["data"]["n_raw_teachings"] == 5
    assert result["data"]["n_clusters"] == 3


def test_synthesize_prompt_includes_all_teachings():
    prompt = synthesize.build_prompt(_RAW_TEACHINGS)
    for t in _RAW_TEACHINGS:
        assert t["teaching"][:30] in prompt


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
