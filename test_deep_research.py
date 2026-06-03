import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

from backend.agents.deep_research import DeepResearchAgent

async def mock_send_event(event_type, content):
    if event_type == "status":
        print(f"\n[STATUS] {content}")
    elif event_type == "token":
        print(content, end="", flush=True)

async def main():
    agent = DeepResearchAgent()
    print("Testing Agent...")
    await agent.execute("who was vishwamotra ? why did he killed brahmings ? explain his rivalvary with vashsiht through research", [], mock_send_event)

if __name__ == "__main__":
    asyncio.run(main())
