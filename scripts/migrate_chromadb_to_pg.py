import os
import psycopg2
import psycopg2.extras
import chromadb
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

console = Console()

LOCAL_DB_URL = "postgresql://postgres:postgres@204.168.176.229:5432/purangpt"
TABLE_NAME = "purana_verses"
CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "purana_verses"

def main():
    console.print(f"[cyan]Connecting to local Postgres at {LOCAL_DB_URL}...[/cyan]")
    conn = psycopg2.connect(LOCAL_DB_URL)
    cur = conn.cursor()

    console.print("[cyan]Connecting to local ChromaDB...[/cyan]")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = chroma_client.get_collection(COLLECTION_NAME)

    total_chroma = col.count()
    console.print(f"[green]Found {total_chroma:,} total vectors in ChromaDB.[/green]")

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id TEXT PRIMARY KEY,
        content TEXT,
        metadata JSONB,
        embedding vector(384),
        fts tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
    );
    """)
    
    console.print(f"[yellow]Truncating {TABLE_NAME}...[/yellow]")
    cur.execute(f"TRUNCATE TABLE {TABLE_NAME};")
    conn.commit()

    console.print("[yellow]Fetching all IDs from ChromaDB...[/yellow]")
    # Fetching only IDs avoids the SQLite variable limits and memory bloat
    id_data = col.get(include=[])
    all_ids = id_data["ids"]
    num_records = len(all_ids)
    
    console.print(f"[green]Successfully fetched {num_records:,} IDs![/green]")

    BATCH_SIZE = 5000
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Migrating batches...", total=num_records)

        for i in range(0, num_records, BATCH_SIZE):
            batch_ids = all_ids[i:i+BATCH_SIZE]
            
            data = col.get(
                ids=batch_ids,
                include=["embeddings", "metadatas", "documents"]
            )
            
            args_list = []
            for j in range(len(data["ids"])):
                cid = data["ids"][j]
                doc = data["documents"][j]
                meta = data["metadatas"][j] if data["metadatas"] else {}
                emb = data["embeddings"][j]
                
                import html
                doc = html.unescape(doc)
                
                if hasattr(emb, "tolist"):
                    emb = emb.tolist()
                
                args_list.append((
                    cid, 
                    doc, 
                    psycopg2.extras.Json(meta), 
                    emb
                ))

            psycopg2.extras.execute_values(
                cur,
                f"INSERT INTO {TABLE_NAME} (id, content, metadata, embedding) VALUES %s ON CONFLICT (id) DO NOTHING",
                args_list
            )
            conn.commit()
            progress.update(task, advance=len(batch_ids))

    console.print(f"[green]Migration complete. {num_records:,} rows inserted![/green]")
    
    console.print("[cyan]Rebuilding vector index (hnsw)...[/cyan]")
    cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_embedding_idx ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops);")
    conn.commit()
    
    console.print("[green]Rebuilding FTS index (gin)...[/green]")
    cur.execute(f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_fts_idx ON {TABLE_NAME} USING GIN (fts);")
    conn.commit()

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
