#!/bin/bash
# PuranGPT Next.js watchdog — restarts the dev server if it stops responding
# Run:        bash scripts/watchdog.sh
# Background: nohup bash scripts/watchdog.sh > /tmp/watchdog.log 2>&1 &

PORT=3001
DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="/tmp/purangpt-next.watchdog.log"
CHECK_INTERVAL=30
MAX_FAILURES=2

failures=0
server_pid=""

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

start_server() {
  log "Starting Next.js dev server on :$PORT..."
  cd "$DIR"
  npm run dev -- --port $PORT >> /tmp/purangpt-next.out.log 2>&1 &
  server_pid=$!
  log "Server started with PID $server_pid"
  sleep 8
}

stop_server() {
  if [ -n "$server_pid" ] && kill -0 "$server_pid" 2>/dev/null; then
    log "Stopping server PID $server_pid..."
    kill "$server_pid" 2>/dev/null
    sleep 2
  fi
  lsof -ti:$PORT 2>/dev/null | xargs kill -9 2>/dev/null
  sleep 1
}

is_healthy() {
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://localhost:$PORT/")
  [ "$code" = "200" ]
}

start_server
log "Watchdog running. Checking every ${CHECK_INTERVAL}s. Watchdog PID $$"

while true; do
  sleep "$CHECK_INTERVAL"
  if ! kill -0 "$server_pid" 2>/dev/null; then
    log "Server process died. Restarting..."
    start_server; failures=0; continue
  fi
  if is_healthy; then
    failures=0
  else
    failures=$((failures + 1))
    log "Health check failed ($failures/$MAX_FAILURES)..."
    if [ "$failures" -ge "$MAX_FAILURES" ]; then
      log "Server frozen — force restarting..."
      stop_server; start_server; failures=0
    fi
  fi
done
