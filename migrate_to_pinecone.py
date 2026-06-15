import os
import chromadb
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
CHROMA_DIR = "./data/chroma_db"  # Local path
INDEX_NAME = "purangpt-vectors"

if not PINECONE_API_KEY:
    print("No Pinecone API Key")
    exit(1)

pc = Pinecone(api_key=PINECONE_API_KEY)

# Create index if it doesn't exist
existing_indexes = pc.list_indexes().names()
if INDEX_NAME not in existing_indexes:
    print(f"Creating Pinecone index '{INDEX_NAME}'...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=384, # multilingual-e5-small is 384d
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

index = pc.Index(INDEX_NAME)

print("Connecting to local ChromaDB...")
client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_collection("purana_verses")

count = collection.count()
print(f"Found {count} items in ChromaDB.")

BATCH_SIZE = 100
offset = 0

print("Starting migration...")
while offset < count:
    batch = collection.get(include=["embeddings", "metadatas", "documents"], limit=BATCH_SIZE, offset=offset)
    
    ids = batch["ids"]
    embeddings = batch["embeddings"]
    metadatas = batch["metadatas"]
    documents = batch["documents"]
    
    if not ids:
        break

    pinecone_vectors = []
    for i in range(len(ids)):
        meta = metadatas[i] or {}
        # Ensure metadata values are strings/numbers/booleans (Pinecone requirement)
        clean_meta = {}
        for k, v in meta.items():
            if v is not None:
                clean_meta[k] = v
        # Add the document text itself to metadata so we can retrieve it
        if documents[i]:
            clean_meta["text"] = documents[i]
            
        pinecone_vectors.append({
            "id": str(ids[i]),
            "values": embeddings[i],
            "metadata": clean_meta
        })

    index.upsert(vectors=pinecone_vectors)
    offset += len(ids)
    print(f"Upserted {offset}/{count} vectors to Pinecone...")

print("Migration complete!")
