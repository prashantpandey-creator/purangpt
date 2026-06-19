import os
import asyncio
import json
import logging
from openai import AsyncOpenAI
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

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
    def __init__(self, model: str = "deepseek-chat", searcher=None):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set.")
        # DeepSeek is OpenAI API compatible
        self.client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        self.model = model
        self.searcher = searcher
        
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Searches the live internet for a given query and returns a summary of the top matching pages. Use this to find general historical context, academic papers, or modern discourse not in the local corpus.",
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
            },
            {
                "type": "function",
                "function": {
                    "name": "search_sacred_texts",
                    "description": "Queries the local pgvector database of Puranas, Vedas, Upanishads, and commentaries. Use this to find exact verses, stories, and philosophical truths.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query (e.g. 'stories of karma', 'Shiva and Sati')."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    async def execute(self, query: str, history: list):
        """
        Executes the deep research loop using DeepSeek client.
        Yields (event_type: str, content: str).
        """
        # ── DeepSeek Reasoner (R1) search-first synthesis flow ──────────────────
        if self.model == "deepseek-reasoner":
            yield "status", "🌐 Formulating search strategies for deep research..."
            
            # Generate search queries using the fast deepseek-chat model
            sys_instruct = (
                "You are PuranGPT's Search Query Generator. Your job is to output exactly a JSON array containing 3 distinct "
                "search queries related to the user's research question. Do not include markdown formatting or extra text."
            )
            hist_context = ""
            if history:
                hist_context = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-5:])
            user_msg = f"History:\n{hist_context}\n\nUser Question: {query}"
            
            queries = [query]
            try:
                q_response = await self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": sys_instruct},
                        {"role": "user", "content": user_msg}
                    ],
                    temperature=0.1
                )
                text = q_response.choices[0].message.content.strip()
                if text.startswith("```"):
                    parts = text.split("```")
                    if len(parts) > 1:
                        text = parts[1]
                        if text.startswith("json"):
                            text = text[4:]
                        text = text.strip()
                parsed = json.loads(text)
                if isinstance(parsed, list) and len(parsed) > 0:
                    queries = parsed[:3]
            except Exception as e:
                logger.error(f"Error generating search queries: {e}")

            # Run searches in parallel
            yield "status", f"🔍 Searching live web for: {', '.join(queries)}..."
            search_tasks = [asyncio.to_thread(_search_web, q) for q in queries]
            search_results = await asyncio.gather(*search_tasks)
            
            # Compile context
            combined_context = ""
            for q, res in zip(queries, search_results):
                combined_context += f"### Results for query: '{q}'\n{res}\n\n"

            # Call deepseek-reasoner
            yield "status", "🧠 Synthesizing scholarly response with DeepSeek-R1..."
            system_instruction = (
                "You are PuranGPT's Deep Research Web Agent. Your goal is to research scholarly, "
                "theological, or historical topics deeply.\n"
                "1. Read the provided search snippets and synthesize a detailed, scholarly answer.\n"
                "2. Cite your sources using the URLs provided.\n"
                "3. NEVER say you are an AI, you are PuranGPT."
            )
            
            synthesis_messages = [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Web Search Context:\n{combined_context}\n\nUser Question: {query}"}
            ]
            
            try:
                response = await self.client.chat.completions.create(
                    model="deepseek-reasoner",
                    messages=synthesis_messages,
                    stream=True
                )
                
                async for chunk in response:
                    delta = chunk.choices[0].delta
                    # Yield reasoning content if present
                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        yield "reasoning", reasoning
                    # Yield content if present
                    content = getattr(delta, "content", None)
                    if content:
                        yield "token", content
            except Exception as e:
                logger.error(f"DeepSeek Reasoner synthesis failed: {e}")
                yield "token", f"\n\n(Reasoner execution failed: {str(e)})"
            return

        # ── Standard DeepSeek Chat (V3) tool-calling agent flow ─────────────────
        system_instruction = (
            "You are PuranGPT's Deep Research Agent. Your goal is to research scholarly, "
            "theological, or historical topics deeply.\n"
            "1. ALWAYS call `search_sacred_texts` to query the local Puranic database for scripture.\n"
            "2. Call `search_web` to find external historical context or academic papers.\n"
            "3. Synthesize a detailed, scholarly answer.\n"
            "4. Cite your sources.\n"
            "5. NEVER say you are an AI, you are PuranGPT."
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
                    elif tool_call.function.name == "search_sacred_texts":
                        args = json.loads(tool_call.function.arguments)
                        search_q = args.get("query", "")
                        yield "status", f"🕉️ Querying Sacred Texts for: {search_q}"
                        
                        if self.searcher:
                            res = await self.searcher.hybrid_search(search_q, top_k=3)
                            if not res:
                                tool_result = "No matches found in sacred texts."
                            else:
                                out = []
                                for r in res:
                                    out.append(f"Source: {r.reference}\nPassage: {r.text}")
                                tool_result = "\n\n---\n\n".join(out)
                        else:
                            tool_result = "Local searcher is unavailable."
                            
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
