import sys, os
sys.path.insert(0, os.path.abspath("."))
from backend.pinecone_client import init_pinecone, get_pinecone_index
from google import genai
from dotenv import load_dotenv

load_dotenv()

print("Testing Gemini...")
client = genai.Client()
try:
    res = client.models.embed_content(model="gemini-embedding-2", contents=["hello"])
    print("Gemini OK")
except Exception as e:
    print(f"Gemini Error: {e}")

print("Testing Pinecone...")
try:
    init_pinecone()
    idx = get_pinecone_index()
    print("Pinecone Index OK:", idx.describe_index_stats())
except Exception as e:
    print(f"Pinecone Error: {e}")
