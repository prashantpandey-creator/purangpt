# CLAUDE.md — PuranGPT Codebase Guide

## Project Overview

PuranGPT is a Retrieval-Augmented Generation (RAG) system for querying Hindu sacred texts — the 18 Mahapuranas, Ramayana, Mahabharata, Bhagavad Gita, 108 Upanishads, and Yoga texts — with exact verse citations.

**Core concept:** Download PDFs → Extract text (OCR if needed) → Chunk by shloka boundaries → Build dual index (vector + BM25) → Serve via FastAPI with streaming LLM responses.

---

## Repository Layout

```
purangpt/
├── data_pipeline/
│   ├── downloader.py      # Async PDF downloader (aiohttp, tenacity, resume support)
│   ├── extractor.py       # PyMuPDF + PaddleOCR text extraction
│   └── chunker.py         # Shloka-aware chunker → JSONL output
├── indexer/
│   ├── build_index.py     # ChromaDB vector index + BM25 keyword index
│   └── search.py          # Hybrid search (semantic + BM25)
├── engine/
│   ├── query_engine.py    # PuranGPTEngine: RAG orchestration + SSE streaming
│   └── prompts.py         # Mode-specific LLM prompts (scholar, yogic, compare, etc.)
├── backend/
│   └── main.py            # FastAPI app: /api/chat, /api/search, /api/instances
├── frontend/
│   ├── index.html         # Temple-inspired UI
│   ├── style.css          # Gold/saffron design system
│   └── app.js             # Chat + search + explore JS
├── data/                  # Runtime data (gitignored)
│   ├── raw_pdfs/          # Downloaded PDFs
│   ├── extracted/         # Per-PDF JSON (page-level text)
│   ├── chunks/            # JSONL chunk files + all_chunks.jsonl
│   ├── chroma_db/         # ChromaDB persistent store
│   └── indexes/           # bm25_index.pkl + chunk_map.json
├── run.py                 # Unified CLI entry point
├── setup.sh               # One-command environment setup
├── Dockerfile
└── docker-compose.yml     # PuranGPT + Ollama services
```

---

## Data Pipeline

The pipeline runs in four sequential stages, each independently re-runnable:

### Stage 1 — Download (`data_pipeline/downloader.py`)
- **Class:** `PuranDownloader`
- **Catalog:** 18 Mahapuranas + Ramayana, Mahabharata, Bhagavad Gita, 108 Upanishads, Yoga texts (30+ texts total, defined in `_build_catalog()`)
- **Sources:** vedpuran.net (primary) → archive.org / sacred-texts.com / GRETIL (fallbacks)
- **Features:** async `aiohttp`, per-domain rate limiting (semaphores + min-delay), exponential backoff with jitter (5 attempts), resume support via `.download_state.json`, Rich progress bars
- **Output:** `data/raw_pdfs/{key}/{key}.pdf` (or `_vol1.pdf`, `_vol2.pdf` for multi-volume)

### Stage 2 — Extract (`data_pipeline/extractor.py`)
- **Class:** `TextExtractor`
- **Strategy:**
  1. PyMuPDF (`fitz`) extracts embedded text layer
  2. If avg chars/page < `min_text_per_page` (default 100) → PaddleOCR fallback
  3. OpenCV preprocessing before OCR: deskew (Hough transform) → Otsu binarization → morphological denoise
- **OCR language:** `hi` (Hindi/Devanagari, covers Sanskrit)
- **Output:** `data/extracted/{key}.json` with page-by-page text + confidence + method

### Stage 3 — Chunk (`data_pipeline/chunker.py`)
- **Class:** `PuranicChunker`
- **Shloka detection:** splits on Devanagari double-danda `॥`; falls back to blank lines for prose/English
- **Chapter detection:** multilingual regex covers अध्याय, Adhyaya, Chapter, Sarga, Kanda, Parva, Skandha, Samhita, Khanda
- **Chunk size:** 3 verses, 1-verse overlap, max 2400 chars (~800 tokens)
- **Chunk ID format:** `{key}-ch{chapter:04d}-v{verse:04d}` (deterministic)
- **Output:** `data/chunks/{key}.jsonl` + `data/chunks/all_chunks.jsonl`

Each chunk carries: `id`, `purana`, `purana_key`, `book_section`, `chapter`, `verse_range`, `text`, `language`, `source_file`, `source_page`, `word_count`.

### Stage 4 — Index (`indexer/build_index.py`)
- **Class:** `EmbeddingIndexer`
- **Vector index:** ChromaDB with `intfloat/multilingual-e5-large` embeddings (cosine similarity). Texts prefixed with `"passage: "` per E5 convention.
- **Keyword index:** `BM25Okapi` (rank_bm25). Tokenizes Devanagari (`[ऀ-ॿ]+`) and Latin words separately.
- **Resume support:** skips chunks already in ChromaDB by ID
- **Output:** `data/chroma_db/` (vector store) + `data/indexes/bm25_index.pkl` + `data/indexes/chunk_map.json`

