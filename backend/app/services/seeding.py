import logging
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.document import Document, DocumentSection, SectionDependency
from app.models.history import EditHistory
from app.models.query import Query
from app.models.suggestion import EditSuggestion
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.utils.files import find_markdown_files

logger = logging.getLogger(__name__)


async def seed_documents(base_path: Path) -> None:
    md_files = find_markdown_files(base_path)

    created = updated = skipped = errors = 0

    async with AsyncSessionLocal() as db:
        service = DocumentService(db)

        for file_path in md_files:
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                if not content:
                    skipped += 1
                    continue

                relative_path = str(file_path.relative_to(base_path))
                existing = await service.get_document_by_path(relative_path)

                if existing:
                    checksum = service.calculate_checksum(content)
                    if checksum != existing.checksum:
                        await service.update_document(relative_path, content)
                        updated += 1
                else:
                    await service.create_document(
                        file_path=relative_path,
                        content=content,
                        generate_embeddings=True,
                    )
                    created += 1

                await db.commit()

            except Exception:
                errors += 1
                await db.rollback()
                logger.exception("Failed to process %s", file_path)

    logger.info(
        "Seeding complete | created=%d updated=%d skipped=%d errors=%d",
        created,
        updated,
        skipped,
        errors,
    )


async def clear_database() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(EditHistory.__table__.delete())
        await db.execute(EditSuggestion.__table__.delete())
        await db.execute(Query.__table__.delete())
        await db.execute(SectionDependency.__table__.delete())
        await db.execute(DocumentSection.__table__.delete())
        await db.execute(Document.__table__.delete())
        await db.commit()


async def clear_vectors() -> None:
    search = SearchService()
    try:
        search.clear_collection()
    except Exception:
        logger.warning("Failed to clear vector store", exc_info=True)


async def show_stats() -> None:
    async with AsyncSessionLocal() as db:
        documents = await db.scalar(select(func.count(Document.id)))
        sections = await db.scalar(select(func.count(DocumentSection.id)))

    vectors = SearchService().get_collection_stats().get("count", 0)

    logger.info(
        "Documents: %d | Sections: %d | Vectors: %d",
        documents,
        sections,
        vectors,
    )
