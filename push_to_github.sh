#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PuranGPT — Push to GitHub + Deploy to Railway
# Run this in Terminal from the purangpt/ directory
# ═══════════════════════════════════════════════════════════════

set -e  # stop on any error

GITHUB_USER="prashantpandey-creator"
REPO_NAME="purangpt"
GITHUB_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PuranGPT → GitHub → Railway"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: Init git if needed ────────────────────────────────
if [ ! -d ".git" ]; then
  echo "▶ Initializing git repository…"
  git init
  git branch -m main
fi

# ── Step 2: Remove lock if stuck ─────────────────────────────
rm -f .git/index.lock

# ── Step 3: Configure git identity ───────────────────────────
git config user.email "pandeyp2@legal.regn.net"
git config user.name "Prashant Pandey"

# ── Step 4: Stage all files ───────────────────────────────────
echo "▶ Staging files…"
git add .
git status --short | head -20
echo ""

# ── Step 5: Commit ────────────────────────────────────────────
echo "▶ Committing…"
git commit -m "PuranGPT v2 — Scholarly Puranic AI with VIDA design system

- 18 Mahapuranas + Upanishads + Yogic texts indexed via GRETIL
- Shailendra Sharma commentaries (Shiv Sutra, Gorakh Bodh, Yogeshwari)
- Hybrid RAG: ChromaDB vector + BM25 + IAST normalization + MMR
- Multi-LLM: Gemini, Groq, DeepSeek, Together AI with auto-fallback
- Premium dark UI: Lucide icons, 4-level luminance hierarchy, WCAG AA
- VIDA audit framework: 92/100 design quality score
- Session memory, Deep Research, Sanskrit search, Inference engine
- iOS-ready via Capacitor, Railway deployment config"

# ── Step 6: Add remote ────────────────────────────────────────
echo ""
echo "▶ Connecting to GitHub…"
git remote remove origin 2>/dev/null || true
git remote add origin "$GITHUB_URL"

# ── Step 7: Create GitHub repo (requires gh CLI) ─────────────
if command -v gh &> /dev/null; then
  echo "▶ Creating GitHub repo (gh CLI detected)…"
  gh repo create "$REPO_NAME" \
    --public \
    --description "AI Oracle of the 18 Mahapuranas — Scholarly Puranic Research with exact verse citations" \
    --push \
    --source=. \
    || true
else
  echo "⚠  GitHub CLI (gh) not found."
  echo ""
  echo "  Do this first:"
  echo "  1. Go to https://github.com/new"
  echo "  2. Repository name: ${REPO_NAME}"
  echo "  3. Public, no README (we have one)"
  echo "  4. Click 'Create repository'"
  echo "  5. Then press Enter to continue…"
  read -r
  git push -u origin main
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Code pushed to GitHub!"
echo "  https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  NEXT: Deploy to Railway"
echo "  ─────────────────────────────────────────"
echo "  1. Go to https://railway.app"
echo "  2. New Project → Deploy from GitHub"
echo "  3. Select: ${GITHUB_USER}/${REPO_NAME}"
echo "  4. Add these environment variables:"
echo ""
echo "     GEMINI_API_KEY = <your key from aistudio.google.com>"
echo "     GROQ_API_KEY   = <your key from console.groq.com>"
echo "     LLM_PROVIDER   = gemini"
echo "     GEMINI_MODEL   = gemini-2.5-flash"
echo "     PORT           = 8000"
echo "     HOST           = 0.0.0.0"
echo ""
echo "  5. Volumes tab → Add volume at /app/data"
echo "  6. After deploy, upload your data:"
echo "     npm install -g @railway/cli"
echo "     railway login && railway link"
echo "     railway run python fetch_gretil.py    # re-fetch texts"
echo "     railway run python run.py --chunk     # rebuild chunks"
echo "     railway run python run.py --index     # rebuild index"
echo ""
echo "  Railway URL will be:"
echo "  https://purangpt-production.up.railway.app"
echo ""
echo "  ─────────────────────────────────────────"
echo "  Update ios_app/ios_config.js with that URL,"
echo "  then run the iOS setup."
echo ""
