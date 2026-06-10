import os
import json
import time
import logging
from typing import Dict, List
from datetime import datetime, timezone
from backend.supabase_client import get_supabase

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, max_history=100):
        self.max_history = max_history
        self._guest_sessions = {}
        self.guest_db_path = "data/guest_sessions.json"
        self._load_guest_sessions()

    def _load_guest_sessions(self):
        if os.path.exists(self.guest_db_path):
            try:
                with open(self.guest_db_path, "r", encoding="utf-8") as f:
                    self._guest_sessions = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load guest sessions: {e}")

    def _save_guest_sessions(self):
        os.makedirs(os.path.dirname(self.guest_db_path) or ".", exist_ok=True)
        try:
            with open(self.guest_db_path, "w", encoding="utf-8") as f:
                json.dump(self._guest_sessions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save guest sessions: {e}")

    def get_session(self, session_id: str, user_id: str = None, guest_id: str = None) -> dict:
        if not user_id:
            # Guest mode: use local persistent JSON
            session = self._guest_sessions.get(session_id)
            if session and session.get("guest_id") == guest_id:
                return session
            # If not found or guest_id mismatch, return a new one
            return {
                "id": session_id,
                "guest_id": guest_id,
                "title": "New Chat",
                "updated_at": time.time(),
                "history": []
            }
            
        supabase = get_supabase()
        if supabase:
            try:
                resp = supabase.table("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).execute()
                if resp.data:
                    data = resp.data[0]
                    updated_at = 0
                    if data.get("updated_at"):
                        try:
                            dt = datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
                            updated_at = dt.timestamp()
                        except: pass
                    return {
                        "id": data["id"],
                        "title": data.get("title", "New Chat"),
                        "updated_at": updated_at,
                        "history": data.get("messages", [])
                    }
            except Exception as e:
                logger.error(f"Error fetching session {session_id}: {e}")
                
        return {"id": session_id, "title": "New Chat", "updated_at": time.time(), "history": []}
        
    def save_session(self, session_id: str, data: dict, user_id: str = None, guest_id: str = None):
        data["updated_at"] = time.time()
        
        if not user_id:
            data["guest_id"] = guest_id
            self._guest_sessions[session_id] = data
            self._save_guest_sessions()
            return
            
        supabase = get_supabase()
        if supabase:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                supabase.table("chat_sessions").upsert({
                    "id": session_id,
                    "user_id": user_id,
                    "title": data.get("title", "New Chat"),
                    "messages": data.get("history", []),
                    "updated_at": now_iso
                }).execute()
            except Exception as e:
                logger.error(f"Error saving session {session_id}: {e}")

    def append_messages(self, session_id: str, messages: List[dict], user_id: str = None, guest_id: str = None):
        session = self.get_session(session_id, user_id, guest_id)
        
        if not session.get("history") and messages:
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "").strip()
                    title = content[:40] + ("..." if len(content) > 40 else "")
                    session["title"] = title
                    break
                    
        session["history"] = session.get("history", []) + messages
        if len(session["history"]) > self.max_history:
            session["history"] = session["history"][-self.max_history:]
            
        self.save_session(session_id, session, user_id, guest_id)
        return session
        
    def truncate_session(self, session_id: str, index: int, user_id: str = None, guest_id: str = None):
        session = self.get_session(session_id, user_id, guest_id)
        if "history" in session and 0 <= index <= len(session["history"]):
            session["history"] = session["history"][:index]
            self.save_session(session_id, session, user_id, guest_id)
        return session
        
    def clear_session(self, session_id: str, user_id: str = None, guest_id: str = None):
        if not user_id:
            if session_id in self._guest_sessions:
                if self._guest_sessions[session_id].get("guest_id") == guest_id:
                    del self._guest_sessions[session_id]
                    self._save_guest_sessions()
            return
            
        supabase = get_supabase()
        if supabase:
            try:
                supabase.table("chat_sessions").delete().eq("id", session_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.error(f"Error deleting session {session_id}: {e}")
            
    def get_all_sessions(self, user_id: str = None, guest_id: str = None) -> List[dict]:
        if not user_id:
            if not guest_id:
                return []
            sessions = []
            for sid, sdata in self._guest_sessions.items():
                if sdata.get("guest_id") == guest_id:
                    sessions.append({
                        "id": sid,
                        "title": sdata.get("title", "Chat"),
                        "updated_at": sdata.get("updated_at", 0)
                    })
            sessions.sort(key=lambda x: x["updated_at"], reverse=True)
            return sessions
            
        supabase = get_supabase()
        if supabase:
            try:
                resp = supabase.table("chat_sessions").select("id, title, updated_at").eq("user_id", user_id).order("updated_at", desc=True).execute()
                sessions = []
                for row in resp.data:
                    updated_at = 0
                    if row.get("updated_at"):
                        try:
                            dt = datetime.fromisoformat(row["updated_at"].replace('Z', '+00:00'))
                            updated_at = dt.timestamp()
                        except: pass
                    sessions.append({
                        "id": row["id"],
                        "title": row.get("title", "Chat"),
                        "updated_at": updated_at
                    })
                return sessions
            except Exception as e:
                logger.error(f"Error fetching all sessions for {user_id}: {e}")
        return []
