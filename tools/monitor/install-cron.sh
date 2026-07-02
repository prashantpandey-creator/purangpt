#!/bin/bash
# Install the PuranGPT monitor as a cron job on the production server.
# Run as root on the Hetzner VPS (204.168.176.229).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_FILE="/var/log/purangpt-metrics.jsonl"

# ── Cron entry: every 15 minutes ─────────────────────────────────────────
CRON_JOB="*/15 * * * * cd $PROJECT_DIR && venv/bin/python -m tools.monitor.check --json >> $LOG_FILE 2>&1"

if crontab -l 2>/dev/null | grep -q "tools.monitor.check"; then
    echo "Monitor cron already installed. Updating..."
    crontab -l 2>/dev/null | grep -v "tools.monitor.check" | crontab -
fi

(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
echo "✓ Monitor cron installed (every 15 min → $LOG_FILE)"

# ── Run once now to verify ──────────────────────────────────────────────
echo "Running first check..."
cd "$PROJECT_DIR" && venv/bin/python -m tools.monitor.check --json >> "$LOG_FILE" 2>&1
echo "✓ First metric written"
tail -1 "$LOG_FILE"
