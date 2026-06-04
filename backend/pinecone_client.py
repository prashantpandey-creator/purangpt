import os
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = "purangpt-verses"

pc = None
index = None

def init_pinecone():
    global pc, index
    if not PINECONE_API_KEY:
        print("Warning: PINECONE_API_KEY not found in .env")
        return False
        
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Check if index exists, create if not
    existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index: {INDEX_NAME} (this may take a minute...)")
        pc.create_index(
            name=INDEX_NAME,
            dimension=384, # for intfloat/multilingual-e5-small or mini
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
    
    index = pc.Index(INDEX_NAME)
    return True

def get_pinecone_index():
    if index is None:
        init_pinecone()
    return index

def upsert_vectors(vectors):
    """
    vectors should be a list of dicts:
    [
        {"id": "chunk_id", "values": [0.1, 0.2, ...], "metadata": {"purana": "...", "chapter": "..."}},
        ...
    ]
    """
    idx = get_pinecone_index()
    if idx:
        idx.upsert(vectors=vectors)

def semantic_search(query_embedding, top_k=10, filters=None):
    """
    Search Pinecone for similar vectors.
    """
    idx = get_pinecone_index()
    if not idx:
        return []
        
    res = idx.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filters
    )
    
    results = []
    for match in res.matches:
        results.append({
            "id": match.id,
            "score": match.score,
            "metadata": match.metadata
        })
    return results
