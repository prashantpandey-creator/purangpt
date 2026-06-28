"""
PuranGPT — GRETIL Scholarly Text Downloader
=============================================
Downloads plain-text Sanskrit from GRETIL (University of Göttingen).
These are the MOST NEUTRAL sources available — input from critical
editions by academic scholars with no sectarian agenda.

URL pattern: https://gretil.sub.uni-goettingen.de/gretil/corpustei/
             transformations/plaintext/sa_<name>.txt

Bias assessment based on:
  - Ludo Rocher, "The Puranas" (1986)
  - R.C. Hazra, "Studies in the Puranic Records" (1940)
  - Wendy Doniger, "The Hindus: An Alternative History" (2009)
"""

import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://gretil.sub.uni-goettingen.de/gretil/corpustei/transformations/plaintext/"
OUTPUT   = Path("data/raw_texts/gretil")
HEADERS  = {"User-Agent": "PuranGPT-Academic/1.0 (scholarly Sanskrit corpus)"}
DELAY    = 2.0

OUTPUT.mkdir(parents=True, exist_ok=True)

# ── Verified GRETIL Plain-Text URLs ───────────────────────────────────────
GRETIL_TEXTS = [
    # ── 18 Mahapuranas ──────────────────────────────────────────────────────
    {
        "id":        "agni",
        "name":      "Agni Purana",
        "file":      "sa_agnipurANa.txt",
        "tradition": "mixed",
        "edition":   "Bibliotheca Indica (BI) ed., input by Jun Takashima et al.",
        "bias":      "✅ NEUTRAL — encyclopedic, covers all traditions equally",
        "notes":     "One of the most encyclopedic Puranas; covers Shaiva, Vaishnava, and Shakta equally.",
    },
    {
        "id":        "bhagavata",
        "name":      "Bhagavata Purana",
        "file":      "sa_bhAgavatapurANa.txt",
        "tradition": "vaishnava",
        "edition":   "Critical edition basis",
        "bias":      "⚠️ VAISHNAVA — inherently Vaishnava text; Book 1 Ch.1 superiority claim is a late addition per Rocher (1986)",
        "notes":     "The Bhagavata IS the great Vaishnava Purana. GRETIL gives you the Sanskrit without Gaudiya commentary.",
    },
    {
        "id":        "brahma",
        "name":      "Brahma Purana",
        "file":      "sa_brahmapurANa-1-246.txt",
        "tradition": "mixed",
        "edition":   "Anandasrama Sanskrit Series, input by Peter Schreiner & Renate Söhnen-Thieme",
        "bias":      "✅ MOSTLY NEUTRAL — some passages demoting Shiva flagged by Hazra as redactions",
        "notes":     "Covers all major creation stories neutrally.",
    },
    {
        "id":        "brahmanda",
        "name":      "Brahmanda Purana",
        "file":      "sa_brahmANDapurANa.txt",
        "tradition": "mixed",
        "edition":   "Input by Sansknet Project",
        "bias":      "✅ NEUTRAL — one of the older, less interpolated Puranas per Hazra",
        "notes":     "Contains Lalita Sahasranama (Shakta) — shows its multi-traditional character.",
    },
    {
        "id":        "garuda",
        "name":      "Garuda Purana",
        "file":      "sa_garuDapurANa.txt",
        "tradition": "vaishnava",
        "edition":   "Input by Sansknet Project",
        "bias":      "⚠️ VAISHNAVA — but Preta Khanda (death/afterlife) is widely considered authentic and pre-sectarian",
        "notes":     "The afterlife/karma sections are cited across all traditions.",
    },
    {
        "id":        "kurma",
        "name":      "Kurma Purana",
        "file":      "sa_kUrmapurANa.txt",
        "tradition": "shaiva-vaishnava",
        "edition":   "All-India Kashiraj Trust edition",
        "bias":      "✅ INTERESTING MIX — Vishnu narrates to Shiva devotees. Contains Ishvara Gita (Shaiva parallel to Bhagavad Gita).",
        "notes":     "Rare text where both traditions are genuinely present.",
    },
    {
        "id":        "linga_1",
        "name":      "Linga Purana (Part 1, Ch. 1-108)",
        "file":      "sa_liGgapurANa1-108.txt",
        "tradition": "shaiva",
        "edition":   "Venkatesvara Steam Press 1906, input by Sansknet Project",
        "bias":      "✅ SHAIVA — Shiva as Brahman. Reliable for Shaiva theology; counterbalances Vaishnava Puranas.",
        "notes":     "Primary Shaiva Mahapurana. GRETIL edition well-regarded by Indologists.",
    },
    {
        "id":        "linga_2",
        "name":      "Linga Purana (Part 2)",
        "file":      "sa_liGgapurANa2.txt",
        "tradition": "shaiva",
        "edition":   "Venkatesvara Steam Press, input by Sansknet Project",
        "bias":      "✅ SHAIVA — continuation of Part 1",
        "notes":     "Contains Shiva cosmology and Shaiva dharma.",
    },
    {
        "id":        "markandeya",
        "name":      "Markandeya Purana",
        "file":      "sa_mArkaNDeyapurANa1-93.txt",
        "tradition": "shakta",
        "edition":   "Input by Sansknet Project",
        "bias":      "✅ SHAKTA — Contains Devi Mahatmya (Durga Saptashati). One of the most TEXTUALLY STABLE Puranas.",
        "notes":     "Scholars consider this one of the most reliably transmitted Puranas. Essential Shakta source.",
    },
    {
        "id":        "matsya",
        "name":      "Matsya Purana (Ch. 1-176)",
        "file":      "sa_matsyapurANa1-176.txt",
        "tradition": "mixed",
        "edition":   "Input by Oliver Hellwig",
        "bias":      "✅ NEUTRAL — ancient text, less sectarian than most. Excellent cosmological content.",
        "notes":     "Ancient text; contains Manu's flood narrative. Less interpolated than many.",
    },
    {
        "id":        "narada",
        "name":      "Narada Purana",
        "file":      "sa_nAradapurANa.txt",
        "tradition": "vaishnava",
        "edition":   "Input by Sansknet Project",
        "bias":      "⚠️ STRONG VAISHNAVA — late Bhakti-oriented composition",
        "notes":     "Useful for Vaishnava perspective but should be read knowing its sectarian character.",
    },
    {
        "id":        "shiva_1_7",
        "name":      "Shiva Purana (Books 1 and 7)",
        "file":      "sa_zivapurANabooks-1-and-7.txt",
        "tradition": "shaiva",
        "edition":   "Input by Jun Takashima et al.",
        "bias":      "✅ SHAIVA — primary Shaiva Mahapurana. GRETIL is the best available neutral Sanskrit edition.",
        "notes":     "Essential for Shaiva theology; counterpart to the Bhagavata for Vaishnavism.",
    },
    {
        "id":        "skanda_1_31",
        "name":      "Skanda Purana (Ch. 1-31)",
        "file":      "sa_skandapurANa1-31.txt",
        "tradition": "mixed",
        "edition":   "Critical edition, R. Adriaensen, H.T. Bakker & H. Isaacson",
        "bias":      "⚠️ COMPLEX — 7 Khandas from different traditions; tirtha-mahatmyas locally inserted",
        "notes":     "Most textually complex Purana. This is the critical Bakker-Isaacson edition — most reliable part.",
    },
    {
        "id":        "vamana",
        "name":      "Vamana Purana",
        "file":      "sa_vAmanapurANa1-69.txt",
        "tradition": "vaishnava",
        "edition":   "Input by Sansknet Project",
        "bias":      "⚠️ VAISHNAVA — but contains significant Shaiva sections; interesting syncretic text",
        "notes":     "Despite Vaishnava framing, contains substantial Shaiva-Vaishnava synthesis material.",
    },
    {
        "id":        "vishnu_critical",
        "name":      "Vishnu Purana (Critical Edition)",
        "file":      "sa_viSNupurANa-crit.txt",
        "tradition": "vaishnava",
        "edition":   "Critical edition, input by Peter Schreiner",
        "bias":      "⚠️ VAISHNAVA — but this is the CRITICAL EDITION (most reliable text-critically)",
        "notes":     "Peter Schreiner's critical edition is the scholarly standard. H.H. Wilson's 1840 translation is also reliable.",
    },
    # ── Vedic Samhitas ────────────────────────────────────────────────────────
    {
        "id":        "rigveda",
        "name":      "Rigveda (Aufrecht ed.)",
        "file":      "sa_Rgveda-edAufrecht.txt",
        "tradition": "vedic",
        "edition":   "Aufrecht edition",
        "bias":      "✅ PRE-SECTARIAN VEDIC — the foundation of all Hindu texts",
        "notes":     "1,028 hymns. Grounding source for all Vedic deities.",
    },
    {
        "id":        "samaveda",
        "name":      "Samaveda Samhita",
        "file":      "sa_sAmavedasaMhitA.txt",
        "tradition": "vedic",
        "edition":   "Input by Anshuman Pandey",
        "bias":      "✅ PRE-SECTARIAN VEDIC — liturgical Veda",
        "notes":     "Chants based largely on Rigveda.",
    },
    {
        "id":        "atharvaveda",
        "name":      "Atharvaveda (Paippalada)",
        "file":      "sa_paippalAdasaMhitA.txt",
        "tradition": "vedic",
        "edition":   "Paippalada recension",
        "bias":      "✅ PRE-SECTARIAN VEDIC",
        "notes":     "Daily life, healing, spells.",
    },
    # ── Brahmanas ────────────────────────────────────────────────────────────
    {
        "id":        "gopatha",
        "name":      "Gopatha Brahmana",
        "file":      "sa_gopathabrAhmaNa.txt",
        "tradition": "vedic",
        "edition":   "Input by Arlo Griffiths",
        "bias":      "✅ PRE-SECTARIAN VEDIC — ritual exegesis",
        "notes":     "Commentary on Atharvaveda.",
    },
    {
        "id":        "kaushitaki",
        "name":      "Kaushitaki Brahmana",
        "file":      "sa_kauSItakibrAhmaNa.txt",
        "tradition": "vedic",
        "edition":   "Input by Muneo Tokunaga",
        "bias":      "✅ PRE-SECTARIAN VEDIC",
        "notes":     "Commentary on Rigveda.",
    },
    # ── Upanishads (10 Principal + more) ──────────────────────────────────────
    {
        "id":        "isha",
        "name":      "Isha Upanishad (with Shankara Bhashya)",
        "file":      "sa_IzopaniSad-or-IzAvAsyopaniSadkANva-recension-comm.txt",
        "tradition": "vedanta",
        "edition":   "Sansknet",
        "bias":      "✅ NEUTRAL TEXT — Advaita lens in commentary",
        "notes":     "Core Vedanta.",
    },
    {
        "id":        "aitareya",
        "name":      "Aitareya Upanishad (with Shankara Bhashya)",
        "file":      "sa_aitareyopaniSad-comm.txt",
        "tradition": "vedanta",
        "edition":   "Sansknet",
        "bias":      "✅ NEUTRAL TEXT — Advaita lens in commentary",
        "notes":     "Consciousness theory.",
    },
    {
        "id":        "taittiriya",
        "name":      "Taittiriya Upanishad (with Shankara Bhashya)",
        "file":      "sa_taittirIyopaniSad-zaMkarabhASya.txt",
        "tradition": "vedanta",
        "edition":   "Input by Ivan Andrijanic",
        "bias":      "✅ NEUTRAL TEXT — Advaita lens in commentary",
        "notes":     "Annamaya-Anandamaya koshas.",
    },
    {
        "id":        "mandukya",
        "name":      "Mandukya Upanishad (with Gaudapada Karika)",
        "file":      "sa_mANDUkyopaniSad-comm.txt",
        "tradition": "vedanta",
        "edition":   "Sansknet",
        "bias":      "✅ NEUTRAL TEXT — Advaita lens in commentary/karika",
        "notes":     "AUM, four states of consciousness.",
    },
    {
        "id":        "prasna",
        "name":      "Prasna Upanishad (with Shankara Bhashya)",
        "file":      "sa_praznopaniSad-comm.txt",
        "tradition": "vedanta",
        "edition":   "Sansknet",
        "bias":      "✅ NEUTRAL TEXT — Advaita lens in commentary",
        "notes":     "Prana, creation.",
    },
    {
        "id":        "svetasvatara",
        "name":      "Svetasvatara Upanishad",
        "file":      "sa_zvetAzvataropaniSad.txt",
        "tradition": "shaiva",
        "edition":   "Standard edition",
        "bias":      "✅ SHAIVA / THEISTIC — early Shaiva philosophy",
        "notes":     "Important early theistic Upanishad.",
    },
    {
        "id":        "brihadaranyaka",
        "name":      "Brihadaranyaka Upanishad",
        "file":      "sa_bRhadAraNyakopaniSad.txt",
        "tradition": "vedic",
        "edition":   "Standard edition with Shankara's commentary",
        "bias":      "✅ PRE-SECTARIAN VEDIC — predates all Puranic sectarianism.",
        "notes":     "One of the oldest and most important Upanishads.",
    },
    {
        "id":        "chandogya",
        "name":      "Chandogya Upanishad",
        "file":      "sa_chAndogyopaniSad.txt",
        "tradition": "vedic",
        "edition":   "Standard edition",
        "bias":      "✅ PRE-SECTARIAN VEDIC — contains 'Tat tvam asi'.",
        "notes":     "Core Upanishad; pre-dates all sectarian divisions.",
    },
    {
        "id":        "katha",
        "name":      "Katha Upanishad",
        "file":      "sa_kaThopaniSad.txt",
        "tradition": "vedic",
        "edition":   "Standard edition",
        "bias":      "✅ PRE-SECTARIAN VEDIC — death and Atman teaching",
        "notes":     "Nachiketa's dialogue with Yama. Pre-sectarian.",
    },
    # ── Epics ────────────────────────────────────────────────────────────────
    {
        "id":        "gita",
        "name":      "Bhagavad Gita (with Shankara Bhashya)",
        "file":      "sa_bhagavadgItA-comm.txt",
        "tradition": "vaishnava",
        "edition":   "Standard edition",
        "bias":      "⚠️ VAISHNAVA — Krishna as Supreme, but universal appeal.",
        "notes":     "The most widely read Hindu scripture.",
    },
    {
        "id":        "mahabharata",
        "name":      "Mahabharata",
        "file":      "sa_mahAbhArata.txt",
        "tradition": "mixed",
        "edition":   "Poona Critical Edition",
        "bias":      "✅ NEUTRAL — encyclopedic epic",
        "notes":     "The Great Epic.",
    },
    {
        "id":        "ramayana",
        "name":      "Ramayana (Valmiki)",
        "file":      "sa_rAmAyaNa.txt",
        "tradition": "vaishnava",
        "edition":   "Standard edition",
        "bias":      "⚠️ VAISHNAVA — Rama as avatar",
        "notes":     "The Adi-Kavya (first poem).",
    },
    {
        "id":        "harivamsha",
        "name":      "Harivamsha",
        "file":      "sa_harivaGza.txt",
        "tradition": "vaishnava",
        "edition":   "Standard edition",
        "bias":      "⚠️ VAISHNAVA — focuses on Krishna's life",
        "notes":     "Appendix to the Mahabharata.",
    },
    # ── Dharmashastra & Arthashastra ─────────────────────────────────────────
    {
        "id":        "manusmriti",
        "name":      "Manusmriti",
        "file":      "sa_manusmRti.txt",
        "tradition": "dharma",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — foundational law text",
        "notes":     "Most famous Dharmashastra.",
    },
    {
        "id":        "arthashastra",
        "name":      "Arthashastra (Kautilya)",
        "file":      "sa_kauTilIyaarthazAstra.txt",
        "tradition": "niti",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — political science",
        "notes":     "Ancient Indian treatise on statecraft.",
    },
    {
        "id":        "apastamba",
        "name":      "Apastamba Dharmasutra",
        "file":      "sa_ApastambadharmasUtra.txt",
        "tradition": "dharma",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — ancient law text",
        "notes":     "One of the oldest surviving Dharmasutras.",
    },
    # ── Grammar & Lexicography ───────────────────────────────────────────────
    {
        "id":        "ashtadhyayi",
        "name":      "Ashtadhyayi (Panini)",
        "file":      "sa_pANini-aSTAdhyAyI.txt",
        "tradition": "vyakarana",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — grammar",
        "notes":     "The foundational text of Sanskrit grammar.",
    },
    {
        "id":        "vakyapadiya",
        "name":      "Vakyapadiya (Bhartrhari)",
        "file":      "sa_vAkyapadIya.txt",
        "tradition": "vyakarana",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — philosophy of language",
        "notes":     "Important for understanding meaning (sphota).",
    },
    {
        "id":        "amarakosha",
        "name":      "Amarakosha",
        "file":      "sa_amarasiMha-nAmaliGgAnuzAsana.txt",
        "tradition": "kosha",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — lexicon",
        "notes":     "Classical Sanskrit thesaurus.",
    },
    # ── Darshana (Philosophy) ────────────────────────────────────────────────
    {
        "id":        "brahmasutras",
        "name":      "Brahma Sutras (with Shankara Bhashya)",
        "file":      "sa_brahmAsUtra-comm.txt",
        "tradition": "vedanta",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL TEXT — Advaita lens in commentary",
        "notes":     "Foundation of Vedanta philosophy.",
    },
    {
        "id":        "nyayasutras",
        "name":      "Nyaya Sutras",
        "file":      "sa_nyAyasUtra.txt",
        "tradition": "nyaya",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — logic",
        "notes":     "Foundational text of Nyaya darshana.",
    },
    {
        "id":        "vaisheshika",
        "name":      "Vaisheshika Sutras",
        "file":      "sa_vaizeSikasUtra.txt",
        "tradition": "vaisheshika",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — ontology",
        "notes":     "Foundational text of Vaisheshika darshana.",
    },
    # ── Yogic Texts & Nath Sampradaya ──────────────────────────────────────────
    {
        "id":        "yoga_sutras",
        "name":      "Yoga Sutras of Patanjali",
        "file":      "sa_yogasUtra-vRttiH.txt",
        "tradition": "neutral-darshana",
        "edition":   "Standard Sanskrit edition",
        "bias":      "✅ PRE-SECTARIAN — Yoga Darshana predates Vaishnava/Shaiva splits.",
        "notes":     "The Yoga Sutras are non-sectarian.",
    },
    {
        "id":        "hatha_yoga_pradipika",
        "name":      "Hatha Yoga Pradipika",
        "file":      "sa_haThayogapradIpikA.txt",
        "tradition": "nath-sampradaya",
        "edition":   "Standard Sanskrit edition",
        "bias":      "✅ YOGIC / NATH — Foundation of physical yoga.",
        "notes":     "Core text of the Nath tradition.",
    },
    {
        "id":        "shiva_samhita",
        "name":      "Shiva Samhita",
        "file":      "sa_zivasaMhitA.txt",
        "tradition": "nath-sampradaya",
        "edition":   "Standard Sanskrit edition",
        "bias":      "✅ YOGIC / TANTRIC — Advanced yogic physiology.",
        "notes":     "Shiva teaching Parvati the secrets of yoga.",
    },
    {
        "id":        "gheranda_samhita",
        "name":      "Gheranda Samhita",
        "file":      "sa_gheraNDasaMhitA.txt",
        "tradition": "nath-sampradaya",
        "edition":   "Standard Sanskrit edition",
        "bias":      "✅ YOGIC — Saptanga (seven-limbed) yoga.",
        "notes":     "Encyclopedic manual of Hatha yoga.",
    },
    {
        "id":        "goraksha_shataka",
        "name":      "Goraksha Shataka",
        "file":      "sa_gorakSazataka.txt",
        "tradition": "nath-sampradaya",
        "edition":   "Standard Sanskrit edition",
        "bias":      "✅ NATH — Attributed to Gorakhnath.",
        "notes":     "Direct teachings of the Gorakhnath tradition.",
    },
    {
        # The Mokṣopāya IS the (older, critical-edition) Yogavāsiṣṭha. This GRETIL
        # plaintext REPLACES a corrupt saved archive.org details webpage that had
        # been ingested by mistake (incident 2026-06-28). Markers: MU_<prak>,<ch>.<v>.
        "id":        "yoga_vasistha",
        "name":      "Yoga Vasistha",
        "file":      "sa_mokSopAya.txt",
        "tradition": "other",
        "edition":   "Mokṣopāya — Historisch-kritische Gesamtausgabe (Slaje, Hanneder, Krause-Stinner et al.)",
        "bias":      "✅ non-sectarian — Advaita idealism; the Rāma–Vasiṣṭha dialogue.",
        "notes":     "Older Kashmiri critical recension of the Yogavāsiṣṭha; all six prakaraṇas.",
    },
    # ── Remaining Darshanas ────────────────────────────────────────────────
    {
        "id":        "samkhya_karika",
        "name":      "Samkhya Karika (Ishvarakrishna)",
        "file":      "sa_sAMkhyakArikA.txt",
        "tradition": "samkhya",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — Foundational dualist cosmology.",
        "notes":     "Essential for understanding Puranic creation myths.",
    },
    {
        "id":        "mimamsa_sutras",
        "name":      "Purva Mimamsa Sutras",
        "file":      "sa_mImAMsAsUtra.txt",
        "tradition": "mimamsa",
        "edition":   "Standard edition",
        "bias":      "✅ NEUTRAL — Vedic ritual exegesis.",
        "notes":     "The science of interpreting Vedic rituals.",
    },
]


