import re

_CH_CITATION   = re.compile(r'\b[a-z]{2,5}_([\d\.,]+)')
DANDA_RE   = re.compile(r'[।॥]')

def _chapter_from_citation(line: str):
    m = _CH_CITATION.search(line)
    if m:
        parts = re.split(r'[,\.]', m.group(1))
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            try:
                chap_str = re.sub(r'\D+$', '', parts[-2])
                return int(chap_str)
            except ValueError:
                pass
    return None

def _detect_chapter(line: str):
    return None

with open("data/raw_texts/gretil/bhagavata/sa_bhAgavatapurANa.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

current_chapter = 0
for line in lines[:50]:
    line = line.strip()
    if not line: continue
    
    ch = _detect_chapter(line)
    if ch is not None and ch > 0:
        current_chapter = ch
    else:
        ch_cite = _chapter_from_citation(line)
        if ch_cite is not None and ch_cite > 0:
            current_chapter = ch_cite
    
    print(f"Line: {line[:30]}... -> current_chapter: {current_chapter}")
