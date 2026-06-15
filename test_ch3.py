import re

_CH_CITATION   = re.compile(r'\b[a-z]{2,5}_([\d\.,]+)')
DANDA_RE   = re.compile(r'[।॥]')

_CH_GRETIL     = re.compile(r'%\s*chapter\s*\{(\d+)\}', re.IGNORECASE)
_CH_BOOK       = re.compile(r'Book\s+\d+\s+Chapter\s+(\d+)', re.IGNORECASE)
_CH_ADHYAYA    = re.compile(
    r'(?:adhy[\u0101a][y]a[h\u1e25]?|chapter|sarga|k[\u0101a][n\u1e47][\u1e0da]a|parva|skandha|samhit[\u0101a]|khanda)\s+(\d+)',
    re.IGNORECASE,
)
_CH_DEVA       = re.compile(r'(?:अध्याय|स्कन्ध|काण्ड|पर्व|सर्ग|खण्ड)\s*([\u0966-\u096F\d]+)')
_DEVA_TO_ASCII = str.maketrans('०१२३४५६७८९', '0123456789')

def _detect_chapter(line: str):
    line_n = line.translate(_DEVA_TO_ASCII)
    for regex in (_CH_GRETIL, _CH_BOOK, _CH_ADHYAYA):
        m = regex.search(line_n)
        if m:
            return int(m.group(1))
    m = _CH_DEVA.search(line)
    if m:
        return int(m.group(1).translate(_DEVA_TO_ASCII))
    return None

def _chapter_from_citation(line: str):
    m = _CH_CITATION.search(line)
    if m:
        parts = re.split(r'[,\.]', m.group(1))
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            chap_str = re.sub(r'\D+$', '', parts[-2])
            return int(chap_str)
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
