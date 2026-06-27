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
from backend.db_client import get_db_conn

async def ping_llm(provider: str, api_key: str) -> dict:
    """Send a tiny test request to DeepSeek (the sole provider) to measure latency."""
    if not api_key:
        return {"status": "unconfigured", "latency_ms": 0, "message": "Missing API Key"}

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider == "deepseek":
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

    # 2. Postgres
    start_time = time.time()
    try:
        conn = get_db_conn()
        if conn:
            try:
                # simple ping query
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM profiles LIMIT 1")
                    cur.fetchone()
                results["database"] = {
                    "status": "healthy",
                    "latency_ms": int((time.time() - start_time) * 1000)
                }
            finally:
                conn.close()
        else:
            results["database"] = {"status": "unconfigured", "latency_ms": 0}
    except Exception as e:
        results["database"] = {
            "status": "down",
            "latency_ms": int((time.time() - start_time) * 1000),
            "error": str(e)
        }

    # 3. pgvector verse count
    start_time = time.time()
    try:
        conn = get_db_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM purana_verses")
                    total_verses = cur.fetchone()[0]
                results["vector_db"] = {
                    "status": "healthy",
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "total_verses": total_verses
                }
            finally:
                conn.close()
        else:
            results["vector_db"] = {"status": "unconfigured", "latency_ms": 0}
    except Exception as e:
        results["vector_db"] = {
            "status": "down",
            "latency_ms": int((time.time() - start_time) * 1000),
            "error": str(e)
        }

    # 4. LLM (DeepSeek — sole provider)
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    results["llms"]["deepseek"] = await ping_llm("deepseek", deepseek_key)

    results["sessions"] = {
        "status": "healthy",
        "active_count": active_sessions
    }

    return results
