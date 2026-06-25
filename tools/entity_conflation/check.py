"""entity_conflation — detect graph nodes that conflate DISTINCT beings.

The Ram/Parashuram bug (daddy flagged it twice): the decoder hands the bare alias
"Rama" to three different figures — Dasharatha's son (Ayodhya prince), Jamadagni's
son (Parashurama the axe-warrior), and Balarama (Krishna's brother). The identity
merge + alias bleed then collapse them into one node. Same class: any node whose
all_forms encode CONFLICTING distinct identities.

Detection key: a node is conflated when its forms carry markers of >1 KNOWN-distinct
being (different patronymics, or names of figures the tradition treats as separate).
This must NOT flag a legitimate epithet cluster (Vishnu's 1000 names on Vishnu).

Input contract:  run(manifest_path="") -> envelope
Output (data on success): { n_entities, n_conflated, conflations:[{id,name,groups,forms}] }
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List


_MANIFEST = os.path.join(os.path.dirname(__file__), "..", "read_pass", "out", "graph_manifest.json")


def _envelope(success, data, metadata, errors):
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


# Distinct-being signatures: forms matching DIFFERENT entries here = a conflation.
# Each tuple is (group_label "family_variant", regex). A node hitting >=2 distinct
# VARIANTS within a family (e.g. rama_dasharatha + rama_parashurama) is conflated.
_DISTINCT_SIGNATURES = [
    # The three Ramas — each pinned by its own patronymic / unique marker
    ("rama_dasharatha", re.compile(r"dashara|raghav|raghu|ayodhya|ramachandra|kausaly|\bsita\b", re.I)),
    ("rama_parashurama", re.compile(r"parashu|parasu|jamadagn|bhargava|khandaparasu", re.I)),
    ("rama_balarama", re.compile(r"balaram|baladev|halayudh|revati|sankarsan", re.I)),
    # Indra vs Shailendra/Shahindra (the other flagged pair)
    ("indra_deva", re.compile(r"\b(shakra|devendra|purandara|vasava|maghavan|sahasraksha)\b", re.I)),
    ("indra_shail", re.compile(r"shailendra|shahindra|shailesh", re.I)),
    # Krishna (Devaki's) vs Krishna Dvaipayana (= Vyasa)
    ("krishna_devaki", re.compile(r"devaki|gopala|govinda|yashoda|nandagopa|\bgopi", re.I)),
    ("krishna_dvaipayana", re.compile(r"dvaipayan|\bvyasa\b|badarayan", re.I)),
]

_PATRONYM_RE = re.compile(r"([A-Za-zāīūṛṣśṇṭḍ]+?)(?:'s son|\s+nandana|\s+suta|\s+putra|\s+atmaja)", re.I)
_SON_OF_RE = re.compile(r"son of ([A-Za-zāīūṛṣśṇṭḍ]+)", re.I)


def incompatible_markers(forms: List[str]) -> List[str]:
    """Return the DISTINCT-being group labels this form-list triggers.

    1. Curated _DISTINCT_SIGNATURES hits (family_variant labels).
    2. Distinct patronymics ("<A>'s son" + "<B>'s son") as parent:<stem> labels.
    """
    hit = set()
    blob = " | ".join(forms)
    for label, rx in _DISTINCT_SIGNATURES:
        if rx.search(blob):
            hit.add(label)

    parents = set()
    for f in forms:
        for m in _PATRONYM_RE.finditer(f):
            parents.add(m.group(1).lower()[:6])
        for m in _SON_OF_RE.finditer(f):
            parents.add(m.group(1).lower()[:6])
    for p in parents:
        hit.add(f"parent:{p}")

    return sorted(hit)


def detect_conflations(entities: List[Dict]) -> List[Dict]:
    flagged = []
    for e in entities:
        forms = [e.get("name", "")] + list(e.get("all_forms", []))
        forms = [f for f in forms if f]
        groups = incompatible_markers(forms)

        # split into curated-family variants and patronymics
        fam_variants = {}   # family -> set(variant)
        parents = set()
        for g in groups:
            if g.startswith("parent:"):
                parents.add(g)
            elif "_" in g:
                fam, var = g.split("_", 1)
                fam_variants.setdefault(fam, set()).add(var)

        # conflation iff a curated distinct-being FAMILY has >=2 variants
        # (rama: dasharatha+parashurama+balarama = 3 beings collapsed).
        #
        # NOTE: the bare-patronym pair rule was REMOVED — it false-fired on every
        # hero with a divine father + mortal mother (Karna: Surya+Adhiratha+Radha;
        # Arjuna: Indra+Kunti). Multiple parents ≠ multiple beings. Sanskrit dialogue
        # pronouns (mama/tava/me) also leaked in as fake patronyms. The curated
        # family-variant signal is the reliable one; `parents` stays in `groups`
        # for human inspection but no longer triggers a flag.
        multi_variant_family = any(len(v) >= 2 for v in fam_variants.values())
        is_conflated = multi_variant_family
        if is_conflated:
            flagged.append({
                "id": e["id"], "name": e.get("name", ""),
                "groups": sorted(set(groups)),
                "forms": forms[:20],
            })
    return flagged


def run(manifest_path: str = "") -> Dict[str, Any]:
    manifest_path = manifest_path or os.path.abspath(_MANIFEST)
    metadata = {"manifest_path": manifest_path}
    if not os.path.isfile(manifest_path):
        return _envelope(False, None, metadata,
                         [{"code": "missing_manifest", "message": f"not found: {manifest_path}"}])
    with open(manifest_path) as f:
        g = json.load(f)
    entities = g.get("entities", [])
    flagged = detect_conflations(entities)
    data = {
        "n_entities": len(entities),
        "n_conflated": len(flagged),
        "conflations": flagged,
    }
    return _envelope(True, data, metadata, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    env = run()
    if as_json:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}")
            return 2
        d = env["data"]
        print(f"=== ENTITY CONFLATION SCAN ===")
        print(f"Entities: {d['n_entities']:,}  |  CONFLATED nodes: {d['n_conflated']}")
        for c in d["conflations"]:
            print(f"\n  ! {c['id']} (name={c['name']})")
            print(f"    distinct-being groups: {c['groups']}")
            print(f"    forms: {c['forms'][:10]}")
    return 1 if env["success"] and env["data"]["n_conflated"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
