"""Harvest the Bhavishya Purana (Sanskrit) from Sanskrit Wikisource.

Sanskrit Wikisource holds भविष्यपुराणम् as a fragmentary but CLEAN Devanagari
text (the only clean Sanskrit Bhavishya that exists — GRETIL/sanskritdocuments
have none; every archive.org OCR is Hindi-translation or garbled). This:

  1. enumerates all भविष्यपुराणम्/ subpages
  2. fetches content with redirects resolved (collapses the duplicate/messy names)
  3. strips wiki+HTML markup (<poem>, <span>, {{templates}}, [[links]])
  4. injects a faithful citation marker  bhav_<parva>.<chapter>.<verse>  derived
     from each page's OWN structure (parva from title, chapter from अध्यायः NNN,
     verse from the native ।। N ।। numbering) — so the result is decode-ready,
     not just readable
  5. emits one GRETIL-shaped raw text file (# Text marker) ordered by parva,chapter

Output is VERIFIED downstream by tools.source_reality_check (the real gate).
"""
import re
import sys
import requests

API = "https://sa.wikisource.org/w/api.php"
HEADERS = {"User-Agent": "PuranGPT-Academic/1.0 (scholarly Sanskrit corpus)"}
PREFIX = "भविष्यपुराणम्/"
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


def fetch_contents(titles):
    pages = {}  # pageid -> (title, wikitext)  — redirects collapse to canonical
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        p = {"action": "query", "prop": "revisions", "rvprop": "content",
             "rvslots": "main", "redirects": "1", "format": "json",
             "titles": "|".join(batch)}
        # POST: 20 long Devanagari titles overflow a GET URL → non-JSON error page
        r = requests.post(API, data=p, headers=HEADERS, timeout=60).json()
        for pid, pg in r["query"]["pages"].items():
            if int(pid) < 0 or not pg.get("revisions"):
                continue
            pages[pid] = (pg["title"], pg["revisions"][0]["slots"]["main"]["*"])
    return pages


def parva_num(title):
    if re.search(r"पर्व\s*१|ब्राह्म|प्रथम", title):
        return 1
    if re.search(r"पर्व\s*२|मध्यम|द्वितीय", title):
        return 2
    if re.search(r"पर्व\s*३|प्रतिसर्ग|तृतीय", title):
        return 3
    if re.search(r"पर्व\s*४|उत्तर|चतुर्थ", title):
        return 4
    return 0


def chapter_num(title):
    m = re.search(r"अध्यायः?\s*([०-९\d]+)", title)
    return int(m.group(1).translate(DEVA_DIG)) if m else 0


def clean(wt):
    wt = re.sub(r"<ref[^>]*>.*?</ref>", "", wt, flags=re.S)
    wt = re.sub(r"<[^>]+>", "", wt)                      # <poem> <span> <br> ...
    for _ in range(5):                                  # nested-ish templates
        wt = re.sub(r"\{\{[^{}]*\}\}", "", wt)
    wt = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", wt)  # links → display
    wt = re.sub(r"^=+.*?=+\s*$", "", wt, flags=re.M)    # == headers ==
    wt = re.sub(r"'{2,}", "", wt)                        # '' '''
    wt = re.sub(r"__[A-Z]+__", "", wt)                  # __NOTOC__ etc.
    return wt


def render_chapter(title, wt):
    """Return (parva, chapter, body_text) or None if not a real verse chapter."""
    P, C = parva_num(title), chapter_num(title)
    if P == 0 or C == 0:
        return None                                     # index/section page
    t = clean(wt)
    # inject faithful marker: ।। 15 ।।  →  ।। bhav_P.C.15 ।।  (keeps a boundary)
    t = re.sub(
        r"([।॥]{1,2})\s*([०-९]+)\s*([।॥]{1,2})",
        lambda m: f"{m.group(1)} bhav_{P}.{C}.{m.group(2).translate(DEVA_DIG)} {m.group(3)}",
        t,
    )
    lines = [ln.strip() for ln in t.splitlines() if re.search(r"[ऀ-ॿ]", ln)]
    body = "\n".join(lines)
    if len(re.findall(r"[ऀ-ॿ]", body)) < 150:           # stub, skip
        return None
    return (P, C, body)


def main(out_path):
    titles = all_titles()
    pages = fetch_contents(titles)
    chapters = []
    skipped = 0
    for pid, (title, wt) in pages.items():
        r = render_chapter(title, wt)
        if r:
            chapters.append(r)
        else:
            skipped += 1
    # dedupe by (parva, chapter) keeping the longest body; order by parva,chapter
    best = {}
    for P, C, body in chapters:
        if (P, C) not in best or len(body) > len(best[(P, C)][2]):
            best[(P, C)] = (P, C, body)
    ordered = sorted(best.values(), key=lambda x: (x[0], x[1]))

    parva_names = {1: "ब्राह्मपर्व", 2: "मध्यमपर्व",
                   3: "प्रतिसर्गपर्व", 4: "उत्तरपर्व"}
    out = ["Bhavishyamahapurana (Bhavishya Purana) — Sanskrit",
           "Source: Sanskrit Wikisource (sa.wikisource.org), Devanagari. "
           "Harvested 2026-06-28. Partial (clean fragment; no complete Sanskrit "
           "machine-readable Bhavishya exists). Citation markers bhav_<parva>.<chapter>.<verse> "
           "derived from each page's own parva/अध्याय/।।N।। structure.",
           "", "# Text", ""]
    for P, C, body in ordered:
        out.append(f"पर्व {P} ({parva_names.get(P,'')}) अध्याय {C}")
        out.append(body)
        out.append("")
    text = "\n".join(out)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

    deva = len(re.findall(r"[ऀ-ॿ]", text))
    markers = len(re.findall(r"bhav_\d+\.\d+\.\d+", text))
    by_parva = {}
    for P, C, _ in ordered:
        by_parva.setdefault(P, []).append(C)
    print(f"pages fetched (unique, redirects collapsed): {len(pages)}")
    print(f"real verse chapters kept: {len(ordered)}  (skipped non-chapter/stub: {skipped})")
    for P in sorted(by_parva):
        print(f"  parva {P} ({parva_names.get(P,'')}): {len(by_parva[P])} chapters")
    print(f"total Devanagari chars: {deva:,}")
    print(f"injected bhav_P.C.V markers: {markers:,}")
    print(f"wrote -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bhavishya_wikisource.txt")
