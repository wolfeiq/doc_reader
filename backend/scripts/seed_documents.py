import asyncio
import logging
import os
from pathlib import Path

from app.config import settings
from app.db.session import async_session_maker, init_db
from app.schemas.document import DocumentCreate
from app.services.document_service import DocumentService
from app.services.search_service import search_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_documents(docs_path: str = "../data/openai-agents-sdk"):

    await init_db()
    logger.info("Database initialized")
    

    await search_service.initialize()
    logger.info("Search service initialized")
    
    base_path = Path(__file__).parent.parent.parent / "data" / "openai-agents-sdk"
    if not base_path.exists():
        logger.error(f"Documentation path does not exist: {base_path}")
        return
    

    md_files = list(base_path.glob("**/*.md"))
    logger.info(f"Found {len(md_files)} markdown files")
    
    async with async_session_maker() as db:
        service = DocumentService(db)
        
        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                
                relative_path = str(md_file.relative_to(base_path))

                existing = await service.get_by_file_path(relative_path)
                if existing:
                    logger.info(f"Document already exists: {relative_path}")
                    continue
                
                doc_data = DocumentCreate(
                    file_path=relative_path,
                    content=content,
                )
                
                document = await service.create(doc_data)
                logger.info(f"Created document: {relative_path} with {len(document.sections)} sections")
                
                for section in document.sections:
                    await search_service.add_section(
                        section_id=section.id,
                        content=section.content,
                        metadata={
                            "document_id": str(document.id),
                            "file_path": document.file_path,
                            "section_title": section.section_title or "",
                            "order": section.order,
                        },
                    )
                
                await db.commit()
                logger.info(f"Indexed {len(document.sections)} sections for {relative_path}")
                
            except Exception as e:
                logger.error(f"Error processing {md_file}: {e}")
                await db.rollback()
    
    stats = await search_service.get_collection_stats()
    logger.info(f"Seeding complete. ChromaDB has {stats['count']} documents indexed.")


async def clear_and_reseed():
    await init_db()

    await search_service.initialize()
    await search_service.clear_collection()
    logger.info("Cleared ChromaDB collection")

    await seed_documents()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        asyncio.run(clear_and_reseed())
    else:
        asyncio.run(seed_documents())