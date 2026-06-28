import os
import urllib.request
import re
from pathlib import Path

OUTPUT_DIR = Path("data/raw_texts/gretil")

TEXTS = [
    {
        "id": "mahabharata",
        "url": "https://raw.githubusercontent.com/INDOLOGY/GRETIL-mirror/master/gretil.sub.uni-goettingen.de/gretil/1_sanskr/2_epic/mbh/sas/mahabharata.htm",
        "format": "htm"
    },
    {
        "id": "nyayasutras",
        "url": "https://raw.githubusercontent.com/INDOLOGY/GRETIL-mirror/master/gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/3_phil/nyaya/gaunys_u.htm",
        "format": "htm"
    },
    {
        "id": "vaisheshika",
        "url": "https://raw.githubusercontent.com/INDOLOGY/GRETIL-mirror/master/gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/3_phil/vaisesik/vaisessu.htm",
        "format": "htm"
    },
    {
        "id": "mimamsa_sutras",
        "url": "https://raw.githubusercontent.com/INDOLOGY/GRETIL-mirror/master/gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/3_phil/mimamsa/mimslovu.htm",
        "format": "htm"
    },
    # yoga_vasistha is now sourced authoritatively from GRETIL (the Mokṣopāya
    # critical edition, sa_mokSopAya.txt) via fetch_gretil.py — see provenance at
    # data/raw_texts/gretil/yoga_vasistha/provenance.json. The former
    # sanskritdocuments.org .itx entry was removed (incident 2026-06-28: a corrupt
    # archive.org HTML page had been ingested; do NOT re-add an ad-hoc source here).
]

def clean_html(raw_html):
    # Remove HTML tags
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def download_texts():
    for text in TEXTS:
        print(f"Downloading {text['id']}...")
        dest_dir = OUTPUT_DIR / text["id"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{text['id']}.txt"
        
        try:
            req = urllib.request.Request(text["url"], headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8', errors='ignore')
                
                if text["format"] == "htm":
                    content = clean_html(content)
                
                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write(content)
            print(f"  ✓ Saved to {dest_file} ({len(content)} chars)")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

if __name__ == "__main__":
    download_texts()
