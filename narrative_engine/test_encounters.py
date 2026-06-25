"""Tests for encounters.py — the classified encounter bank.

Run: venv/bin/python -m narrative_engine.test_encounters
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from narrative_engine import encounters as enc

_passed = 0
_failed = 0


def _check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  OK  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}: {detail}")


def main():
    if not os.path.exists(enc._BIO_PATH):
        print(f"SKIP: {enc._BIO_PATH} not found")
        return 0

    print("--- classifier unit rules ---")
    # register: beheld > glimpsed > told
    _check("samadhi -> beheld", enc._classify_register("entered samadhi and realization") == "beheld")
    _check("materialized -> glimpsed", enc._classify_register("appeared and materialized at Govardhan") == "glimpsed")
    _check("heard story -> told", enc._classify_register("heard a story about him") == "told")
    _check("empty -> told (conservative)", enc._classify_register("xyz") == "told")

    # act: lineage names always win
    _check("Babaji -> lineage", enc._classify_act("Mahavatar Babaji", "anything") == "lineage")
    _check("Satyacharan -> lineage", enc._classify_act("Satyacharan Lahiri", "taught kriya") == "lineage")
    _check("Omkar -> act3", enc._classify_act("Shiva", "taught Omkar kriya and conscious exit") == "act3_rudra")
    _check("smashan -> act2", enc._classify_act("Hanuman", "appeared at the smashan during the python attack") == "act2_vishnu")
    _check("khechari -> act1", enc._classify_act("Shiva", "khechari was mastered") == "act1_brahma")
    _check("random -> ambient", enc._classify_act("Djinns", "saw coins in a fort") == "ambient")

    # principle index
    _check("Shiva principle = Time", "Time" in enc._principle_for("Shiva (Mahadev)"))
    _check("Hanuman principle = prana", "prana" in enc._principle_for("Hanuman"))
    _check("Yama principle = death", "death" in enc._principle_for("Yama (Yamaraj)"))
    _check("unknown -> empty principle", enc._principle_for("Djinns") == "")

    print("\n--- encounter_bank (real biography) ---")
    r = enc.encounter_bank()
    _check("bank envelope", r["success"])
    d = r["data"]
    total = r["metadata"]["total"]
    _check("bank has many encounters", total > 100, f"got {total}")
    _check("every encounter has register", all(c["register"] in ("told", "glimpsed", "beheld") for c in d["encounters"]))
    _check("every encounter has act", all(c["act"] in ("lineage", "act1_brahma", "act2_vishnu", "act3_rudra", "ambient") for c in d["encounters"]))
    _check("distribution covers >=3 registers", len([k for k, v in d["by_register"].items() if v > 0]) >= 2)
    _check("lineage act is populated", d["by_act"].get("lineage", 0) > 0)

    print("\n--- encounters_for_act ---")
    r2 = enc.encounters_for_act("act2_vishnu")
    _check("act2 query envelope", r2["success"])
    _check("act2 has encounters", r2["metadata"]["n"] > 0)
    _check("act2 results all act2", all(c["act"] == "act2_vishnu" for c in r2["data"]["encounters"]))

    print("\n--- encounters_with ---")
    r3 = enc.encounters_with("Babaji")
    _check("babaji query envelope", r3["success"])
    _check("babaji has many encounters", r3["metadata"]["n"] >= 5, f"got {r3['metadata']['n']}")
    _check("babaji results all lineage", all(c["act"] == "lineage" for c in r3["data"]["encounters"]))

    print(f"\n{'='*40}\n  {_passed} passed, {_failed} failed\n{'='*40}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
