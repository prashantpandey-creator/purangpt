"""
Workspace Document Ingestion Pipeline
======================================
Async pipeline: extract → chunk → embed → upsert into purana_verses.
Updates workspace_documents.status at each stage.

Called as a background task from the upload endpoint via asyncio.create_task().
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("purangpt.workspace_ingest")

VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "postgresql://postgres:postgres@localhost:5432/purangpt")
EMBED_BATCH_SIZE = 32
MAX_CHUNKS = 2000

# Serialize ingestion — one at a time on an 8GB VPS
_ingest_lock = asyncio.Lock()


async def _get_pool():
    """One-shot asyncpg pool for workspace DB ops."""
    import asyncpg
    return await asyncpg.create_pool(VECTOR_DB_URL, min_size=1, max_size=3)


async def update_doc_status(
    pool,
    doc_id: str,
    status: str,
    *,
    error_msg: str | None = None,
    chunk_count: int | None = None,
    section_count: int | None = None,
    title: str | None = None,
    thread_map: dict | None = None,
):
    sets = ["status = $2", "updated_at = NOW()"]
    params: list[Any] = [doc_id, status]
    idx = 3

    for field, val in [
        ("error_msg", error_msg),
        ("chunk_count", chunk_count),
        ("section_count", section_count),
        ("title", title),
    ]:
        if val is not None:
            sets.append(f"{field} = ${idx}")
            params.append(val)
            idx += 1

    if thread_map is not None:
        sets.append(f"thread_map = ${idx}::jsonb")
        params.append(json.dumps(thread_map))
        idx += 1

    sql = f"UPDATE workspace_documents SET {', '.join(sets)} WHERE doc_id = $1"
    await pool.execute(sql, *params)


def _get_embed_model():
    """Get the shared embedding model (already loaded by HybridSearcher)."""
    from indexer.search import HybridSearcher
    return HybridSearcher._shared_model or HybridSearcher.preload_model()


async def _embed_batch(model, texts: list[str]) -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, model.encode, texts)


async def _upsert_chunks(pool, chunks: list[dict], embeddings) -> None:
    """Batch upsert chunks + embeddings into purana_verses."""
    for chunk, emb in zip(chunks, embeddings):
        emb_list = emb.tolist() if hasattr(emb, "tolist") else list(emb)
        emb_str = "[" + ",".join(str(x) for x in emb_list) + "]"
        meta_json = json.dumps(chunk["metadata"])

        await pool.execute(
            """
            INSERT INTO purana_verses (id, content, metadata, embedding)
            VALUES ($1, $2, $3::jsonb, $4::vector)
            ON CONFLICT (id) DO UPDATE SET
                content = EXCLUDED.content,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding
            """,
            chunk["id"],
            chunk["text"],
            meta_json,
            emb_str,
        )


async def _generate_title(first_chunk_text: str) -> str:
    """Generate a short title from the first chunk using the LLM."""
    try:
        from backend.main import call_llm_once
        prompt = (
            "Generate a short title (max 8 words) for a document that begins with:\n\n"
            f"{first_chunk_text[:500]}\n\n"
            "Return ONLY the title, nothing else."
        )
        title = await call_llm_once(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return title.strip().strip('"').strip("'")[:100]
    except Exception as e:
        logger.warning("Title generation failed: %s", e)
        return ""


async def ingest_document(
    doc_id: str,
    file_path: Path | None,
    source_url: str | None,
    doc_type: str,
    user_id: str,
    filename: str,
) -> None:
    """
    Full ingestion pipeline. Runs as a background asyncio task.
    """
    pool = await _get_pool()
    try:
        async with _ingest_lock:
            await _run_pipeline(pool, doc_id, file_path, source_url, doc_type, user_id, filename)
    except Exception as e:
        logger.exception("Ingestion failed for %s: %s", doc_id, e)
        await update_doc_status(pool, doc_id, "failed", error_msg=str(e)[:500])
    finally:
        await pool.close()


async def _run_pipeline(
    pool,
    doc_id: str,
    file_path: Path | None,
    source_url: str | None,
    doc_type: str,
    user_id: str,
    filename: str,
) -> None:
    # ── Extract ───────────────────────────────────────────────────────────
    await update_doc_status(pool, doc_id, "extracting")
    logger.info("[%s] Extracting (%s)…", doc_id[:8], doc_type)

    if doc_type == "pdf":
        from data_pipeline.extractor import TextExtractor
        extractor = TextExtractor(lang="en", min_text_per_page=50)
        result = extractor.extract_pdf(file_path)
        pages = result.to_dict()["pages"]
    elif doc_type == "docx":
        from data_pipeline.extractor import extract_docx
        result = extract_docx(file_path)
        pages = result["pages"]
    elif doc_type == "url":
        from data_pipeline.extractor import extract_url
        result = extract_url(source_url)
        pages = result["pages"]
    else:
        raise ValueError(f"Unsupported doc_type: {doc_type}")

    if not pages:
        await update_doc_status(pool, doc_id, "failed", error_msg="No text extracted from document")
        return

    # ── Chunk ─────────────────────────────────────────────────────────────
    await update_doc_status(pool, doc_id, "chunking")
    logger.info("[%s] Chunking…", doc_id[:8])

    from data_pipeline.doc_chunker import chunk_document
    chunks = chunk_document(pages, doc_id, filename, user_id)

    if not chunks:
        await update_doc_status(pool, doc_id, "failed", error_msg="No chunks produced from document")
        return

    if len(chunks) > MAX_CHUNKS:
        logger.warning("[%s] Truncating %d chunks to %d", doc_id[:8], len(chunks), MAX_CHUNKS)
        chunks = chunks[:MAX_CHUNKS]

    section_count = max(c["metadata"]["chapter"] for c in chunks)

    # ── Embed + Upsert ────────────────────────────────────────────────────
    await update_doc_status(pool, doc_id, "embedding")
    logger.info("[%s] Embedding %d chunks…", doc_id[:8], len(chunks))

    model = _get_embed_model()

    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i:i + EMBED_BATCH_SIZE]
        texts = [f"passage: {c['text'][:1000]}" for c in batch]
        embeddings = await _embed_batch(model, texts)
        await _upsert_chunks(pool, batch, embeddings)
        logger.debug("[%s] Embedded batch %d/%d", doc_id[:8], i // EMBED_BATCH_SIZE + 1,
                     (len(chunks) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE)

    # ── Generate title ────────────────────────────────────────────────────
    title = await _generate_title(chunks[0]["text"])
    if not title:
        title = filename.rsplit(".", 1)[0][:80]

    # ── Mark ready ────────────────────────────────────────────────────────
    await update_doc_status(
        pool, doc_id, "ready",
        chunk_count=len(chunks),
        section_count=section_count,
        title=title,
    )
    logger.info("[%s] Ingestion complete: %d chunks, %d sections, title='%s'",
                doc_id[:8], len(chunks), section_count, title)
