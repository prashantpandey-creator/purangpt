import sys, os
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv(".env")
sys.path.insert(0, os.path.abspath("."))
from backend.supabase_client import get_supabase

supabase = get_supabase()
try:
    res = supabase.table("profiles").insert({"id": "00000000-0000-0000-0000-000000000000", "role": "guest"}).execute()
    print("Success:", res)
    supabase.table("profiles").delete().eq("id", "00000000-0000-0000-0000-000000000000").execute()
except Exception as e:
    print("Error:", e)
