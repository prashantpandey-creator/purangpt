"""Harvest the Varaha Purana (Sanskrit) from Sanskrit Wikisource.

Unlike Bhavishya (fragmentary), वराहपुराणम् on Sanskrit Wikisource is NEARLY
COMPLETE — ~237 cleanly-named flat chapters (वराहपुराणम्/अध्यायः NNN; the Varaha
has ~217 adhyayas). GRETIL & sanskritdocuments lack it; the old corpus source was
catastrophically font-garbled Hindi OCR (varaha_purana_hindi.txt).

Pipeline: enumerate अध्यायः subpages → POST-batched content (redirects=1) → strip
wiki+HTML markup → convert the native ।। C.V ।। verse refs into zero-padded
prefixed markers  vrh_<chapter:03d>.<verse:03d>  (≥10 chars → all survive
index_gretil danda-chunking) → emit one GRETIL-shaped raw file (# Text marker),
ordered by chapter. Output is VERIFIED by tools.source_reality_check (the gate).
"""
import re
import sys
import time
import requests

API = "https://sa.wikisource.org/w/api.php"
HEADERS = {"User-Agent": "PuranGPT-Academic/1.0 (scholarly Sanskrit corpus)"}
PREFIX = "वराहपुराणम्/"
DEVA_DIG = str.maketrans("०१२३४५६७८९", "0123456789")


def all_titles():
    titles, cont = [], None
    while True:
        p = {"action": "query", "list": "allpages", "apprefix": PREFIX,
             "aplimit": "500", "format": "json"}
        if cont:
            p["apcontinue"] = cont
        r = requests.get(API, params=p, headers=HEADERS, timeout=30).json()
        titles += [a["title"] for a in r["query"]["allpages"]]
        if "continue" in r:
            cont = r["continue"]["apcontinue"]
        else:
            break
    return titles


def _fetch_batch(batch):
    """POST one batch; return parsed JSON or None after retries."""
    p = {"action": "query", "prop": "revisions", "rvprop": "content",
         "rvslots": "main", "redirects": "1", "format": "json",
         "titles": "|".join(batch)}
    for attempt in range(3):
        try:
            return requests.post(API, data=p, headers=HEADERS, timeout=60).json()
        except Exception:
            time.sleep(1.0 + attempt)
    return None


def fetch_contents(titles):
    pages = {}
    failed = []

    def take(data):
        for pid, pg in data.get("query", {}).get("pages", {}).items():
            if int(pid) < 0 or not pg.get("revisions"):
                continue
            pages[pid] = (pg["title"], pg["revisions"][0]["slots"]["main"]["*"])

    def fetch(batch):
        # a batch that fails as a whole is split and retried down to single titles,
        # so one oversized/bad page never costs the rest of the batch
        data = _fetch_batch(batch)
        if data is not None:
            take(data)
        elif len(batch) == 1:
            failed.append(batch[0])
        else:
            mid = len(batch) // 2
            fetch(batch[:mid])
            fetch(batch[mid:])

    for i in range(0, len(titles), 20):
        fetch(titles[i:i + 20])
        time.sleep(0.3)                                # be polite to Wikisource
    if failed:
        print(f"  ! {len(failed)} titles unfetchable after split-retry: "
              f"{failed[:5]}{'…' if len(failed) > 5 else ''}")
    return pages


def chapter_num(title):
    m = re.search(r"अध्यायः?\s*([०-९\d]+)", title)
    return int(m.group(1).translate(DEVA_DIG)) if m else 0


def clean(wt):
    wt = re.sub(r"<ref[^>]*>.*?</ref>", "", wt, flags=re.S)
    wt = re.sub(r"<[^>]+>", "", wt)
    for _ in range(5):                                  # {{header}} is multiline
        wt = re.sub(r"\{\{[^{}]*\}\}", "", wt)
    wt = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", wt)
    wt = re.sub(r"^=+.*?=+\s*$", "", wt, flags=re.M)
    wt = re.sub(r"'{2,}", "", wt)
    wt = re.sub(r"__[A-Z]+__", "", wt)
    return wt


def render_chapter(title, wt):
    C = chapter_num(title)
    if C == 0:
        return None
    t = clean(wt)

    def repl(m):
        d1, num, d2 = m.group(1), m.group(2), m.group(3)
        parts = num.translate(DEVA_DIG).split(".")
        try:
            if len(parts) == 2:
                c, v = int(parts[0]), int(parts[1])
            else:
                c, v = C, int(parts[0])
            return f"{d1} vrh_{c:03d}.{v:03d} {d2}"
        except ValueError:
            return m.group(0)

    # native verse refs: ।। C.V ।।  or  ।। V ।।  →  vrh_CCC.VVV (boundary kept)
    t = re.sub(r"([।॥]{1,2})\s*([०-९]+(?:\.[०-९]+)?)\s*([।॥]{1,2})", repl, t)
    lines = [ln.strip() for ln in t.splitlines() if re.search(r"[ऀ-ॿ]", ln)]
    body = "\n".join(lines)
    if len(re.findall(r"[ऀ-ॿ]", body)) < 150:
        return None
    return (C, body)


def main(out_path):
    titles = all_titles()
    pages = fetch_contents(titles)
    best = {}
    skipped = 0
    for pid, (title, wt) in pages.items():
        r = render_chapter(title, wt)
        if r:
            C, body = r
            if C not in best or len(body) > len(best[C][1]):
                best[C] = (C, body)
        else:
            skipped += 1
    ordered = sorted(best.values(), key=lambda x: x[0])

    out = ["Varahapurana (Varaha Purana) — Sanskrit",
           "Source: Sanskrit Wikisource (sa.wikisource.org), Devanagari. "
           "Harvested 2026-06-28. Citation markers vrh_<chapter>.<verse> derived "
           "from the native ।। C.V ।। verse numbering.",
           "", "# Text", ""]
    for C, body in ordered:
        out.append(f"अध्याय {C}")
        out.append(body)
        out.append("")
    text = "\n".join(out)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    deva = len(re.findall(r"[ऀ-ॿ]", text))
    markers = len(re.findall(r"vrh_\d+\.\d+", text))
    chs = [c for c, _ in ordered]
    print(f"pages fetched (unique): {len(pages)}")
    print(f"real verse chapters kept: {len(ordered)}  (skipped: {skipped})")
    print(f"chapter range: {min(chs) if chs else 0}–{max(chs) if chs else 0}")
    print(f"total Devanagari chars: {deva:,}")
    print(f"injected vrh_C.V markers: {markers:,}")
    print(f"wrote -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "varaha_wikisource.txt")
