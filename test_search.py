import os
import sys
from dotenv import load_dotenv
import json

load_dotenv("/Users/badenath/projects/vedic puran/purangpt/.env")

sys.path.append("/Users/badenath/projects/vedic puran/purangpt")
from engine.rag import retrieve_context

print("Testing query: 'ramas feet smell'")
contexts = retrieve_context("ramas feet smell")
for c in contexts:
    print(f"\n--- SCORE: {c.get('similarity', 'N/A')} | FILE: {c.get('file_name')} ---")
    print(c.get('content')[:300])
