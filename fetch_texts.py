"""
PuranGPT — Fast Text Downloader
Downloads Puranic texts from archive.org (most reliable public source).
Runs in background while the website is live.
"""
import os, sys, time, json, requests, hashlib
from pathlib import Path

OUTPUT = Path("data/raw_pdfs")
STATE_FILE = Path("data/.download_state.json")

HEADERS = {
    "User-Agent": "PuranGPT-Academic/1.0 (purangpt educational project)"
}

# Archive.org links — these are stable, public domain texts
TEXTS = [
    # 18 Mahapuranas
    ("bhagavata",      "Bhagavata Purana",       "https://archive.org/download/bhagavata-purana-all-12-scandhas-hindi/Srimad%20Bhagavata%20Purana%20with%20Sarartha%20Darsini%20Hindi%20Tikka%20Skandha%201-4.pdf"),
    ("vishnu",         "Vishnu Purana",           "https://archive.org/download/VishnuPuranaHindi/Vishnu%20Purana%20Hindi.pdf"),
    ("shiva",          "Shiva Purana",            "https://archive.org/download/ShivaPuranaHindi/Shiva%20Purana%20Hindi.pdf"),
    ("garuda",         "Garuda Purana",           "https://archive.org/download/GarudaPurana_Hindi/Garuda%20Purana%20Hindi.pdf"),
    ("agni",           "Agni Purana",             "https://archive.org/download/AgniPuranaHindi/Agni%20Purana%20Hindi.pdf"),
    ("markandeya",     "Markandeya Purana",       "https://archive.org/download/MarkandeyaPurana_Hindi/Markandeya%20Purana%20Hindi.pdf"),
    ("brahma",         "Brahma Purana",           "https://archive.org/download/BrahmaPurana_Hindi/Brahma%20Purana%20Hindi.pdf"),
    ("bhavishya",      "Bhavishya Purana",        "https://archive.org/download/bhavishya-puran-hindi/bhavishya%20puran%20hindi.pdf"),
    ("matsya",         "Matsya Purana",           "https://archive.org/download/matsya-purana-hindi/Matsya%20Purana%20Hindi.pdf"),
    ("kurma",          "Kurma Purana",            "https://archive.org/download/KurmaPurana_Hindi/Kurma%20Purana%20Hindi.pdf"),
    ("padma",          "Padma Purana",            "https://archive.org/download/PadmaPurana_Hindi/Padma%20Purana%20Hindi.pdf"),
    ("narada",         "Narada Purana",           "https://archive.org/download/NaradPurana_Hindi/Narad%20Purana%20Hindi.pdf"),
    ("linga",          "Linga Purana",            "https://archive.org/download/LingaPurana_Hindi/Linga%20Purana%20Hindi.pdf"),
    ("vamana",         "Vamana Purana",           "https://archive.org/download/VamanaPurana_Hindi/Vamana%20Purana%20Hindi.pdf"),
    ("varaha",         "Varaha Purana",           "https://archive.org/download/VarahaPurana_Hindi/Varaha%20Purana%20Hindi.pdf"),
    ("brahmanda",      "Brahmanda Purana",        "https://archive.org/download/BrahmandaPurana_Hindi/Brahmanda%20Purana%20Hindi.pdf"),
    ("brahma_vaivarta","Brahma Vaivarta Purana",  "https://archive.org/download/BrahmaVaivartaPurana_Hindi/Brahma%20Vaivarta%20Purana%20Hindi.pdf"),
    ("skanda",         "Skanda Purana",           "https://archive.org/download/SkandaPurana_Hindi/Skanda%20Purana%20Hindi%20Vol%201.pdf"),
    # Epics & Key Texts  
    ("bhagavad_gita",  "Bhagavad Gita",           "https://archive.org/download/BhagavadGitaHindi/Bhagavad%20Gita%20Hindi.pdf"),
    ("ramayana",       "Valmiki Ramayana",        "https://archive.org/download/ValmikiRamayana_Hindi/Valmiki%20Ramayana%20Hindi.pdf"),
    ("mahabharata",    "Mahabharata",             "https://archive.org/download/MahabharataHindi/Mahabharata%20Hindi.pdf"),
    ("yoga_sutras",    "Yoga Sutras of Patanjali","https://archive.org/download/yoga-sutras-of-patanjali/Yoga%20Sutras%20of%20Patanjali.pdf"),
    ("hatha_yoga",     "Hatha Yoga Pradipika",    "https://archive.org/download/HathaYogaPradipika/Hatha%20Yoga%20Pradipika.pdf"),
    ("upanishads",     "108 Upanishads",          "https://archive.org/download/108upanishads/108%20Upanishads%20Hindi.pdf"),
]

