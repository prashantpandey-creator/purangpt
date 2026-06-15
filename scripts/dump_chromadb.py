import json
import chromadb
from rich.progress import track

CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "purana_verses"

print("Connecting to ChromaDB...")
client = chromadb.PersistentClient(path=CHROMA_DIR)
col = client.get_collection(COLLECTION_NAME)

print("Fetching IDs...")
all_ids = col.get(include=[])["ids"]

print(f"Exporting {len(all_ids)} vectors to embeddings.jsonl...")
BATCH_SIZE = 10000

with open("data/embeddings.jsonl", "w") as f:
    for i in range(0, len(all_ids), BATCH_SIZE):
        batch = all_ids[i:i+BATCH_SIZE]
        data = col.get(ids=batch, include=["embeddings", "metadatas", "documents"])
        
        for j in range(len(data["ids"])):
            record = {
                "id": data["ids"][j],
                "doc": data["documents"][j],
                "meta": data["metadatas"][j] if data["metadatas"] else {},
                "emb": data["embeddings"][j].tolist() if hasattr(data["embeddings"][j], "tolist") else data["embeddings"][j]
            }
            f.write(json.dumps(record) + "\n")

print("Done exporting!")
