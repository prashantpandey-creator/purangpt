"""sqlite_export — Export all_chunks.jsonl to a SQLite DB with FTS5 for offline use.

Input contract:  run(chunks_path, output_path) -> envelope
Output contract (envelope.data on success):
  {
    "output_path": str,
    "row_count": int,
    "fts_row_count": int,
    "db_size_mb": float,
    "texts": [str]   # unique purana names indexed
  }

DB schema:
  chunks(id, purana, category, book_section, chapter, verse_range,
         language, source_file, source_page, word_count, text)
  chunks_fts  -- FTS5 virtual table over (purana, book_section, text)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from typing import Any, Dict, List

CHUNKS_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "chunks", "all_chunks.jsonl"
)
OUTPUT_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "offline", "corpus.db"
)


def _envelope(success: bool, data: Any, metadata: Dict[str, Any],
              errors: List[Dict[str, str]]) -> Dict[str, Any]:
    return {"success": success, "data": data, "metadata": metadata, "errors": errors}


def run(chunks_path: str = CHUNKS_DEFAULT,
        output_path: str = OUTPUT_DEFAULT) -> Dict[str, Any]:
    chunks_path = os.path.abspath(chunks_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(chunks_path):
        return _envelope(False, None, {"chunks_path": chunks_path},
                         [{"code": "missing_input",
                           "message": f"chunks file not found: {chunks_path}"}])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if os.path.exists(output_path):
        os.remove(output_path)

    con = sqlite3.connect(output_path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA page_size=4096")

    con.execute("""
        CREATE TABLE chunks (
            id           TEXT PRIMARY KEY,
            purana       TEXT,
            category     TEXT,
            book_section TEXT,
            chapter      INTEGER,
            verse_range  TEXT,
            language     TEXT,
            source_file  TEXT,
            source_page  INTEGER,
            word_count   INTEGER,
            text         TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            purana,
            book_section,
            text,
            content='chunks',
            content_rowid='rowid'
        )
    """)

    con.execute("CREATE INDEX idx_purana   ON chunks(purana)")
    con.execute("CREATE INDEX idx_language ON chunks(language)")

    BATCH = 5000
    rows: List[tuple] = []
    row_count = 0
    texts: set = set()

    def flush(batch: List[tuple]) -> None:
        con.executemany(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?)", batch
        )
        con.executemany(
            """INSERT INTO chunks_fts(rowid, purana, book_section, text)
               SELECT rowid, purana, book_section, text FROM chunks
               WHERE id = ?""",
            [(r[0],) for r in batch],
        )

    print("Importing chunks...", file=sys.stderr)
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            texts.add(c.get("purana", ""))
            rows.append((
                c.get("id", ""),
                c.get("purana", ""),
                c.get("category", ""),
                c.get("book_section", ""),
                c.get("chapter", 0),
                c.get("verse_range", ""),
                c.get("language", ""),
                c.get("source_file", ""),
                c.get("source_page", 0),
                c.get("word_count", 0),
                c.get("text", ""),
            ))
            row_count += 1

            if len(rows) >= BATCH:
                flush(rows)
                rows = []
                if row_count % 50000 == 0:
                    print(f"  {row_count:,} rows...", file=sys.stderr)

    if rows:
        flush(rows)

    con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
    con.commit()

    fts_count = con.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    con.close()

    db_size_mb = os.path.getsize(output_path) / (1024 * 1024)

    data = {
        "output_path": output_path,
        "row_count": row_count,
        "fts_row_count": fts_count,
        "db_size_mb": round(db_size_mb, 1),
        "texts": sorted(t for t in texts if t),
    }
    return _envelope(True, data, {"chunks_path": chunks_path}, [])


def main(argv: List[str]) -> int:
    as_json = "--json" in argv
    chunks_path = CHUNKS_DEFAULT
    output_path = OUTPUT_DEFAULT

    if "--chunks" in argv:
        chunks_path = argv[argv.index("--chunks") + 1]
    if "--output" in argv:
        output_path = argv[argv.index("--output") + 1]

    env = run(chunks_path, output_path)

    if as_json:
        print(json.dumps(env, indent=2))
    else:
        if not env["success"]:
            print(f"ERROR: {env['errors'][0]['message']}", file=sys.stderr)
            return 2
        d = env["data"]
        print(f"OK: {d['row_count']:,} rows → {d['output_path']}")
        print(f"    FTS rows: {d['fts_row_count']:,}  DB size: {d['db_size_mb']} MB")
        print(f"    Texts ({len(d['texts'])}): {', '.join(d['texts'][:5])}...")

    return 0 if env["success"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
