#!/usr/bin/env python3
"""
PuranGPT — Main Entry Point
============================
python run.py                  # Start the web server
python run.py --download       # Download all sacred texts
python run.py --extract        # Extract text from PDFs
python run.py --chunk          # Chunk into verses
python run.py --index          # Build search indexes
python run.py --pipeline       # Run all steps (download → extract → chunk → index)
python run.py --status         # Show system status
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path so submodules can be imported
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.table import Table

console = Console()
logger  = logging.getLogger(__name__)


def cmd_download(args) -> None:
    """Download PDFs from vedpuran.net and fallback sources."""
    from data_pipeline.downloader import PuranDownloader, CATALOG
    downloader = PuranDownloader(output_dir=args.data_dir + "/raw_pdfs")

    texts = None
    if args.texts:
        texts = [CATALOG[tid] for tid in args.texts if tid in CATALOG]

    downloader.download_all(texts=texts, category=args.category)


def cmd_extract(args) -> None:
    """Extract text from downloaded PDFs using PyMuPDF + PaddleOCR."""
    from data_pipeline.extractor import TextExtractor
    extractor = TextExtractor()
    extractor.extract_all(
        input_dir  = args.data_dir + "/raw_pdfs",
        output_dir = args.data_dir + "/extracted",
    )


def cmd_chunk(args) -> None:
    """Chunk extracted text into verse-aware units with metadata."""
    from data_pipeline.chunker import PuranicChunker
    chunker = PuranicChunker()
    chunker.process_all(
        extracted_dir = args.data_dir + "/extracted",
        chunks_dir    = args.data_dir + "/chunks",
    )


def cmd_index(args) -> None:
    """Build ChromaDB vector index + BM25 keyword index."""
    from indexer.build_index import EmbeddingIndexer
    indexer = EmbeddingIndexer(
        chunks_dir = args.data_dir + "/chunks",
        db_dir     = args.data_dir + "/chroma_db",
        index_dir  = args.data_dir + "/indexes",
        embed_model= args.embed_model,
    )
    indexer.build_all()


def cmd_pipeline(args) -> None:
    """Run the full data pipeline: download → extract → chunk → index."""
    console.rule("[bold gold1]PuranGPT Full Pipeline[/bold gold1]")
    console.print("Steps: Download → Extract → Chunk → Index\n")

    console.print("[bold]Step 1/4: Downloading texts…[/bold]")
    cmd_download(args)

    console.print("\n[bold]Step 2/4: Extracting text…[/bold]")
    cmd_extract(args)

    console.print("\n[bold]Step 3/4: Chunking into verses…[/bold]")
    cmd_chunk(args)

    console.print("\n[bold]Step 4/4: Building search indexes…[/bold]")
    cmd_index(args)

    console.rule("[bold green]✓ Pipeline Complete[/bold green]")
    console.print("Now start the server: [cyan]python run.py[/cyan]")


def cmd_status(args) -> None:
    """Show system status: indexes, model, disk usage."""
    data_dir = Path(args.data_dir)

    console.rule("[bold gold1]PuranGPT Status[/bold gold1]")

    table = Table(show_header=True, header_style="bold gold1")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    # Raw PDFs
    pdf_dir = data_dir / "raw_pdfs"
    if pdf_dir.exists():
        pdfs = list(pdf_dir.glob("**/*.pdf"))
        size_mb = sum(p.stat().st_size for p in pdfs) / 1024 / 1024
        table.add_row("Raw PDFs", "[green]✓[/green]", f"{len(pdfs)} files, {size_mb:.0f} MB")
    else:
        table.add_row("Raw PDFs", "[red]✗[/red]", "Not downloaded (run --download)")

    # Extracted text
    ext_dir = data_dir / "extracted"
    if ext_dir.exists():
        jsons = list(ext_dir.glob("**/*.json"))
        table.add_row("Extracted Text", "[green]✓[/green]", f"{len(jsons)} files")
    else:
        table.add_row("Extracted Text", "[red]✗[/red]", "Not extracted (run --extract)")

    # Chunks
    chunk_dir = data_dir / "chunks"
    if chunk_dir.exists():
        jsonls = list(chunk_dir.glob("*.jsonl"))
        total_chunks = sum(
            sum(1 for line in open(f) if line.strip())
            for f in jsonls
        )
        table.add_row("Chunks", "[green]✓[/green]", f"{total_chunks:,} verses across {len(jsonls)} texts")
    else:
        table.add_row("Chunks", "[red]✗[/red]", "Not chunked (run --chunk)")

    # ChromaDB
    db_dir = data_dir / "chroma_db"
    if db_dir.exists():
        size_mb = sum(p.stat().st_size for p in db_dir.rglob("*") if p.is_file()) / 1024 / 1024
        table.add_row("Vector Index", "[green]✓[/green]", f"ChromaDB, {size_mb:.0f} MB")
    else:
        table.add_row("Vector Index", "[red]✗[/red]", "Not built (run --index)")

    # BM25
    bm25_path = data_dir / "indexes" / "bm25_index.pkl"
    if bm25_path.exists():
        size_mb = bm25_path.stat().st_size / 1024 / 1024
        table.add_row("BM25 Index", "[green]✓[/green]", f"{size_mb:.1f} MB")
    else:
        table.add_row("BM25 Index", "[red]✗[/red]", "Not built (run --index)")

    # Ollama
    import urllib.request
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=2)
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        table.add_row("Ollama LLM", "[green]✓[/green]", f"Running at {ollama_url} — model: {model}")
    except Exception:
        table.add_row("Ollama LLM", "[yellow]○[/yellow]", f"Not running at {ollama_url}")

    # Groq API
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        table.add_row("Groq API", "[green]✓[/green]", f"Key configured — model: {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}")
    else:
        table.add_row("Groq API", "[dim]○[/dim]", "GROQ_API_KEY not set")

    console.print(table)


def cmd_serve(args) -> None:
    """Start the FastAPI web server."""
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", args.port))

    console.print()
    console.rule("[bold gold1]🕉️  PuranGPT[/bold gold1]")
    console.print(f"  Web UI: [cyan link]http://localhost:{port}[/cyan link]")
    console.print(f"  API:    [cyan]http://localhost:{port}/api/status[/cyan]")
    console.print()

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=args.dev,
        log_level="info",
    )


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="🕉️  PuranGPT — AI Oracle of the Sacred Texts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Quick Start:
  python run.py --pipeline     # Download, extract, chunk, and index everything
  python run.py                # Start the web server at http://localhost:8000

Individual Steps:
  python run.py --download     # Step 1: Download PDFs
  python run.py --extract      # Step 2: Extract text (OCR)
  python run.py --chunk        # Step 3: Chunk into verses
  python run.py --index        # Step 4: Build search indexes
  python run.py --status       # Check system status
        """,
    )

    # Actions (mutually exclusive group)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--download",  action="store_true", help="Download sacred texts")
    action_group.add_argument("--extract",   action="store_true", help="Extract text from PDFs")
    action_group.add_argument("--chunk",     action="store_true", help="Chunk text into verses")
    action_group.add_argument("--index",     action="store_true", help="Build search indexes")
    action_group.add_argument("--pipeline",  action="store_true", help="Run full pipeline")
    action_group.add_argument("--status",    action="store_true", help="Show system status")

    # Download options
    parser.add_argument("--texts",    nargs="+", metavar="ID", help="Specific text IDs to download")
    parser.add_argument("--category", choices=["mahapuranas","epics","upanishads","yoga"], help="Download category")

    # Index options
    parser.add_argument(
        "--embed-model",
        default=os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-large"),
        help="Embedding model for indexing",
    )

    # Server options
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Server port")
    parser.add_argument("--dev",  action="store_true", help="Enable hot-reload for development")

    # Common options
    parser.add_argument(
        "--data-dir",
        default=os.getenv("DATA_DIR", "data"),
        help="Root data directory",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s — %(message)s",
    )

    if args.download:
        cmd_download(args)
    elif args.extract:
        cmd_extract(args)
    elif args.chunk:
        cmd_chunk(args)
    elif args.index:
        cmd_index(args)
    elif args.pipeline:
        cmd_pipeline(args)
    elif args.status:
        cmd_status(args)
    else:
        # Default: start the server
        cmd_serve(args)


if __name__ == "__main__":
    main()
