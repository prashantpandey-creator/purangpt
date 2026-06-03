# PuranGPT 🕉️

**AI Oracle of the 18 Mahapuranas & Hindu Sacred Texts**

PuranGPT is a specialized AI knowledge system that lets you explore the 18 Mahapuranas, Vedas, Upanishads, Bhagavad Gita, Ramayana, Mahabharata, and Yogic texts through natural language conversation — with exact verse citations.

> **Why PuranGPT?** Unlike general-purpose AI (ChatGPT, Gemini), PuranGPT is grounded in the actual texts. It returns exact verse numbers, Sanskrit originals, and never hallucinates Puranic content.

---

## ✨ Features

- 💬 **Chat with the Puranas** — Ask anything, get answers with citations like *(Bhagavata Purana, Skandha 10, Ch. 29, Verse 1)*
- 🔍 **Find All Instances** — "Show every mention of Narada across all 18 Puranas" — returns ALL occurrences
- 📚 **Explore Library** — Browse all indexed texts by text, chapter, verse
- 🔤 **Translate Shlokas** — Paste Sanskrit/Hindi, get English translation with commentary
- ⚖️ **Compare Texts** — "How do Vishnu Purana and Shiva Purana differ on creation?"
- 🧘 **Yogic Mode** — Specialized for yoga, meditation, tantra, chakra questions
- 🌐 **Hybrid Search** — Semantic + BM25 keyword search for best results
- 📡 **Streaming Responses** — Answers stream in real-time like ChatGPT
- 🔒 **100% Local** — Runs on your machine, no data sent to cloud (with Ollama)

---

## 🏗️ Architecture

```
User Query → FastAPI Backend → Hybrid Search (ChromaDB + BM25)
                          ↓                    ↓
                    Relevant passages    Exact term matches
                          ↓
                   LLM (Ollama/Groq) + Context → Cited Answer
```

**Stack:**
| Layer | Technology |
|-------|-----------|
| LLM (local) | Ollama + Qwen2.5:7b |
| LLM (cloud) | Groq API (llama-3.3-70b) |
| Embeddings | multilingual-e5-large |
| Vector DB | ChromaDB |
| Keyword search | BM25 (rank_bm25) |
| RAG framework | LlamaIndex |
| Backend | FastAPI + SSE streaming |
| Frontend | Pure HTML/CSS/JS |
| OCR | PaddleOCR (Devanagari) |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai) (for local LLM) — or a Groq API key

### 1. Setup
```bash
git clone <this-repo>
cd purangpt
chmod +x setup.sh && ./setup.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Check/install Ollama and pull the Qwen2.5:7b model
- Create the data directory structure

### 2. Configure
```bash
cp .env.example .env
# Edit .env to set your preferences
```

### 3. Download Texts
```bash
source venv/bin/activate
python run.py --download
# Downloads all 18 Mahapuranas + other texts
# Takes 10-30 minutes depending on internet speed
```

### 4. Extract & Index
```bash
python run.py --extract   # OCR + text extraction
python run.py --chunk     # Shloka-aware chunking
python run.py --index     # Build vector + BM25 indexes
```
Or run all pipeline steps at once:
```bash
python run.py --pipeline  # All steps sequentially
```

### 5. Start the App
```bash
python run.py
# Opens browser at http://localhost:8000
```

---

## 🐳 Docker (Easiest)

```bash
# Clone and start everything:
docker-compose up -d

# Then visit: http://localhost:8000
# Note: First run downloads the LLM model (~4GB)
```

---

## ⚙️ Configuration

Edit `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `groq` |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model name |
| `GROQ_API_KEY` | *(empty)* | Groq API key for cloud mode |
| `DB_DIR` | `./data/chroma_db` | ChromaDB storage path |
| `PORT` | `8000` | Server port |

**Recommended models by hardware:**
| Your Hardware | Recommended Model | RAM |
|--------------|------------------|-----|
| M1/M2/M3 Mac | `qwen2.5:7b` | 8GB+ |
| 4GB RAM laptop | `llama3.2:3b` | 4GB |
| GPU server | `qwen2.5:14b` | 12GB+ |
| Cloud/API | `groq:llama-3.3-70b` | N/A |