---

## Query Engine (`engine/query_engine.py`)

**Class:** `PuranGPTEngine`

**Workflow for each query:**
1. `HybridSearcher.hybrid_search()` — semantic + BM25 (configurable `top_k`, default 10)
2. Emit `{"type": "sources", "sources": [...]}` immediately (frontend shows while LLM thinks)
3. Build prompt via `get_prompt(mode)` + `format_context(results)`
4. Stream tokens from LLM → yield `{"type": "token", "content": "..."}`
5. Yield `{"type": "done"}`

**LLM providers:**
- **Ollama** (default): `qwen2.5:7b` at `http://localhost:11434` — low-level `aiohttp` streaming via `/api/generate`
- **Groq API**: `llama-3.3-70b-versatile` — OpenAI-compatible SSE streaming
- **Auto-detect:** tries Ollama first (`/api/tags` ping), falls back to Groq if `GROQ_API_KEY` is set

**Query modes:** `scholar` (default), `yogic`, `compare`, `translate`, `find_instances`

**Key methods:**
- `query()` — async generator, yields SSE-compatible dicts
- `query_sync()` — collects full response, returns `{answer, sources, mode}`
- `find_instances()` — finds all occurrences of a topic across all texts, grouped by Purana

---

## CLI Commands (`run.py`)

```bash
python run.py                        # Start FastAPI server (default port 8000)
python run.py --download             # Stage 1: download PDFs
python run.py --extract              # Stage 2: OCR + text extraction
python run.py --chunk                # Stage 3: shloka chunking
python run.py --index                # Stage 4: build vector + BM25 indexes
python run.py --pipeline             # All 4 stages sequentially
python run.py --status               # Show system health (indexes, Ollama, Groq)
python run.py --dev                  # Server with hot-reload
python run.py --verbose              # Debug logging

# Download specific texts or categories:
python run.py --download --texts bhagavata vishnu
python run.py --download --category mahapuranas  # or: epics | upanishads | yoga
```

Each pipeline module also has its own `main()` CLI:
```bash
python data_pipeline/downloader.py --list          # Show all available texts
python data_pipeline/extractor.py data/raw_pdfs   # Batch extract
python data_pipeline/chunker.py                   # Batch chunk
python indexer/build_index.py --model intfloat/multilingual-e5-small  # Faster/smaller model
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | SSE streaming chat |
| POST | `/api/search` | Raw hybrid search |
| POST | `/api/instances` | Find all topic instances |
| GET | `/api/puranas` | List indexed texts |
| GET | `/api/status` | Health check |

---

## Environment Variables (`.env`)

| Variable | Default | Notes |
|----------|---------|-------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `groq` |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Any Ollama model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `GROQ_API_KEY` | — | Required for Groq |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | HuggingFace model |
| `DB_DIR` | `./data/chroma_db` | ChromaDB path |
| `DATA_DIR` | `data` | Root data directory |
| `PORT` | `8000` | Server port |

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `aiohttp` + `aiofiles` | Async HTTP downloads |
| `tenacity` | Retry with backoff |
| `PyMuPDF` (`fitz`) | PDF text extraction |
| `paddleocr` + `paddlepaddle` | Devanagari OCR |
| `opencv-python` (`cv2`) | Image preprocessing for OCR |
| `sentence-transformers` | Multilingual embeddings |
| `chromadb` | Vector store |
| `rank_bm25` | BM25 keyword search |
| `llama-index` | RAG framework (LLM clients) |
| `fastapi` + `uvicorn` | Web server |
| `rich` | Progress bars + console output |
| `python-dotenv` | `.env` loading |

---

## Docker

```bash
docker-compose up -d    # Starts purangpt (port 8000) + ollama (port 11434)
                        # First run pulls qwen2.5:7b (~4-6 GB)
```

Data is mounted from `./data` so indexes persist across container restarts.

---

## Text Catalog Summary

- **18 Mahapuranas:** Agni, Bhagavata, Bhavishya, Brahma, Brahmanda, Brahma Vaivarta, Garuda, Kurma, Linga, Markandeya, Matsya, Narada, Padma, Shiva, Skanda, Vamana, Varaha, Vishnu
- **Epics:** Ramayana, Mahabharata, Bhagavad Gita
- **Upanishads:** 108 Upanishads collection + Isha, Kena, Katha, Chandogya, Brihadaranyaka, Mandukya individually
- **Yoga:** Yoga Sutras of Patanjali, Hatha Yoga Pradipika, Yoga Vasistha

All sourced from vedpuran.net (primary), archive.org, and sacred-texts.com (fallbacks).
