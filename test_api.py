import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/chat",
            json={"query": "hello"},
            headers={"Authorization": "Bearer test"}
        )
        print("Status:", response.status_code)
        async for line in response.aiter_lines():
            if line:
                print(line)

asyncio.run(main())
