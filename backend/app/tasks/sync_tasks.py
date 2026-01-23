import logging
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.services.dependency_service import DependencyService
from app.services.search_service import SearchService
from app.utils.celery_helpers import run_async, DBSessionContext, update_task_progress

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.sync_tasks.rebuild_all_dependencies"
)
def rebuild_all_dependencies_task(self) -> dict:

    logger.info("Rebuilding all document dependencies")
    
    async def _rebuild():
        async with DBSessionContext() as db:
            service = DependencyService(db)
            
            total_dependencies = await service.rebuild_all_dependencies()
            
            return {
                "success": True,
                "total_dependencies": total_dependencies,
            }
    
    return run_async(_rebuild())


@celery_app.task(
    bind=True,
    name="app.tasks.sync_tasks.sync_chromadb"
)
def sync_chromadb_task(self) -> dict:

    logger.info("Syncing all documents to ChromaDB")
    
    async def _sync():
        async with DBSessionContext() as db:
            result = await db.execute(
                select(Document).options(selectinload(Document.sections))
            )
            documents = result.scalars().all()
            
            search_service = SearchService()
            await search_service.initialize()
            
            search_service.clear_collection()
            
            total_docs = len(documents)
            total_sections = 0
            sections_synced = 0
            errors = []
            
            for i, doc in enumerate(documents):
                try:
                    for section in doc.sections:
                        total_sections += 1
                        
                        if not section.content.strip():
                            continue
                        
                        try:
                            await search_service.add_section(
                                section_id=str(section.id),
                                content=section.content,
                                metadata={
                                    "document_id": str(doc.id),
                                    "file_path": doc.file_path,
                                    "section_title": section.section_title,
                                    "order": section.order,
                                },
                            )
                            sections_synced += 1
                        except Exception as e:
                            logger.error(f"Failed to sync section {section.id}: {e}")
                            errors.append({
                                "document_id": str(doc.id),
                                "section_id": str(section.id),
                                "error": str(e)
                            })

                    await update_task_progress(
                        self.request.id,
                        i + 1,
                        total_docs,
                        f"Synced {i + 1}/{total_docs} documents ({sections_synced} sections)"
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to sync document {doc.id}: {e}")
                    errors.append({
                        "document_id": str(doc.id),
                        "error": str(e)
                    })
            
            await search_service.close()
            
            return {
                "success": True,
                "documents_processed": total_docs,
                "total_sections": total_sections,
                "sections_synced": sections_synced,
                "errors": errors,
            }
    
    return run_async(_sync())


@celery_app.task(name="app.tasks.sync_tasks.verify_chromadb_integrity")
def verify_chromadb_integrity_task() -> dict:

    logger.info("Verifying ChromaDB integrity")
    
    async def _verify():
        async with DBSessionContext() as db:
            result = await db.execute(select(DocumentSection))
            sections = result.scalars().all()
            
            search_service = SearchService()
            await search_service.initialize()
            
            stats = search_service.get_collection_stats()
            
            missing_embeddings = []
            for section in sections:
                if not section.embedding_id:
                    missing_embeddings.append(str(section.id))
            
            await search_service.close()
            
            return {
                "total_sections_in_db": len(sections),
                "total_embeddings_in_chromadb": stats.get("count", 0),
                "sections_missing_embeddings": len(missing_embeddings),
                "missing_embedding_ids": missing_embeddings[:100],
                "chromadb_initialized": stats.get("initialized", False),
            }
    
    return run_async(_verify())


@celery_app.task(name="app.tasks.sync_tasks.cleanup_orphaned_embeddings")
def cleanup_orphaned_embeddings_task() -> dict:

    logger.info("Cleaning up orphaned embeddings in ChromaDB")
    
    async def _cleanup():
        async with DBSessionContext() as db:
            result = await db.execute(select(DocumentSection.id))
            valid_section_ids = {str(row[0]) for row in result}
            
            search_service = SearchService()
            await search_service.initialize()
 
            stats = search_service.get_collection_stats()
            
            await search_service.close()
            
            return {
                "valid_sections": len(valid_section_ids),
                "chromadb_count": stats.get("count", 0),
                "message": "Full cleanup requires SearchService.list_all_ids() method",
            }
    
    return run_async(_cleanup())


@celery_app.task(name="app.tasks.sync_tasks.health_check")
def health_check_task() -> dict:

    logger.info("Performing system health check")
    
    async def _health_check():
        results = {
            "database": False,
            "chromadb": False,
            "redis": True, 
        }

        try:
            async with DBSessionContext() as db:
                result = await db.execute(select(1))
                results["database"] = result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
        
        try:
            search_service = SearchService()
            await search_service.initialize()
            stats = search_service.get_collection_stats()
            results["chromadb"] = stats.get("initialized", False)
            await search_service.close()
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
        
        return {
            "healthy": all(results.values()),
            "services": results,
        }
    
    return run_async(_health_check())