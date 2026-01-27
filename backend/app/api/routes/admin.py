"""Admin routes for database management."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.services.document_service import DocumentService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/seed")
async def seed_database(
    secret: str = Query(..., description="Admin secret for authorization"),
    clear: bool = Query(False, description="Clear existing data before seeding"),
    path: str = Query("data/openai-agents-sdk", description="Path to markdown files"),
):
    """Seed the database with documentation files."""
    # Simple secret check - set ADMIN_SECRET in Railway variables
    admin_secret = getattr(settings, 'admin_secret', None) or "seed-secret-change-me"
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    base_path = Path(path)
    if not base_path.exists():
        raise HTTPException(status_code=400, detail=f"Path {path} does not exist")

    try:
        search_service = SearchService()

        if clear:
            # Clear vectors
            try:
                search_service.clear_collection()
                logger.info("Cleared vector store")
            except Exception as e:
                logger.warning(f"Failed to clear vectors: {e}")

        # Find markdown files
        md_files = list(base_path.glob("**/*.md"))
        if not md_files:
            raise HTTPException(status_code=400, detail=f"No markdown files found in {path}")

        stats = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0}

        async with AsyncSessionLocal() as db:
            if clear:
                # Clear database tables
                from app.models.history import EditHistory
                from app.models.suggestion import EditSuggestion
                from app.models.query import Query
                from app.models.section_dependency import SectionDependency

                await db.execute(EditHistory.__table__.delete())
                await db.execute(EditSuggestion.__table__.delete())
                await db.execute(Query.__table__.delete())
                await db.execute(SectionDependency.__table__.delete())
                await db.execute(DocumentSection.__table__.delete())
                await db.execute(Document.__table__.delete())
                await db.commit()
                logger.info("Cleared database tables")

            service = DocumentService(db)

            for md_file in md_files:
                try:
                    content = md_file.read_text(encoding="utf-8").strip()
                    if not content:
                        stats["skipped"] += 1
                        continue

                    relative_path = str(md_file.relative_to(base_path))
                    existing = await service.get_document_by_path(relative_path)

                    if existing:
                        checksum = service.calculate_checksum(content)
                        if checksum != existing.checksum:
                            await service.update_document(relative_path, content)
                            stats["updated"] += 1
                        else:
                            stats["unchanged"] += 1
                    else:
                        await service.create_document(
                            file_path=relative_path,
                            content=content,
                            generate_embeddings=True,
                        )
                        stats["created"] += 1

                    await db.commit()
                except Exception as e:
                    stats["errors"] += 1
                    await db.rollback()
                    logger.exception(f"Failed processing {md_file}: {e}")

        return {
            "status": "success",
            "files_found": len(md_files),
            "stats": stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Seed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug-cors")
async def debug_cors():
    """Debug: show current CORS settings."""
    from app.config import settings
    return {
        "cors_origins": settings.cors_origins,
        "cors_origins_str": settings.cors_origins_str,
    }

@router.get("/stats")
async def get_stats(
    secret: str = Query(..., description="Admin secret for authorization"),
):
    """Get database statistics."""
    admin_secret = getattr(settings, 'admin_secret', None) or "seed-secret-change-me"
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")

    async with AsyncSessionLocal() as db:
        docs = await db.scalar(select(func.count(Document.id)))
        sections = await db.scalar(select(func.count(DocumentSection.id)))

    vectors = SearchService().get_collection_stats().get("count", 0)

    return {
        "documents": docs,
        "sections": sections,
        "vectors": vectors,
    }
