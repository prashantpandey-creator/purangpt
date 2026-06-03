"""
PuranGPT — Index Builder
Builds the vector (ChromaDB) and keyword (BM25) indexes from chunked JSONL files.

Usage:
    python indexer/build_index.py
    python indexer/build_index.py --chunks-dir data/chunks --db-dir data/chroma_db --model intfloat/multilingual-e5-small
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from sentence_transformers import SentenceTransformer

logger  = logging.getLogger(__name__)
console = Console()

# ── Config ─────────────────────────────────────────────────────────────────

# multilingual-e5-large: highest quality but ~2GB model
# multilingual-e5-small: fast and small, still multilingual — good for dev/test
DEFAULT_EMBED_MODEL  = "intfloat/multilingual-e5-large"
COLLECTION_NAME      = "purana_verses"
EMBED_BATCH_SIZE     = 32   # Reduce if running out of RAM
MAX_TEXT_LENGTH      = 1000 # Truncate very long chunks for embedding


# ── EmbeddingIndexer ───────────────────────────────────────────────────────

class EmbeddingIndexer:
    """
    Builds and populates the dual search index:
    1. ChromaDB — dense vector index using multilingual sentence embeddings
    2. BM25     — sparse keyword index for exact term matching
    """

    def __init__(
        self,
        chunks_dir:    str | Path = "data/chunks",
        db_dir:        str | Path = "data/chroma_db",
        index_dir:     str | Path = "data/indexes",
        embed_model:   str        = DEFAULT_EMBED_MODEL,
        collection:    str        = COLLECTION_NAME,
        batch_size:    int        = EMBED_BATCH_SIZE,
    ) -> None:
        self.chunks_dir   = Path(chunks_dir)
        self.db_dir       = Path(db_dir)
        self.index_dir    = Path(index_dir)
        self.embed_model  = embed_model
        self.collection   = collection
        self.batch_size   = batch_size

        self._model:       SentenceTransformer | None = None
        self._chroma:      chromadb.ClientAPI | None  = None
        self._col:         chromadb.Collection | None = None

    # ── Setup ──────────────────────────────────────────────────────────

    def _load_model(self) -> SentenceTransformer:
        """Load the multilingual sentence embedding model."""
        if self._model is None:
            console.print(f"[cyan]Loading embedding model:[/cyan] {self.embed_model}")
            console.print("  (First run downloads ~1-2 GB — subsequent runs use cache)")
            self._model = SentenceTransformer(self.embed_model)
            console.print(f"[green]✓[/green] Model loaded")
        return self._model

    def _get_collection(self) -> chromadb.Collection:
        """Get or create the ChromaDB collection."""
        if self._chroma is None:
            self.db_dir.mkdir(parents=True, exist_ok=True)
            self._chroma = chromadb.PersistentClient(
                path=str(self.db_dir),
                settings=Settings(anonymized_telemetry=False),
            )
        if self._col is None:
            self._col = self._chroma.get_or_create_collection(
                name=self.collection,
                metadata={"hnsw:space": "cosine"},
            )
        return self._col

    # ── Chunk Loading ─────────────────────────────────────────────────

    # Derived/aggregate files that merely concatenate the per-text JSONL files.
    # Loading these alongside the per-text files double-counts every chunk, which
    # inflates the BM25 corpus, skews IDF, and produces duplicate search results.
    DERIVED_FILES = {
        "all_chunks.jsonl",            # concatenation of the per-text files
        "shailendra_sharma_mock.jsonl",  # placeholder/mock data — never index
    }

    def _load_chunks(self) -> list[dict[str, Any]]:
        """
        Load all chunks from the per-text JSONL files in chunks_dir.

        Two coherence safeguards:
          1. Skip derived aggregate files (e.g. all_chunks.jsonl) — they duplicate
             the per-text files.
          2. Deduplicate by chunk id (keep first occurrence) as a belt-and-braces
             guard against any remaining overlap.
        """
        all_chunks: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        dup_count = 0

        jsonl_files = sorted(self.chunks_dir.glob("*.jsonl"))
        # Load per-text files first; skip derived aggregates entirely.
        jsonl_files = [p for p in jsonl_files if p.name not in self.DERIVED_FILES]

        if not jsonl_files:
            console.print(f"[yellow]No JSONL files found in {self.chunks_dir}[/yellow]")
            console.print("Run the chunker first: python run.py --chunk")
            return []

        console.print(f"[cyan]Loading chunks from {len(jsonl_files)} JSONL files…[/cyan]")

        for path in jsonl_files:
            count_before = len(all_chunks)
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.debug("Skipping bad JSON in %s: %s", path.name, e)
                        continue
                    cid = chunk.get("id")
                    # Validate required fields
                    if not (chunk.get("text") and cid):
                        continue
                    if cid in seen_ids:
                        dup_count += 1
                        continue
                    seen_ids.add(cid)
                    all_chunks.append(chunk)
            count = len(all_chunks) - count_before
            console.print(f"  {path.name}: [green]{count:,}[/green] chunks")

        if dup_count:
            console.print(f"[yellow]Skipped {dup_count:,} duplicate chunk ids[/yellow]")
        console.print(f"\n[bold]Total unique chunks:[/bold] {len(all_chunks):,}\n")
        return all_chunks

    # ── ChromaDB Indexing ─────────────────────────────────────────────

    def _get_existing_ids(self) -> set[str]:
        """Get IDs already in ChromaDB (for resume support)."""
        col = self._get_collection()
        try:
            existing = col.get(include=[])
            return set(existing.get("ids", []))
        except Exception:
            return set()

    def build_vector_index(self, chunks: list[dict[str, Any]]) -> int:
        """
        Embed chunks and store in ChromaDB.
        Skips chunks already in the collection (resume support).
        Returns number of newly indexed chunks.
        """
        col   = self._get_collection()
        model = self._load_model()

        existing_ids = self._get_existing_ids()
        new_chunks   = [c for c in chunks if c.get("id") not in existing_ids]

        if not new_chunks:
            console.print("[dim]All chunks already in ChromaDB — nothing to index[/dim]")
            return 0

        console.print(f"[cyan]Embedding {len(new_chunks):,} new chunks in batches of {self.batch_size}…[/cyan]")

        indexed_count = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Indexing…", total=len(new_chunks))

            for i in range(0, len(new_chunks), self.batch_size):
                batch = new_chunks[i : i + self.batch_size]

                # Prepare texts (multilingual-e5 needs "query: " / "passage: " prefix)
                texts = [
                    "passage: " + c.get("text", "")[:MAX_TEXT_LENGTH]
                    for c in batch
                ]
                ids   = [c["id"] for c in batch]
                metas = [self._chunk_to_metadata(c) for c in batch]

                # Generate embeddings
                embeddings = model.encode(
                    texts,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                ).tolist()

                # Upsert to ChromaDB
                col.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=[c.get("text", "") for c in batch],
                    metadatas=metas,
                )

                indexed_count += len(batch)
                progress.update(task, advance=len(batch))

        console.print(f"[green]✓[/green] Indexed {indexed_count:,} chunks into ChromaDB")
        return indexed_count

    def prune_vector_index(self, chunks: list[dict[str, Any]]) -> int:
        """
        Remove vectors from ChromaDB whose ids are no longer in the current corpus.

        Without this, deleting or renaming a chunk file leaves orphaned vectors in
        the collection (upsert only adds/updates, it never removes). This is what
        kept the `mock-shailendra-*` placeholders retrievable after they were taken
        out of the source data. Returns the number of vectors deleted.
        """
        col = self._get_collection()
        corpus_ids = {c["id"] for c in chunks if c.get("id")}
        existing_ids = self._get_existing_ids()
        stale = sorted(existing_ids - corpus_ids)

        if not stale:
            console.print("[dim]No stale vectors to prune[/dim]")
            return 0

        console.print(f"[yellow]Pruning {len(stale):,} stale vectors from ChromaDB…[/yellow]")
        # Delete in batches to stay well within ChromaDB limits.
        for i in range(0, len(stale), 500):
            col.delete(ids=stale[i : i + 500])
        console.print(f"[green]✓[/green] Pruned {len(stale):,} stale vectors")
        if len(stale) <= 20:
            console.print(f"  removed: {', '.join(stale)}")
        return len(stale)

    def _chunk_to_metadata(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Convert a chunk dict to ChromaDB-compatible metadata (string values only)."""
        meta: dict[str, Any] = {}
        str_fields = ["id", "purana", "book_section", "verse_range",
                      "language", "source_file", "category"]
        int_fields = ["chapter", "source_page", "word_count"]

        for field in str_fields:
            val = chunk.get(field)
            if val is not None:
                meta[field] = str(val)

        for field in int_fields:
            val = chunk.get(field)
            if val is not None:
                try:
                    meta[field] = int(val)
                except (ValueError, TypeError):
                    meta[field] = 0

        return meta

    # ── BM25 Indexing ─────────────────────────────────────────────────

    def build_bm25_index(self, chunks: list[dict[str, Any]]) -> int:
        """
        Build BM25 sparse keyword index over all chunks.
        Saves:
          - data/indexes/bm25_index.pkl  — the BM25Okapi object
          - data/indexes/chunk_map.json  — mapping from index position → chunk dict
        """
        self.index_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[cyan]Building BM25 index over {len(chunks):,} chunks…[/cyan]")

        # Tokenize all texts
        tokenized_corpus = [self._tokenize(c.get("text", "")) for c in chunks]

        # Build BM25 index
        bm25 = BM25Okapi(tokenized_corpus)

        # Save index
        bm25_path = self.index_dir / "bm25_index.pkl"
        with open(bm25_path, "wb") as f:
            pickle.dump(bm25, f)

        # Save chunk map (position in BM25 → chunk metadata, no full text to save space)
        chunk_map = [
            {
                "id":          c.get("id", ""),
                "purana":      c.get("purana", ""),
                "book_section":c.get("book_section", ""),
                "chapter":     c.get("chapter"),
                "verse_range": c.get("verse_range", ""),
                "text":        c.get("text", "")[:500],  # Snippet only in map
                "language":    c.get("language", ""),
                "source_file": c.get("source_file", ""),
                "category":    c.get("category", ""),
            }
            for c in chunks
        ]
        chunk_map_path = self.index_dir / "chunk_map.json"
        with open(chunk_map_path, "w", encoding="utf-8") as f:
            json.dump(chunk_map, f, ensure_ascii=False)

        console.print(f"[green]✓[/green] BM25 index saved to {bm25_path}")
        console.print(f"[green]✓[/green] Chunk map saved to {chunk_map_path} ({len(chunk_map):,} entries)")
        return len(chunks)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize for BM25 (Devanagari + Latin)."""
        import re
        tokens = re.findall(r'[\u0900-\u097F]+|[a-zA-Z]+', text.lower())
        return [t for t in tokens if len(t) > 1]

    # ── Full Build ────────────────────────────────────────────────────

    def build_all(self) -> dict[str, int]:
        """Build both indexes. Returns counts of indexed documents."""
        console.rule("[bold gold1]PuranGPT Index Builder[/bold gold1]")

        chunks = self._load_chunks()
        if not chunks:
            return {"vector": 0, "bm25": 0}

        vector_count = self.build_vector_index(chunks)
        pruned_count = self.prune_vector_index(chunks)
        bm25_count   = self.build_bm25_index(chunks)

        console.rule("[bold green]Indexing Complete[/bold green]")
        console.print(f"  Vector index: [green]{vector_count:,}[/green] new chunks added")
        console.print(f"  Pruned:       [green]{pruned_count:,}[/green] stale vectors removed")
        console.print(f"  BM25 index:   [green]{bm25_count:,}[/green] chunks indexed")
        console.print(f"\nStart the server: [cyan]python run.py[/cyan]")

        return {"vector": vector_count, "pruned": pruned_count, "bm25": bm25_count}


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PuranGPT — Build search indexes")
    parser.add_argument("--chunks-dir", default="data/chunks")
    parser.add_argument("--db-dir",     default="data/chroma_db")
    parser.add_argument("--index-dir",  default="data/indexes")
    parser.add_argument(
        "--model",
        default=DEFAULT_EMBED_MODEL,
        help=f"HuggingFace model for embeddings (default: {DEFAULT_EMBED_MODEL})",
    )
    parser.add_argument(
        "--batch-size", type=int, default=EMBED_BATCH_SIZE,
        help="Embedding batch size (reduce if OOM)",
    )
    args = parser.parse_args()

    indexer = EmbeddingIndexer(
        chunks_dir=args.chunks_dir,
        db_dir=args.db_dir,
        index_dir=args.index_dir,
        embed_model=args.model,
        batch_size=args.batch_size,
    )
    indexer.build_all()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
