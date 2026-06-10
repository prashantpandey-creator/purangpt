import asyncio
import aiohttp
import urllib.request
import json
import re
from pathlib import Path

OUT_DIR = Path("data/raw_texts/gretil")
MBH_DIR = OUT_DIR / "mahabharata"
MBH_DIR.mkdir(parents=True, exist_ok=True)

async def download_file(session, url):
    try:
        async with session.get(url) as r:
            if r.status == 200:
                content = await r.read()
                content = content.decode("utf-8", errors="ignore")
                return re.sub(r"<.*?>", "", content)
    except Exception:
        pass
    return ""

async def main():
    url = "https://api.github.com/repos/INDOLOGY/GRETIL-mirror/git/trees/master?recursive=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Python"})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
    
    mbh_files = []
    for item in data.get("tree", []):
        path = item.get("path", "").lower()
        if "mbh/sas/b" in path and path.endswith(".htm"):
            mbh_files.append(item["path"])
            
    print(f"Found {len(mbh_files)} Mahabharata chapters.")
    mbh_files.sort()
    
    urls = [f"https://raw.githubusercontent.com/INDOLOGY/GRETIL-mirror/master/{f}" for f in mbh_files]
    
    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_file(session, u) for u in urls]
        results = await asyncio.gather(*tasks)
        
    with open(MBH_DIR / "mahabharata.txt", "w", encoding="utf-8") as f:
        for res in results:
            if res:
                f.write(res + "\n")
                
    print("Mahabharata fully downloaded and concatenated!")

if __name__ == "__main__":
    asyncio.run(main())