# Fallback to vedpuran.net direct download pattern
VEDPURAN_FALLBACKS = {
    "bhagavata":      "https://vedpuran.net/download/bhagwat-puran.pdf",
    "vishnu":         "https://vedpuran.net/download/vishnu-puran.pdf",
    "shiva":          "https://vedpuran.net/download/shiv-puran.pdf",
    "garuda":         "https://vedpuran.net/download/garud-puran.pdf",
    "agni":           "https://vedpuran.net/download/agni-puran.pdf",
    "markandeya":     "https://vedpuran.net/download/markandey-puran.pdf",
    "brahma":         "https://vedpuran.net/download/brahma-puran.pdf",
    "bhavishya":      "https://vedpuran.net/download/bhavishya-puran.pdf",
    "matsya":         "https://vedpuran.net/download/matsya-puran.pdf",
    "kurma":          "https://vedpuran.net/download/kurma-puran.pdf",
    "padma":          "https://vedpuran.net/download/padma-puran.pdf",
    "narada":         "https://vedpuran.net/download/narad-puran.pdf",
    "linga":          "https://vedpuran.net/download/ling-puran.pdf",
    "vamana":         "https://vedpuran.net/download/vaman-puran.pdf",
    "varaha":         "https://vedpuran.net/download/varah-puran.pdf",
    "brahmanda":      "https://vedpuran.net/download/brahmand-puran.pdf",
    "brahma_vaivarta":"https://vedpuran.net/download/brahma-vaivarta-puran.pdf",
    "skanda":         "https://vedpuran.net/download/skand-puran.pdf",
    "bhagavad_gita":  "https://vedpuran.net/download/bhagwat-geeta.pdf",
}

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def download_one(text_id, name, url, state):
    dest_dir = OUTPUT / text_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{text_id}.pdf"

    if dest_path.exists() and dest_path.stat().st_size > 50_000:
        print(f"  ⏭  {name} — already downloaded ({dest_path.stat().st_size // 1024} KB)")
        state[text_id] = "ok"
        return True

    urls_to_try = [url]
    if text_id in VEDPURAN_FALLBACKS:
        urls_to_try.append(VEDPURAN_FALLBACKS[text_id])

    for attempt_url in urls_to_try:
        try:
            print(f"  ↓  {name}  →  {attempt_url[:70]}…", flush=True)
            resp = requests.get(attempt_url, headers=HEADERS, stream=True, timeout=60, allow_redirects=True)
            if resp.status_code == 404:
                print(f"     404 Not Found — trying next URL")
                continue
            resp.raise_for_status()

            ct = resp.headers.get("content-type", "")
            if "html" in ct.lower():
                print(f"     Got HTML instead of PDF — trying next URL")
                continue

            with open(dest_path, "wb") as f:
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (512 * 1024) == 0:
                            print(f"     {downloaded // 1024} KB…", flush=True)

            # Verify PDF magic bytes
            with open(dest_path, "rb") as f:
                header = f.read(4)
            if header != b"%PDF":
                print(f"     Not a valid PDF — trying next URL")
                dest_path.unlink(missing_ok=True)
                continue

            size_kb = dest_path.stat().st_size // 1024
            print(f"  ✓  {name} — {size_kb} KB saved")
            state[text_id] = "ok"

            # Save metadata
            meta = {"id": text_id, "name": name, "url": attempt_url, "size_kb": size_kb}
            (dest_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
            return True

        except requests.exceptions.ConnectionError as e:
            print(f"     Connection error: {e}")
        except requests.exceptions.Timeout:
            print(f"     Timeout — trying next URL")
        except requests.exceptions.HTTPError as e:
            print(f"     HTTP {e.response.status_code} — trying next URL")
        except Exception as e:
            print(f"     Error: {e}")
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)

    print(f"  ✗  {name} — all URLs failed")
    state[text_id] = "failed"
    return False

def main():
    print("\n🕉️  PuranGPT — Downloading Sacred Texts")
    print("=" * 55)
    print(f"Output: {OUTPUT.resolve()}\n")
    OUTPUT.mkdir(parents=True, exist_ok=True)

    state = load_state()
    ok = skipped = failed = 0

    for i, (text_id, name, url) in enumerate(TEXTS, 1):
        print(f"\n[{i}/{len(TEXTS)}] {name}")
        result = download_one(text_id, name, url, state)
        save_state(state)
        if state.get(text_id) == "ok":
            ok += 1
        elif state.get(text_id) == "failed":
            failed += 1
        time.sleep(2.0)  # Be respectful — 2s delay between downloads

    print(f"\n{'='*55}")
    print(f"✓ Downloaded: {ok}")
    print(f"✗ Failed:     {failed}")
    print(f"\nNext step: python fetch_and_index.py")

if __name__ == "__main__":
    main()
