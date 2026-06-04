import os
import json
import time
from typing import Dict, List
import logging
from datetime import datetime, timezone
from backend.supabase_client import get_supabase

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, max_history=100):
        self.max_history = max_history
        self._guest_sessions = {} # In-memory storage for guests

    def get_session(self, session_id: str, user_id: str = None) -> dict:
        """Returns the full session object."""
        if not user_id:
            # Guest mode: use in-memory
            return self._guest_sessions.get(session_id, {
                "id": session_id,
                "title": "New Chat",
                "updated_at": time.time(),
                "history": []
            })
            
        supabase = get_supabase()
        if supabase:
            try:
                resp = supabase.table("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).execute()
                if resp.data:
                    data = resp.data[0]
                    # Parse timestamp
                    updated_at = 0
                    if data.get("updated_at"):
                        try:
                            dt = datetime.fromisoformat(data["updated_at"].replace('Z', '+00:00'))
                            updated_at = dt.timestamp()
                        except:
                            pass
                            
                    return {
                        "id": data["id"],
                        "title": data.get("title", "New Chat"),
                        "updated_at": updated_at,
                        "history": data.get("messages", [])
                    }
            except Exception as e:
                logger.error(f"Error fetching session {session_id}: {e}")
                
        return {"id": session_id, "title": "New Chat", "updated_at": time.time(), "history": []}
        
    def save_session(self, session_id: str, data: dict, user_id: str = None):
        """Saves the session object."""
        data["updated_at"] = time.time()
        
        if not user_id:
            self._guest_sessions[session_id] = data
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
                # Fallback to local memory if DB fails
                self._guest_sessions[session_id] = data

    def append_messages(self, session_id: str, messages: List[dict], user_id: str = None):
        """Appends messages to the session and automatically generates a title if it's new."""
        session = self.get_session(session_id, user_id)
        
        if not session["history"] and messages:
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "").strip()
                    title = content[:40] + ("..." if len(content) > 40 else "")
                    session["title"] = title
                    break
                    
        session["history"].extend(messages)
        
        if len(session["history"]) > self.max_history:
            session["history"] = session["history"][-self.max_history:]
            
        self.save_session(session_id, session, user_id)
        return session
        
    def truncate_session(self, session_id: str, index: int, user_id: str = None):
        """Truncates the session history to keep only messages up to the given index (exclusive)."""
        session = self.get_session(session_id, user_id)
        if 0 <= index <= len(session["history"]):
            session["history"] = session["history"][:index]
            self.save_session(session_id, session, user_id)
        return session
        
    def clear_session(self, session_id: str, user_id: str = None):
        if not user_id:
            if session_id in self._guest_sessions:
                del self._guest_sessions[session_id]
            return
            
        supabase = get_supabase()
        if supabase:
            try:
                supabase.table("chat_sessions").delete().eq("id", session_id).eq("user_id", user_id).execute()
            except Exception as e:
                logger.error(f"Error deleting session {session_id}: {e}")
            
    def get_all_sessions(self, user_id: str = None) -> List[dict]:
        """Returns a list of all sessions sorted by updated_at (newest first)."""
        if not user_id:
            # Guests don't get session history list persisted
            return []
            
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
                        except:
                            pass
                    sessions.append({
                        "id": row["id"],
                        "title": row.get("title", "Chat"),
                        "updated_at": updated_at
                    })
                return sessions
            except Exception as e:
                logger.error(f"Error fetching all sessions for {user_id}: {e}")
        return []
