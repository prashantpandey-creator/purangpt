"""growth_engine — autonomous marketing/growth-automation app for PuranGPT.

A peer package of `backend/`. It generates marketing content (copy, images,
voiceover, faceless video) and publishes to channels where automation is
allowed, queueing drafts for risky channels (Reddit, reviews) for 1-click
human approval.

Design rule: this package REUSES the backend's infrastructure rather than
reinventing it —
  - LLM routing/failover: backend.main.{get_providers, stream_llm, call_llm_once}
  - encrypted key vault:   backend.db_client.{encrypt_keys, decrypt_keys}
  - pooled Postgres:       backend.db_client.get_db_conn
No provider-named streaming functions are ever introduced here (that pattern
caused recurring NameError crashes in the chat backend — see purangpt/CLAUDE.md).
"""

__all__ = ["__version__"]
__version__ = "0.0.1"
