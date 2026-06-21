"""
PuranGPT — Postgres PGVector Index Builder
Builds the vector and FTS index in PostgreSQL using pgvector.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

import psycopg2
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from sentence_transformers import SentenceTransformer

logger  = logging.getLogger(__name__)
console = Console()

DEFAULT_EMBED_MODEL  = "intfloat/multilingual-e5-small"
TABLE_NAME           = "purana_verses"
EMBED_BATCH_SIZE     = 32

class PostgresIndexer:
    def __init__(self, db_url: str, model_name: str = DEFAULT_EMBED_MODEL):
        self.db_url = db_url
        self.model_name = model_name
        
        console.print(f"[bold cyan]Loading SentenceTransformer:[/] {self.model_name}")
        self.model = SentenceTransformer(self.model_name, trust_remote_code=True)
        
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = True
        
        self._init_db()

    def _init_db(self):
        console.print("[bold cyan]Initializing PostgreSQL schema & pgvector...[/]")
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    embedding vector(384)
                );
            """)
            # Create HNSW index for fast vector search
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx 
                ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops);
            """)
            # Create GIN index for full text search
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS {TABLE_NAME}_fts_idx 
                ON {TABLE_NAME} USING GIN (to_tsvector('english', content));
            """)
            
            # Create hybrid_search function.
            # Uses 'simple' text search config (not 'english') so Sanskrit transliterated
            # terms (narada, vishnu, dharma) match without being stemmed/stop-word-dropped.
            # semantic_weight is passed as a parameter (0.0–1.0); keyword weight = 1 - it.
            cur.execute(f"""
                CREATE OR REPLACE FUNCTION hybrid_search(
                    search_query TEXT,
                    query_embedding vector(384),
                    match_count INT,
                    filter_metadata JSONB DEFAULT '{{}}'::jsonb,
                    semantic_weight FLOAT DEFAULT 0.7
                )
                RETURNS TABLE (
                    id TEXT,
                    content TEXT,
                    metadata JSONB,
                    similarity FLOAT
                )
                LANGUAGE plpgsql
                AS $$
                DECLARE
                    kw_weight FLOAT := GREATEST(0.0, LEAST(1.0, 1.0 - semantic_weight));
                    sem_weight FLOAT := GREATEST(0.0, LEAST(1.0, semantic_weight));
                BEGIN
                    RETURN QUERY
                    WITH semantic_search AS (
                        SELECT
                            v.id,
                            v.content,
                            v.metadata,
                            1 - (v.embedding <=> query_embedding) AS semantic_sim
                        FROM {TABLE_NAME} v
                        WHERE v.metadata @> filter_metadata
                        ORDER BY v.embedding <=> query_embedding
                        LIMIT match_count * 2
                    ),
                    keyword_search AS (
                        SELECT
                            v.id,
                            v.content,
                            v.metadata,
                            ts_rank_cd(to_tsvector('simple', v.content), websearch_to_tsquery('simple', search_query)) AS keyword_sim
                        FROM {TABLE_NAME} v
                        WHERE v.metadata @> filter_metadata
                          AND to_tsvector('simple', v.content) @@ websearch_to_tsquery('simple', search_query)
                        ORDER BY keyword_sim DESC
                        LIMIT match_count * 2
                    )
                    SELECT
                        COALESCE(ss.id, ks.id) as id,
                        COALESCE(ss.content, ks.content) as content,
                        COALESCE(ss.metadata, ks.metadata) as metadata,
                        (COALESCE(ss.semantic_sim, 0.0) * sem_weight + COALESCE(ks.keyword_sim, 0.0) * kw_weight) AS similarity
                    FROM semantic_search ss
                    FULL OUTER JOIN keyword_search ks ON ss.id = ks.id
                    ORDER BY similarity DESC
                    LIMIT match_count;
                END;
                $$;
            """)

    def build(self, chunks_dir: Path):
        jsonl_files = list(chunks_dir.glob("*.jsonl"))
        if not jsonl_files:
            console.print(f"[bold red]No .jsonl files found in {chunks_dir}[/]")
            return

        console.print(f"[bold cyan]Found {len(jsonl_files)} JSONL files to process.[/]")

        for file_path in jsonl_files:
            console.print(f"\n[bold yellow]Processing:[/] {file_path.name}")
            self._process_file(file_path)

    def _process_file(self, file_path: Path):
        chunks = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                data = json.loads(line)
                # Fallbacks for legacy fields
                if "id" not in data:
                    data["id"] = data.get("chunk_id", data.get("metadata", {}).get("chunk_id", str(hash(line))))
                if "text" not in data and "content" in data:
                    data["text"] = data["content"]
                chunks.append(data)

        if not chunks:
            return

        texts = []
        for c in chunks:
            text = c.get("text", "")
            if len(text) > 1000:
                text = text[:1000]
            # multilingual-e5 requires "passage: " prefix
            texts.append(f"passage: {text}")

        total_batches = (len(texts) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TimeElapsedColumn(), console=console) as progress:
            task = progress.add_task(f"Embedding & Inserting {file_path.name}", total=total_batches)

            for i in range(0, len(texts), EMBED_BATCH_SIZE):
                batch_chunks = chunks[i:i+EMBED_BATCH_SIZE]
                batch_texts  = texts[i:i+EMBED_BATCH_SIZE]
                
                embeddings = self.model.encode(batch_texts)
                
                records = []
                for chunk, emb in zip(batch_chunks, embeddings):
                    chunk_id = chunk["id"]
                    content = chunk["text"]
                    meta = chunk.get("metadata", {})
                    meta_json = json.dumps(meta)
                    emb_list = emb.tolist() if hasattr(emb, "tolist") else emb
                    emb_str = "[" + ",".join(map(str, emb_list)) + "]"
                    records.append((chunk_id, content, meta_json, emb_str))
                
                with self.conn.cursor() as cur:
                    # Upsert
                    args_str = ','.join(cur.mogrify("(%s,%s,%s,%s::vector)", r).decode('utf-8') for r in records)
                    cur.execute(f"""
                        INSERT INTO {TABLE_NAME} (id, content, metadata, embedding)
                        VALUES {args_str}
                        ON CONFLICT (id) DO UPDATE SET 
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                    """)
                
                progress.advance(task)

def main():
    parser = argparse.ArgumentParser(description="Build PGVector Index")
    parser.add_argument("--chunks-dir", type=str, default="data/chunks", help="Directory containing JSONL chunks")
    parser.add_argument("--model", type=str, default=DEFAULT_EMBED_MODEL, help="HuggingFace model to use")
    args = parser.parse_args()

    db_url = os.getenv("VECTOR_DB_URL")
    if not db_url:
        console.print("[bold red]VECTOR_DB_URL is not set. Please set it to the pgvector connection string.[/]")
        return

    indexer = PostgresIndexer(db_url, args.model)
    indexer.build(Path(args.chunks_dir))
    console.print("\n[bold green]Index build complete! 🕉️[/]")

if __name__ == "__main__":
    main()
