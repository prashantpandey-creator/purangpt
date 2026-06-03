#!/usr/bin/env bash
# ============================================================
# PuranGPT — One-Command Setup Script
# ============================================================
# Usage: chmod +x setup.sh && ./setup.sh
# ============================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
CYAN='\033[0;36m'; GOLD='\033[0;33m'; BOLD='\033[1m'; RESET='\033[0m'

print_header() { echo -e "\n${GOLD}${BOLD}$1${RESET}"; echo -e "${GOLD}$(printf '─%.0s' {1..60})${RESET}"; }
ok()    { echo -e "  ${GREEN}✓${RESET} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
err()   { echo -e "  ${RED}✗${RESET} $1"; }
info()  { echo -e "  ${CYAN}→${RESET} $1"; }

# ── Banner ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GOLD}${BOLD}  ॐ  PuranGPT Setup  ॐ${RESET}"
echo -e "${GOLD}  AI Oracle of the 18 Mahapuranas${RESET}"
echo ""

# ── Step 1: Python version check ──────────────────────────────────────────
print_header "Step 1/6: Checking Python version"

PYTHON=$(command -v python3 || command -v python || true)
if [ -z "$PYTHON" ]; then
    err "Python not found. Install Python 3.10+ from https://python.org"
    exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    err "Python 3.10+ required. Found Python $PY_VERSION"
    info "Install from: https://python.org/downloads"
    exit 1
fi
ok "Python $PY_VERSION"

# ── Step 2: Virtual environment ───────────────────────────────────────────
print_header "Step 2/6: Setting up virtual environment"

if [ -d "venv" ]; then
    ok "Virtual environment already exists at ./venv"
else
    info "Creating virtual environment…"
    "$PYTHON" -m venv venv
    ok "Virtual environment created at ./venv"
fi

# Activate venv
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi

# Upgrade pip silently
python -m pip install --upgrade pip --quiet
ok "pip upgraded"

# ── Step 3: Install dependencies ──────────────────────────────────────────
print_header "Step 3/6: Installing Python dependencies"
info "This may take 3-5 minutes (first run only)…"

# Install core deps first (faster feedback loop)
pip install --quiet fastapi uvicorn[standard] sse-starlette python-dotenv rich
ok "Core web framework installed"

# Install the rest
pip install -r requirements.txt --quiet
ok "All dependencies installed"

# ── Step 4: Environment configuration ────────────────────────────────────
print_header "Step 4/6: Environment configuration"

if [ ! -f ".env" ]; then
    cp .env.example .env
    ok ".env created from .env.example"
    warn "Edit .env to set your Groq API key or Ollama model preferences"
else
    ok ".env already exists"
fi

# ── Step 5: Check Ollama ──────────────────────────────────────────────────
print_header "Step 5/6: Checking Ollama (local LLM)"

if command -v ollama &>/dev/null; then
    ok "Ollama is installed"

    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags &>/dev/null; then
        ok "Ollama is running"
        OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
        
        # Check if model is already pulled
        if ollama list 2>/dev/null | grep -q "$OLLAMA_MODEL"; then
            ok "Model $OLLAMA_MODEL already downloaded"
        else
            info "Pulling model: $OLLAMA_MODEL (this downloads ~4-6 GB, please wait…)"
            ollama pull "$OLLAMA_MODEL"
            ok "Model $OLLAMA_MODEL ready"
        fi
    else
        warn "Ollama is installed but not running"
        info "Start it with: ollama serve"
        info "Then pull the model: ollama pull qwen2.5:7b"
        warn "PuranGPT will use Groq API if GROQ_API_KEY is set in .env"
    fi
else
    warn "Ollama not found (optional — needed for local/offline mode)"
    info "Install from: https://ollama.ai"
    info "After installing: ollama pull qwen2.5:7b"
    info ""
    info "Alternative: Set GROQ_API_KEY in .env for cloud LLM (free tier available)"
    info "Get your free key: https://console.groq.com"
fi

# ── Step 6: Create data directories ──────────────────────────────────────
print_header "Step 6/6: Creating data directories"

mkdir -p data/raw_pdfs data/extracted data/chunks data/chroma_db data/indexes
ok "data/ directory structure created"

# ── Create __init__.py files ──────────────────────────────────────────────
touch data_pipeline/__init__.py indexer/__init__.py engine/__init__.py backend/__init__.py
ok "Python package __init__.py files created"

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GOLD}${BOLD}  ════════════════════════════════════════${RESET}"
echo -e "${GOLD}${BOLD}  ✓  PuranGPT Setup Complete!${RESET}"
echo -e "${GOLD}${BOLD}  ════════════════════════════════════════${RESET}"
echo ""
echo -e "${BOLD}Next Steps:${RESET}"
echo ""
echo -e "  ${CYAN}1. Download sacred texts:${RESET}"
echo -e "     python run.py --download"
echo ""
echo -e "  ${CYAN}2. Build search indexes (after download):${RESET}"
echo -e "     python run.py --extract --chunk --index"
echo ""
echo -e "  ${CYAN}3. Or run the full pipeline at once:${RESET}"
echo -e "     python run.py --pipeline"
echo ""
echo -e "  ${CYAN}4. Start PuranGPT:${RESET}"
echo -e "     python run.py"
echo -e "     → Open http://localhost:8000"
echo ""
echo -e "  ${YELLOW}Tip:${RESET} Set GROQ_API_KEY in .env for faster cloud responses"
echo -e "  ${YELLOW}Tip:${RESET} Check status anytime: python run.py --status"
echo ""
echo -e "  ${GOLD}ॐ तत् सत् — May this serve seekers of wisdom 🙏${RESET}"
echo ""
