import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

def search(q: str) -> str:
    """Search web for q"""
    print(f"-> search called with {q}")
    return 'Vishwamitra was a legendary sage.'

res = client.chats.create(model='gemini-2.5-flash', config=types.GenerateContentConfig(tools=[search])).send_message('search for vishwamitra')
print(res.text)
