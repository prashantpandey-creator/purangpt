"""Tests-first for the biography/lineage distiller (Rule 0 precond A).

Daddy downloaded new Russian Guruji material — chiefly Mossin's "The Awakener"
(Пробуждающий), the authorized 1,121-page biography of Shailendra Sharma, the
fifth Guru of the Kriya Yoga lineage (positioned as the sequel to Yogananda's
Autobiography of a Yogi).

This is NOT decryption commentary (that's guruji_ram.py). It is biography +
lineage + lived encounters with the Puranic cosmos (gods, avatars, Babaji, the
Nath siddhas, the God of Death, alchemy). It connects the abstract graph entities
to how Guruji EXPERIENTIALLY relates to them.

The distiller reads the Russian directly (LLM translates+structures in one pass)
and emits an English lineage framework:
  lineage_chain    — the guru-parampara (who taught whom, up to Sharma)
  biographical_arc — key life events / realizations, ordered
  entity_encounters— graph entities Sharma personally encountered + how
  places           — sacred sites tied to his life (Govardhan, etc.)

Run: venv/bin/python -m tools.read_pass.test_biography   (exit 0)
"""
from __future__ import annotations
import json
import os
import tempfile

from tools.read_pass import biography


def test_make_windows_covers_russian_text():
    text = "\n\n".join(f"Глава {i}. Некоторый текст здесь." for i in range(100))
    windows = biography.make_windows(text, max_chars=800)
    assert len(windows) >= 2
    joined = " ".join(windows)
    assert "Глава 0." in joined and "Глава 99." in joined


def test_merge_lineage_unions_and_orders():
    f1 = {
        "lineage_chain": ["Babaji", "Lahiri Mahasaya"],
        "biographical_arc": [{"event": "Birth in Agra", "order": 1}],
        "entity_encounters": [{"entity": "Hanuman", "encounter": "performed puja"}],
        "places": ["Govardhan"],
    }
    f2 = {
        "lineage_chain": ["Lahiri Mahasaya", "Yukteshwar", "Shailendra Sharma"],
        "biographical_arc": [{"event": "Met Babaji", "order": 3}],
        "entity_encounters": [{"entity": "Yamuna", "encounter": "her arrival"}],
        "places": ["Govardhan", "Gaya"],
    }
    merged = biography.merge_biographies([f1, f2])
    # lineage deduped preserving order
    assert "Babaji" in merged["lineage_chain"]
    assert "Shailendra Sharma" in merged["lineage_chain"]
    assert merged["lineage_chain"].count("Lahiri Mahasaya") == 1
    # places deduped
    assert sorted(merged["places"]) == ["Gaya", "Govardhan"]
    # arc events accumulate
    assert len(merged["biographical_arc"]) == 2
    # entity encounters accumulate
    names = {e["entity"] for e in merged["entity_encounters"]}
    assert names == {"Hanuman", "Yamuna"}


def test_extract_biography_uses_reasoner():
    def fake(prompt, model, key):
        # confirm Russian text reached the prompt
        assert "Шарма" in prompt or "biography" in prompt.lower()
        return json.dumps({
            "lineage_chain": ["Babaji", "Shailendra Sharma"],
            "biographical_arc": [{"event": "Realization at Govardhan", "order": 1}],
            "entity_encounters": [{"entity": "Shiva", "encounter": "vision of Shivalingam"}],
            "places": ["Govardhan"],
        })
    fw = biography.extract_biography("Текст про Шарма", "k", caller=fake)
    assert fw["lineage_chain"][-1] == "Shailendra Sharma"


def test_envelope_shape():
    def fake(prompt, model, key):
        return json.dumps({"lineage_chain": ["X"], "biographical_arc": [],
                           "entity_encounters": [], "places": []})
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "mossin.txt"), "w").write("Шарма текст " * 50)
        env = biography.run(os.path.join(d, "mossin.txt"), "k", caller=fake)
    assert set(env.keys()) == {"success", "data", "metadata", "errors"}
    assert env["success"]
    assert "biography" in env["data"]


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
