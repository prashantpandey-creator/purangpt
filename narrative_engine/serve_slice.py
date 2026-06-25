"""serve_slice — a zero-dependency server for the web vertical slice.

The full backend (backend/main.py) needs Postgres + LLM keys to boot. The game
slice needs none of that — only the graph files and the narrative engine. This
mounts JUST the /api/game/* router plus CORS for the browser client, so a person
can run the playable Ayodhya with one command and no setup.

    venv/bin/python -m narrative_engine.serve_slice      # :8000
    # then open the web client (served on :3000) in a browser

It also serves the web client itself at / so a single process runs everything.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from narrative_engine.api import router as game_router

app = FastAPI(title="THE AWAKENER — vertical slice")

# the browser client calls us from the same origin (served below) or :3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # local dev slice only — wide open is fine here
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(game_router)

# serve the web client (index.html etc.) at the root, if present
_WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
if os.path.isdir(_WEB_DIR):
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")


def main():
    import uvicorn
    port = int(os.getenv("SLICE_PORT", "8000"))
    print(f"\n  THE AWAKENER — vertical slice")
    print(f"  brain + client on http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
