"""DB adapter — thin re-export of the backend's pooled Postgres connection.

growth_engine never opens its own connection pool. It borrows the existing
ThreadedConnectionPool in backend.db_client so the shared logto-db connection
budget is respected (see the pool-exhaustion note in db_client.py).
"""

from backend.db_client import get_db_conn  # noqa: F401  (re-exported)

__all__ = ["get_db_conn"]
