import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from indexer.search import HybridSearcher

load_dotenv()

def main():
    searcher = HybridSearcher(db_dir="data/chroma_db", index_dir="data/indexes").initialize()
    
    print("Fetching Purana stats from ChromaDB...")
    stats = searcher.get_purana_stats()
    print(f"Total Puranas: {len(stats)}")
    for s in stats:
        print(f"  {s['name']}: {s['chunk_count']} chunks")

if __name__ == "__main__":
    main()
