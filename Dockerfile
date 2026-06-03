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

# Create data directories
RUN mkdir -p data/raw_pdfs data/extracted data/chunks data/chroma_db data/indexes

# Create __init__.py files
RUN touch data_pipeline/__init__.py indexer/__init__.py engine/__init__.py backend/__init__.py

# Copy env example if .env doesn't exist
RUN cp .env.example .env 2>/dev/null || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || exit 1

CMD ["python", "run.py", "--port", "8000"]
