import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from indexer.search import HybridSearcher

load_dotenv()

def main():
    searcher = HybridSearcher(db_dir="data/chroma_db", index_dir="data/indexes").initialize()
    
    queries = [
        "Bhūma Puruṣa",
        "Bhuma Purusha",
        "Brahma Vaivarta Purana Bhuma Purusha",
        "krishna bhuma purusha"
    ]
    
    for query in queries:
        print(f"\n======================================")
        print(f"QUERY: {query}")
        print(f"======================================")
        results = searcher.hybrid_search(query, top_k=5)
        print(f"Found {len(results)} results.")
        for i, res in enumerate(results):
            print(f"\nResult {i+1}:")
            print(f"  Reference: {res.reference}")
            print(f"  ID: {res.id}")
            print(f"  Score: {res.score}")
            print(f"  Text preview (first 200 chars): {repr(res.text[:200])}")
            print(f"  Metadata: {res.chunk}")

if __name__ == "__main__":
    main()
