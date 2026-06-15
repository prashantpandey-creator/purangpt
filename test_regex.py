import re
_CH_CITATION   = re.compile(r'\b[a-z]{2,5}_([\d\.,]+)')
lines = [
    "janmādyasya yato 'nvayāditarataścārtheṣvabhijñaḥ svarāṭ $ tene brahma hṛdā ya ādikavaye muhyanti yat sūrayaḥ &tejovārimṛdāṃ yathā vinimayo yatra trisargo 'mṛṣā % dhāmnā svena sadā nirastakuhakaṃ satyaṃ paraṃ dhīmahi // bhp_01.01.001* //dharmaḥ projjhitakaitavo 'tra paramo nirmatsarāṇāṃ satāṃ $ vedyaṃ vāstavam atra vastu śivadaṃ tāpatrayonmūlanam &dharmaḥ projjhitakaitavo 'tra paramo nirmatsarāṇāṃ satāṃ $ vedyaṃ vāstavam atra vastu śivadaṃ tāpatrayonmūlanam &śrīmadbhāgavate mahāmunikṛte kiṃ vā parairīśvaraḥ % sadyo hṛdyavarudhyate 'tra kṛtibhiḥ śuśrūṣubhistatkṣaṇāt // bhp_01.01.002* //nigamakalpatarorgalitaṃ phalaṃ $ śukamukhādamṛtadravasaṃyutam &nigamakalpatarorgalitaṃ phalaṃ $ śukamukhādamṛtadravasaṃyutam &pibata bhāgavataṃ rasam ālayaṃ % muhuraho rasikā bhuvi bhāvukāḥ // bhp_01.01.003* //",
    "satraṃ svargāya lokāya sahasrasamam āsata // bhp_01.01.004 //"
]

def _chapter_from_citation(line: str) -> int:
    m = _CH_CITATION.search(line)
    if m:
        parts = re.split(r'[,\.]', m.group(1))
        parts = [p for p in parts if p]
        print(f"Parts: {parts}")
        if len(parts) >= 2:
            try:
                chap_str = re.sub(r'\D+$', '', parts[-2])
                return int(chap_str)
            except ValueError:
                pass
    return None

for l in lines:
    print(f"Result: {_chapter_from_citation(l)}")
