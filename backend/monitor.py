import os
import time
try:
    import psutil
except ImportError:
    psutil = None
import httpx
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# To avoid circular imports or messy setups, we import clients directly
from backend.supabase_client import get_supabase
from backend.pinecone_client import get_pinecone_index

async def ping_llm(provider: str, api_key: str) -> dict:
    """Send a tiny test request to an LLM provider to measure latency and status."""
    if not api_key:
        return {"status": "unconfigured", "latency_ms": 0, "message": "Missing API Key"}
        
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "groq":
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "llama3-8b-8192", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
                )
            elif provider == "together":
                r = await client.post(
                    "https://api.together.xyz/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "meta-llama/Meta-Llama-3-8B-Instruct", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
                )
            elif provider == "deepseek":
                r = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
                )
            else:
                return {"status": "unsupported", "latency_ms": 0}

            r.raise_for_status()
            latency = int((time.time() - start_time) * 1000)
            return {"status": "healthy", "latency_ms": latency}
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {"status": "down", "latency_ms": latency, "message": str(e)}

async def run_health_checks(active_sessions: int = 0) -> dict:
    """Run all health checks and return the aggregated data."""
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {},
        "database": {},
        "vector_db": {},
        "llms": {},
        "sessions": {}
    }

    # 1. System Metrics (psutil)
    try:
        if psutil:
            results["system"] = {
                "status": "healthy",
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "ram_percent": psutil.virtual_memory().percent,
                "ram_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
                "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2)
            }
        else:
            results["system"] = {"status": "unsupported", "error": "psutil not installed"}
    except Exception as e:
        results["system"] = {"status": "degraded", "error": str(e)}

    # 2. Supabase
    start_time = time.time()
    try:
        supabase = get_supabase()
        if supabase:
            # simple ping query
            supabase.table("profiles").select("id").limit(1).execute()
            results["database"] = {
                "status": "healthy",
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        else:
            results["database"] = {"status": "unconfigured", "latency_ms": 0}
    except Exception as e:
        results["database"] = {
            "status": "down",
            "latency_ms": int((time.time() - start_time) * 1000),
            "error": str(e)
        }

    # 3. Pinecone
    start_time = time.time()
    try:
        index = get_pinecone_index()
        if index:
            stats = index.describe_index_stats()
            results["vector_db"] = {
                "status": "healthy",
                "latency_ms": int((time.time() - start_time) * 1000),
                "total_vectors": stats.get("total_vector_count", 0)
            }
        else:
            results["vector_db"] = {"status": "unconfigured", "latency_ms": 0}
    except Exception as e:
        results["vector_db"] = {
            "status": "down",
            "latency_ms": int((time.time() - start_time) * 1000),
            "error": str(e)
        }

    # 4. LLMs
    groq_key = os.getenv("GROQ_API_KEY")
    together_key = os.getenv("TOGETHER_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    results["llms"]["groq"] = await ping_llm("groq", groq_key)
    results["llms"]["together"] = await ping_llm("together", together_key)
    results["llms"]["deepseek"] = await ping_llm("deepseek", deepseek_key)

    results["sessions"] = {
        "status": "healthy",
        "active_count": active_sessions
    }

    return results
