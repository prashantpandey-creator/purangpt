import os
import asyncio
import json
from openai import AsyncOpenAI
from duckduckgo_search import DDGS

def _search_web(query: str) -> str:
    """Searches the live web using DuckDuckGo and returns summaries of top results."""
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No results found on the web."
        
        out = []
        for r in results:
            out.append(f"Title: {r.get('title')}\nURL: {r.get('href')}\nSummary: {r.get('body')}")
        return "\n\n---\n\n".join(out)
    except Exception as e:
        return f"Web Search failed: {str(e)}"

class DeepResearchAgent:
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set.")
        # DeepSeek is OpenAI API compatible
        self.client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        self.model = "deepseek-chat"
        
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Searches the live internet for a given query and returns a summary of the top matching pages. Use this to find information not in the local Puranic corpus.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The web search query."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    async def execute(self, query: str, history: list):
        """
        Executes the deep research loop using Groq and OpenAI client.
        Yields (event_type: str, content: str).
        """
        system_instruction = (
            "You are PuranGPT's Deep Research Web Agent. Your goal is to research scholarly, "
            "theological, or historical topics deeply using live web searches.\n"
            "1. ALWAYS call `search_web` to find information if it's beyond your local knowledge.\n"
            "2. Read the search snippets and synthesize a detailed, scholarly answer.\n"
            "3. Cite your sources using the URLs provided in the search results.\n"
            "4. NEVER say you are an AI, you are PuranGPT."
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": query}
        ]

        yield "status", "🌐 Initiating Deep Web Research Agent (DeepSeek-V3)..."

        iteration = 0
        max_iterations = 4

        while iteration < max_iterations:
            iteration += 1
            yield "status", f"🧠 Agent thinking (Step {iteration})..."
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.3
            )
            
            message = response.choices[0].message
            messages.append(message)
            
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "search_web":
                        args = json.loads(tool_call.function.arguments)
                        search_q = args.get("query", "")
                        yield "status", f"🔍 Searching Live Web for: {search_q}"
                        
                        tool_result = await asyncio.to_thread(_search_web, search_q)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": tool_result
                        })
                continue
            
            # Extract final text
            final_text = message.content
            if final_text:
                for i in range(0, len(final_text), 20):
                    chunk = final_text[i:i+20]
                    yield "token", chunk
                    await asyncio.sleep(0.01)
            break
            
        if iteration >= max_iterations:
            yield "token", "\n\n(Research halted due to iteration limit)"
