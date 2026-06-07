import os
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
print(f"Key: {PINECONE_API_KEY}")

pc = Pinecone(api_key=PINECONE_API_KEY)
indexes = pc.list_indexes()
print("Indexes:")
for idx in indexes:
    print(f"- {idx['name']} (status: {idx['status']['state']})")
    index = pc.Index(idx['name'])
    stats = index.describe_index_stats()
    print(stats)