def download_text(entry: dict) -> bool:
    """Download a single GRETIL plaintext file."""
    text_id   = entry["id"]
    name      = entry["name"]
    file_name = entry["file"]
    url       = BASE + file_name

    dest_dir  = OUTPUT / text_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / file_name

    # Resume support
    if dest_file.exists() and dest_file.stat().st_size > 10_000:
        print(f"  ⏭  Already downloaded ({dest_file.stat().st_size:,} bytes)")
        return True

    print(f"  ↓  {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 404:
            print(f"  ✗  404 — file not on GRETIL server")
            return False
        resp.raise_for_status()

        dest_file.write_bytes(resp.content)

        # Save provenance metadata
        meta = {
            **entry,
            "url":          url,
            "local_file":   str(dest_file),
            "size_bytes":   len(resp.content),
            "lines":        resp.text.count("\n"),
            "source":       "GRETIL — University of Göttingen",
            "scholarly_tier": "TIER_1_MOST_NEUTRAL",
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (dest_dir / "provenance.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"  ✓  {len(resp.content):,} bytes — {resp.text.count(chr(10)):,} lines")
        return True

    except requests.exceptions.Timeout:
        print("  ✗  Timeout")
    except Exception as e:
        print(f"  ✗  {e}")
    return False


def main():
    print("\n🕉️  PuranGPT — GRETIL Scholarly Sanskrit Downloader")
    print("=" * 60)
    print("Source: University of Göttingen — gretil.sub.uni-goettingen.de")
    print("Format: Plain UTF-8 Sanskrit (IAST transliteration)")
    print("Bias:   MINIMAL — critical editions, zero devotional commentary")
    print(f"Output: {OUTPUT.resolve()}\n")

    ok = failed = skipped = 0
    bias_alerts = []

    for i, entry in enumerate(GRETIL_TEXTS, 1):
        print(f"\n[{i}/{len(GRETIL_TEXTS)}] {entry['name']}")
        print(f"  Tradition: {entry['tradition']}")
        print(f"  Bias:      {entry['bias']}")

        if entry["bias"].startswith("⚠️"):
            bias_alerts.append(entry["name"])

        result = download_text(entry)
        if result:
            ok += 1
        else:
            failed += 1
        time.sleep(DELAY)

    print(f"\n{'=' * 60}")
    print(f"✓ Downloaded: {ok}")
    print(f"✗ Failed:     {failed}")

    if bias_alerts:
        print(f"\n⚠️  Sectarian bias noted in these texts (still use them")
        print(f"    but PuranGPT will flag them in responses):")
        for name in bias_alerts:
            print(f"  • {name}")

    print(f"\n📖 Source provenance saved in each text directory.")
    print(f"   Next: python extract_and_index.py")


if __name__ == "__main__":
    main()
