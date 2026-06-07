import os
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

def main():
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("PINECONE_API_KEY not found in .env")
        return
        
    pc = Pinecone(api_key=api_key)
    index = pc.Index("purangpt-verses")
    stats = index.describe_index_stats()
    print("Pinecone index stats:")
    print(stats)

if __name__ == "__main__":
    main()