---

## 📂 Project Structure

```
purangpt/
├── data_pipeline/
│   ├── downloader.py    # Downloads PDFs from vedpuran.net + fallbacks
│   ├── extractor.py     # PyMuPDF + PaddleOCR text extraction
│   └── chunker.py       # Shloka-aware chunking with metadata
├── indexer/
│   ├── build_index.py   # Embedding + ChromaDB + BM25 indexing
│   └── search.py        # Hybrid semantic + keyword search
├── engine/
│   ├── query_engine.py  # LlamaIndex RAG engine + streaming
│   └── prompts.py       # Specialized Puranic scholar prompts
├── backend/
│   └── main.py          # FastAPI server + SSE streaming
├── frontend/
│   ├── index.html       # Temple-inspired UI
│   ├── style.css        # Dark gold/saffron design system
│   └── app.js           # Chat + search + explore logic
├── data/
│   ├── raw_pdfs/        # Downloaded PDF files
│   ├── extracted/       # Extracted text JSON files
│   ├── chunks/          # Chunked JSONL files
│   ├── chroma_db/       # ChromaDB vector store
│   └── indexes/         # BM25 index + chunk map
├── run.py               # Main entry point
├── setup.sh             # One-command setup
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker image
└── docker-compose.yml   # Full stack with Ollama
```

---

## 📖 Indexed Texts

### 18 Mahapuranas
| # | Purana | Sanskrit | Deity |
|---|--------|---------|-------|
| 1 | Agni Purana | अग्नि पुराण | Agni |
| 2 | Bhagavata Purana | भागवत पुराण | Vishnu/Krishna |
| 3 | Bhavishya Purana | भविष्य पुराण | Surya |
| 4 | Brahma Purana | ब्रह्म पुराण | Brahma |
| 5 | Brahmanda Purana | ब्रह्माण्ड पुराण | Brahma |
| 6 | Brahma Vaivarta Purana | ब्रह्मवैवर्त पुराण | Krishna |
| 7 | Garuda Purana | गरुड पुराण | Vishnu |
| 8 | Kurma Purana | कूर्म पुराण | Vishnu |
| 9 | Linga Purana | लिंग पुराण | Shiva |
| 10 | Markandeya Purana | मार्कण्डेय पुराण | Brahma |
| 11 | Matsya Purana | मत्स्य पुराण | Vishnu |
| 12 | Narada Purana | नारद पुराण | Narada |
| 13 | Padma Purana | पद्म पुराण | Vishnu |
| 14 | Shiva Purana | शिव पुराण | Shiva |
| 15 | Skanda Purana | स्कन्द पुराण | Kartikeya |
| 16 | Vamana Purana | वामन पुराण | Vishnu |
| 17 | Varaha Purana | वराह पुराण | Vishnu |
| 18 | Vishnu Purana | विष्णु पुराण | Vishnu |

### Additional Texts
- 4 Vedas (Rigveda, Samaveda, Yajurveda, Atharvaveda)
- Ramayana, Mahabharata, Bhagavad Gita
- 108 Upanishads
- Yoga Sutras of Patanjali
- Hatha Yoga Pradipika
- Yoga Vasistha

---

## 🔌 API Reference

```
POST /api/chat        - Stream chat (SSE)
POST /api/search      - Raw hybrid search
POST /api/instances   - Find all instances
GET  /api/puranas     - List indexed texts
GET  /api/status      - Health check
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Who is Narada Muni?", "mode": "scholar"}'
```

---

## 🙏 Credits & Legal

- Texts from [vedpuran.net](https://vedpuran.net), [GRETIL](https://gretil.sub.uni-goettingen.de), [sacred-texts.com](https://sacred-texts.com)
- All Puranic texts are ancient public domain works
- Translations by various scholarly traditions
- Built with LlamaIndex, ChromaDB, FastAPI, Ollama

---

*ॐ तत् सत् — May this serve seekers of wisdom* 🙏
