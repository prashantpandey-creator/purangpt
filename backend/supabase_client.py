import os
import json
from datetime import datetime, timezone
from supabase import create_client, Client
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

# Supabase Initialization
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

_supabase: Client = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            logger.warning("Supabase credentials not found. Auth will not work.")
            return None
        _supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase

# Encryption for BYOK Keys
FERNET_KEY = os.getenv("FERNET_KEY", "")
if not FERNET_KEY:
    FERNET_KEY = Fernet.generate_key().decode()
    logger.warning(f"FERNET_KEY not set. Generated ephemeral key: {FERNET_KEY}")
fernet = Fernet(FERNET_KEY.encode())

def encrypt_keys(keys_dict: dict) -> str:
    """Encrypts a dictionary of API keys."""
    json_str = json.dumps(keys_dict)
    encrypted = fernet.encrypt(json_str.encode())
    return encrypted.decode()

def decrypt_keys(encrypted_str: str) -> dict:
    """Decrypts an encrypted string of API keys."""
    if not encrypted_str:
        return {}
    try:
        decrypted = fernet.decrypt(encrypted_str.encode())
        return json.loads(decrypted.decode())
    except Exception as e:
        logger.error(f"Error decrypting BYOK keys: {e}")
        return {}

def get_profile(user_id: str) -> dict:
    """Fetch user profile from Supabase."""
    supabase = get_supabase()
    if not supabase: return None
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logger.error(f"Error fetching profile for {user_id}: {e}")
    return None

def update_profile(user_id: str, data: dict):
    """Update user profile in Supabase."""
    supabase = get_supabase()
    if not supabase: return
    try:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        supabase.table("profiles").update(data).eq("id", user_id).execute()
    except Exception as e:
        logger.error(f"Error updating profile for {user_id}: {e}")

def check_rate_limit(user_id: str, role: str) -> tuple[bool, int]:
    """Check if the user has exceeded their daily message limit."""
    if role in ["pro", "scholar", "admin"]:
        return True, 999999
        
    profile = get_profile(user_id)
    if not profile:
        return False, 0
        
    limit = 30 if role == "free" else 10 # Default fallback
    
    # Check if we need to reset the daily count
    last_reset = profile.get("daily_reset_at")
    try:
        last_reset_dt = datetime.fromisoformat(last_reset.replace('Z', '+00:00')) if last_reset else datetime.min.replace(tzinfo=timezone.utc)
    except:
        last_reset_dt = datetime.min.replace(tzinfo=timezone.utc)
        
    now = datetime.now(timezone.utc)
    if now.date() > last_reset_dt.date():
        # Reset count
        supabase = get_supabase()
        supabase.table("profiles").update({
            "daily_message_count": 0,
            "daily_reset_at": now.isoformat()
        }).eq("id", user_id).execute()
        return True, limit
        
    count = profile.get("daily_message_count", 0)
    return count < limit, limit - count

def increment_usage(user_id: str, session_id: str = None, model: str = None):
    """Increment the user's daily message count and log the usage."""
    supabase = get_supabase()
    if not supabase: return
    
    # 1. Increment daily count in profile
    try:
        # We can't do an atomic increment easily via REST without RPC, so we fetch and update.
        # For a low-traffic app, this is acceptable.
        profile = get_profile(user_id)
        if profile:
            new_count = profile.get("daily_message_count", 0) + 1
            supabase.table("profiles").update({"daily_message_count": new_count}).eq("id", user_id).execute()
    except Exception as e:
        logger.error(f"Error incrementing usage for {user_id}: {e}")
        
    # 2. Add to usage_logs
    try:
        supabase.table("usage_logs").insert({
            "user_id": user_id,
            "session_id": session_id,
            "model_used": model
        }).execute()
    except Exception as e:
        logger.error(f"Error logging usage for {user_id}: {e}")

def get_admin_stats() -> dict:
    """Fetch analytics for the admin dashboard."""
    supabase = get_supabase()
    if not supabase: return {}
    try:
        # Very basic stats due to REST limitations (normally use RPC or raw SQL)
        users_resp = supabase.table("profiles").select("id", count="exact").execute()
        pro_resp = supabase.table("profiles").select("id", count="exact").in_("role", ["pro", "scholar"]).execute()
        
        # Today's messages
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        usage_resp = supabase.table("usage_logs").select("id", count="exact").gte("created_at", today_start).execute()
        
        return {
            "total_users": users_resp.count if hasattr(users_resp, 'count') else 0,
            "paid_users": pro_resp.count if hasattr(pro_resp, 'count') else 0,
            "messages_today": usage_resp.count if hasattr(usage_resp, 'count') else 0
        }
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        return {}

def get_all_users() -> list:
    """Fetch all users for admin dashboard."""
    supabase = get_supabase()
    if not supabase: return []
    try:
        resp = supabase.table("profiles").select("*").order("created_at", desc=True).limit(100).execute()
        return resp.data
    except Exception as e:
        logger.error(f"Error fetching all users: {e}")
        return []
