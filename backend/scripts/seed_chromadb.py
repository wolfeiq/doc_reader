# scripts/seed_chromadb.py
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_maker
from app.models import DocumentSection
from app.services.search_service import search_service


async def sync_sections_to_chromadb():
    await search_service.initialize()
    
    # Check current count
    stats = search_service.get_collection_stats()
    print(f"ChromaDB before: {stats['count']} sections")
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(DocumentSection).options(
                selectinload(DocumentSection.document)
            )
        )
        sections = result.scalars().all()
        
        batch = []
        for section in sections:
            if not section.content.strip():
                continue 
            batch.append({
                "section_id": section.id,
                "content": section.content,
                "metadata": {
                    "document_id": str(section.document_id),
                    "file_path": section.document.file_path,
                    "section_title": section.section_title or "",
                    "order": section.order
                },
            })
        
        if batch:
            count = await search_service.add_sections_batch(batch)
            print(f"Synced {count} sections to ChromaDB")
    
    stats = search_service.get_collection_stats()
    print(f"ChromaDB after: {stats['count']} sections")


if __name__ == "__main__":
    asyncio.run(sync_sections_to_chromadb())