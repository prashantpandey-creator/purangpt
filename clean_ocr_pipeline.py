"""
PuranGPT — OCR Text Cleaning Pipeline
=====================================
Uses the DeepSeek or Gemini API to process heavily corrupted OCR text (e.g. from Hindi PDFs)
and extract purely clean Sanskrit Shlokas.

Usage:
  python clean_ocr_pipeline.py <input_file.txt> <output_file.txt>
"""

import sys
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import aiohttp
import json

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

PROMPT = """
You are an expert Sanskrit scholar. I will give you a block of highly corrupted OCR text scanned from a Hindi-Sanskrit book.
Your task is to EXTRACT and RECONSTRUCT ONLY the Sanskrit Shlokas in standard Devanagari script.
- Ignore all Hindi translations, commentary, or page numbers.
- Fix any obvious OCR spelling mistakes in the Sanskrit.
- Output ONLY the clean Sanskrit verses, separated by newlines.
- Do NOT output any conversational text or english.
"""

async def clean_chunk(session: aiohttp.ClientSession, chunk: str) -> str:
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Clean this text:\n\n{chunk}"}
        ],
        "temperature": 0.1
    }
    
    try:
        async with session.post(url, headers=headers, json=payload, timeout=60) as r:
            if r.status == 200:
                data = await r.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                print(f"API Error {r.status}: {await r.text()}")
                return ""
    except Exception as e:
        print(f"Request failed: {e}")
        return ""

async def process_file(input_path: Path, output_path: Path):
    if not DEEPSEEK_API_KEY:
        print("DEEPSEEK_API_KEY not found in .env")
        return

    print(f"Processing {input_path}...")
    text = input_path.read_text(encoding="utf-8")
    
    # Simple chunking by character length (roughly 2000 chars per chunk to avoid context limit)
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    print(f"Total chunks to process: {len(chunks)}")
    
    clean_text = []
    
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{len(chunks)}...")
            result = await clean_chunk(session, chunk)
            if result:
                clean_text.append(result)
            await asyncio.sleep(0.5) # rate limit prevention
            
    output_path.write_text("\n\n".join(clean_text), encoding="utf-8")
    print(f"✓ Saved clean text to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clean_ocr_pipeline.py <input> <output>")
        sys.exit(1)
        
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    
    if not in_path.exists():
        print(f"File {in_path} does not exist.")
        sys.exit(1)
        
    asyncio.run(process_file(in_path, out_path))
