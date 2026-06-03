import os
import json
import time
from pathlib import Path
from typing import Dict, List

SESSIONS_DIR = Path("./data/sessions")

class SessionManager:
    def __init__(self, max_history=100):
        self.max_history = max_history
        os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    def _get_path(self, session_id: str) -> Path:
        # Sanitize session_id to prevent directory traversal
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        if not safe_id:
            safe_id = "default"
        return SESSIONS_DIR / f"{safe_id}.json"
        
    def get_session(self, session_id: str) -> dict:
        """Returns the full session object, or an empty template if it doesn't exist."""
        path = self._get_path(session_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"id": session_id, "title": "New Chat", "updated_at": time.time(), "history": []}
        
    def save_session(self, session_id: str, data: dict):
        """Saves the session object to disk."""
        data["updated_at"] = time.time()
        path = self._get_path(session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def append_messages(self, session_id: str, messages: List[dict]):
        """Appends messages to the session and automatically generates a title if it's new."""
        session = self.get_session(session_id)
        
        # If this is a brand new session and we are adding user messages, use the first user query as title
        if not session["history"] and messages:
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "").strip()
                    title = content[:40] + ("..." if len(content) > 40 else "")
                    session["title"] = title
                    break
                    
        session["history"].extend(messages)
        
        # Enforce max history limit
        if len(session["history"]) > self.max_history:
            session["history"] = session["history"][-self.max_history:]
            
        self.save_session(session_id, session)
        return session
        
    def truncate_session(self, session_id: str, index: int):
        """Truncates the session history to keep only messages up to the given index (exclusive)."""
        session = self.get_session(session_id)
        if 0 <= index <= len(session["history"]):
            session["history"] = session["history"][:index]
            self.save_session(session_id, session)
        return session
        
    def clear_session(self, session_id: str):
        path = self._get_path(session_id)
        if path.exists():
            path.unlink()
            
    def get_all_sessions(self) -> List[dict]:
        """Returns a list of all sessions sorted by updated_at (newest first)."""
        sessions = []
        for path in SESSIONS_DIR.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "id": data.get("id", path.stem),
                        "title": data.get("title", "Chat"),
                        "updated_at": data.get("updated_at", 0)
                    })
            except Exception:
                continue
        # Sort by updated_at descending
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions
