import asyncio
from app.services.search_service import search_service

async def check_vectors():
    await search_service.initialize()
    stats = search_service.get_collection_stats()
    print(f"Collection name: {stats['name']}")
    print(f"Vector count: {stats['count']}")
    print(f"Initialized: {stats['initialized']}")

asyncio.run(check_vectors())
