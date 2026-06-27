FROM python:3.11-slim

# System dependencies for PaddleOCR + OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    curl wget git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Pre-download the embedding model used at runtime (intfloat/multilingual-e5-small,
# 384-dim) so it's baked into the image and never downloaded at container boot.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# Create data directories
RUN mkdir -p data/raw_pdfs data/extracted data/chunks data/chroma_db data/indexes

# Create __init__.py files
RUN touch data_pipeline/__init__.py indexer/__init__.py engine/__init__.py backend/__init__.py


EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

# This is an I/O-bound async app (every request waits on the LLM API), so a single
# event loop handles high concurrency — we do NOT need one worker per core. 2 workers
# gives redundancy (one serves while the other restarts) at a fraction of the RAM.
# The embedding model is loaded ONCE in the gunicorn master via the on_starting hook
# in gunicorn.conf.py, then shared across workers copy-on-write (preload fork) — so the
# ~1.2GB model lives once, not per-worker (was the cause of 9GB RAM use at 6 workers).
CMD ["gunicorn", "backend.main:app", "-c", "gunicorn.conf.py"]
