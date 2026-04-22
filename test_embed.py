import asyncio
from litellm import aembedding

# 16 texts of 5000 characters each
texts = ["A" * 5000 for _ in range(16)]

async def test():
    try:
        res = await aembedding(model='ollama/nomic-embed-text:latest', input=texts, api_base='http://localhost:11434')
        print(f'Success: {len(res.data)} embeddings')
    except Exception as e:
        print(f'Failed: {e}')

if __name__ == "__main__":
    asyncio.run(test())
