import re

_CH_CITATION   = re.compile(r'\b[a-z]{2,5}_([\d\.,]+)')

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

with open("data/raw_texts/gretil/bhagavata/sa_bhAgavatapurANa.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

chaps = set()
for line in lines:
    c = _chapter_from_citation(line)
    if c is not None and c > 0:
        chaps.add(c)
print(f"Detected chapters: {len(chaps)} -> {sorted(list(chaps))}")
