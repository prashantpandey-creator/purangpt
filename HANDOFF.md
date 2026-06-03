# PuranGPT — Complete Project Handoff

## What this is
AI-powered scholarly research tool for Hindu sacred texts. Users ask questions about the 18 Mahapuranas, Vedas, Upanishads, Yogic scriptures and get answers with exact Sanskrit verse citations. Built by Prashant Pandey (pandeyp2@legal.regn.net).

---

## Tech Stack
- **Backend**: FastAPI + Python, SSE streaming, async
- **LLM**: Gemini 2.5 Flash (primary, key is valid) + Groq fallback (key currently invalid)
- **RAG**: ChromaDB (vector) + BM25Okapi hybrid search with MMR diversity reranking
- **Embeddings**: `intfloat/multilingual-e5-large`
- **Corpus**: GRETIL Sanskrit texts (31 texts, ~18M chars) + Shailendra Sharma commentaries
- **Frontend**: Vanilla HTML/CSS/JS, Lucide SVG icons, Crimson Pro + Cinzel + Inter fonts
- **Design**: VIDA framework (92/100 audit score), 4-level luminance hierarchy, WCAG AA

---

## Repository
- **Local path**: `/Users/badenath/projects/vedic puran/purangpt/`
- **GitHub**: https://github.com/prashantpandey-creator/purangpt (to be pushed)
- **Deploy**: Railway.app with `Dockerfile.railway` + `railway.toml`
- **iOS**: Capacitor wrapper in `ios_app/` (wraps existing web frontend)

---

## Key Files
```
purangpt/
├── backend/main.py          ← FastAPI app, all API endpoints, LLM routing
├── frontend/
│   ├── index.html           ← Single-page app, Lucide icons, ARIA labels
│   ├── style.css            ← Complete design system (388 lines, 4-level surfaces)
│   └── app.js               ← Chat, streaming, source cards, citation links
├── indexer/search.py        ← HybridSearcher: RRF fusion + MMR reranking
├── data_pipeline/           ← Download → OCR → chunk → index pipeline
├── vida_audit.py            ← Design quality audit (92/100, runs in <1s)
├── vida_audit_extended.py   ← Full audit: DOM + CSS + Lighthouse + axe-core
├── push_to_github.sh        ← One-command GitHub push script
├── DEPLOY.md                ← Railway + iOS deployment guide
└── ios_app/                 ← Capacitor iOS scaffold
    ├── capacitor.config.json
    ├── package.json
    └── ios_config.js        ← Points iOS app at Railway URL
```

---

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | SSE streaming chat (scholar/deep/nath/darshana modes) |
| POST | `/api/infer` | Original scholarly inference across all texts |
| POST | `/api/search` | Raw hybrid search |
| POST | `/api/sanskrit-search` | GRETIL full-text search with IAST normalization |
| POST | `/api/instances` | Find all occurrences of a topic |
| GET  | `/api/status` | Health check + active provider info |
| GET  | `/api/puranas` | Catalog of all indexed texts |
| GET  | `/api/text/{id}` | Paginated text reader |
| GET/DELETE | `/api/session/{id}` | Session memory management |

---

## Environment Variables (.env)
```
GEMINI_API_KEY=AIzaSy...          # VALID — primary provider
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=gsk_3aC3...          # INVALID — key rejected by Groq
LLM_PROVIDER=groq                  # auto-detects and falls back to Gemini
EMBED_MODEL=intfloat/multilingual-e5-large
DB_DIR=./data/chroma_db
INDEX_DIR=./data/indexes
PORT=8000
```

---

## Corpus Status
**Indexed and searchable via GRETIL (Sanskrit, IAST):**
Agni, Bhagavata, Brahma, Brahmanda, Garuda, Kurma, Linga, Markandeya, Matsya, Narada, Shiva, Vamana, Vishnu Puranas + Ramayana + Bhagavad Gita + Rig/Sama/Atharva Veda + Upanishads (Isha, Katha, Mandukya, Prasna, Kaushitaki, Aitareya, Taittiriya, Svetasvatara) + Manusmriti + Amarakosha + Ashtadhyayi

**Yoga & Darshana texts (indexed):**
Yoga Sutras (196 sutras with commentary), Samkhya Karika (72 karikas), Brahma Sutras, Hatha Yoga Pradipika, Gorakshashataka, Gheranda Samhita

**Shailendra Sharma corpus (84 chunks from official sites):**
- Full Shiv Sutra commentary (all 77 sutras)
- Gorakh Bodh (chakra commentary + tenth door passage)
- Yogeshwari Gita preface (Brahma/Vishnu/Shiva yogic interpretation)
- Shiva Sutras Special Discussion (65-sutra Q&A)
- Ojas & Amrita (immortality science — 8 drops, 12yr per drop)
- Yoga & Alchemy (prana=mercury, apana=sulfur)
- Khechari Vidya, HYP Discussion, Kundalini Upanishad

**Missing (need to purchase or pipeline):**
Bhavishya, Padma, Varaha, Brahma Vaivarta Puranas + Yoga Darshan (Patanjali commentary), full Hatha Yoga Pradipika commentary

---

## Design System (style.css)
```css
/* Surface hierarchy (luminance, not borders) */
--s0: #0B0907  /* void */
--s1: #111009  /* base surface */
--s2: #181510  /* raised: cards, sidebar */
--s3: #1F1C13  /* elevated: modals */
--s4: #272219  /* hover state */

/* Text */
--t1: #EDE8D8  /* primary (15.6:1 contrast — AAA) */
--t2: #9A8E70  /* secondary (5.9:1 — AA) */
--t3: #8A7E65  /* muted (4.8:1 — AA) */

/* Accent — used in ≤10% of rules */
--accent: #C4961F  /* warm amber */

/* Fonts */
--font-display:  'Cinzel' (headings only)
--font-body:     'Inter' 16px
--font-reading:  'Crimson Pro' (message content)
--font-devanagari: 'Noto Sans Devanagari'
```

---

## Response Format (SCHOLAR_SYSTEM prompt)
Every answer follows this structure:
1. **📋 Summary** — plain 3-5 sentence answer first
2. **📚 Citations & Primary Evidence** — Sanskrit originals + IAST + translation
3. **💬 Researched Quotes** — blockquoted direct passages
4. **🔗 Cross-Textual Analysis** — multi-tradition comparison
5. **🤖 General Knowledge** — clearly labelled inference
6. **🔮 Synthesis & Conclusion**

---

## VIDA Audit (run anytime)
```bash
python vida_audit.py                    # 96/100 base CSS audit
python vida_audit_extended.py           # 92/100 full DOM + CSS audit
python vida_audit_extended.py --lighthouse --url http://localhost:8000  # + Lighthouse
```

---

## Pending / Next Steps
1. **Get a new Groq API key** — current one rejected (401). Free at console.groq.com
2. **Run data pipeline** after Railway deploy: `railway run python run.py --pipeline`
3. **Purchase Shailendra Sharma books** from shailendrasharmabooks.com, run `ingest_sharma_books.py`
4. **Run `fetch_missing_texts.py`** locally to download 5 missing Puranas
5. **iOS App Store submission** — needs Apple Developer account ($99/yr)
6. **Rebuild Groq key** in `.env` and redeploy

---

## To start a new session with full context
Paste this entire document at the start of the new conversation and say:
"Continue working on PuranGPT. Here is the full project state."
