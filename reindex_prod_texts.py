"""Reindex specific texts into the prod pgvector `purana_verses` table.

Delete-then-ingest, with FLAT metadata matching the live prod shape (the chunk
dict minus the bulky `text` field — verified against prod rows 2026-06-28).
pg_ingest.py is WRONG for our chunks (it reads chunk["metadata"] → empty);
build_index.py is the old ChromaDB path. This is the corrected pgvector ingest.

RUN ON THE SERVER (pgvector is firewalled to the internal Docker network):
    docker exec purangpt_backend python /app/reindex_prod_texts.py yoga_vasistha bhavishya varaha

--dry-run: print row counts + a sample record per text; NO DB, NO embedding.
"""
import argparse
import json
import os
import sys
from pathlib import Path

TABLE = "purana_verses"
CHUNKS_DIR = os.environ.get("CHUNKS_DIR", "data/chunks")
MARKER = "v3-corpus-repair-2026-06-28"


def load_chunks(text_id):
    path = Path(CHUNKS_DIR) / f"{text_id}.jsonl"
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def to_metadata(chunk):
    # flat metadata == chunk dict minus the bulky text (matches prod shape) + a
    # provenance marker so these rows are identifiable/auditable.
    md = {k: v for k, v in chunk.items() if k != "text"}
    md["reembedded"] = MARKER
    return md


def dry_run(text_ids):
    for tid in text_ids:
        chunks = load_chunks(tid)
        print(f"\n{tid}: {len(chunks)} chunks")
        c = chunks[0]
        print(f"  id:       {c['id']}")
        print(f"  content:  {c['text'][:90]!r}")
        print(f"  metadata: {json.dumps(to_metadata(c), ensure_ascii=False)[:240]}")


def run(text_ids):
    import psycopg2
    from sentence_transformers import SentenceTransformer

    db = os.environ["VECTOR_DB_URL"]
    print("loading embedding model intfloat/multilingual-e5-small …", flush=True)
    model = SentenceTransformer("intfloat/multilingual-e5-small")
    conn = psycopg2.connect(db)
    conn.autocommit = True

    for tid in text_ids:
        chunks = load_chunks(tid)
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {TABLE} WHERE id LIKE %s", (tid + "-%",))
            print(f"{tid}: deleted {cur.rowcount} stale rows; ingesting {len(chunks)} …",
                  flush=True)
        BATCH = 64
        done = 0
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i + BATCH]
            texts = ["passage: " + c["text"][:1000] for c in batch]
            embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            records = []
            for c, e in zip(batch, embs):
                emb = "[" + ",".join(map(str, e.tolist())) + "]"
                records.append((c["id"], c["text"],
                                json.dumps(to_metadata(c), ensure_ascii=False), emb))
            with conn.cursor() as cur:
                args = ",".join(
                    cur.mogrify("(%s,%s,%s,%s::vector)", r).decode("utf-8")
                    for r in records)
                cur.execute(
                    f"INSERT INTO {TABLE} (id, content, metadata, embedding) "
                    f"VALUES {args} ON CONFLICT (id) DO UPDATE SET "
                    f"content=EXCLUDED.content, metadata=EXCLUDED.metadata, "
                    f"embedding=EXCLUDED.embedding")
            done += len(batch)
            if done % 3200 == 0 or done == len(chunks):
                print(f"  {tid}: {done}/{len(chunks)}", flush=True)

    print("\nverify:")
    with conn.cursor() as cur:
        for tid in text_ids:
            cur.execute(f"SELECT count(*) FROM {TABLE} WHERE id LIKE %s", (tid + "-%",))
            cur.execute(f"SELECT count(*) FROM {TABLE} WHERE id LIKE %s", (tid + "-%",))
            n = cur.fetchone()[0]
            cur.execute(f"SELECT metadata->>'purana', metadata->>'category' "
                        f"FROM {TABLE} WHERE id LIKE %s LIMIT 1", (tid + "-%",))
            row = cur.fetchone()
            print(f"  {tid}: {n} rows, sample meta purana={row[0]!r} category={row[1]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text_ids", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        dry_run(args.text_ids)
    else:
        run(args.text_ids)


if __name__ == "__main__":
    main()
