import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.models.document_base import Document
from app.services.document_service import DocumentService
from app.services.search_service import SearchService
from app.utils.celery_helpers import run_async, DBSessionContext, update_task_progress

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.document_tasks.generate_embeddings",
    max_retries=3,
)
def generate_embeddings_task(self, document_id: str) -> dict:

    logger.info(f"Generating embeddings for document {document_id}")
    
    async def _generate():
        async with DBSessionContext() as db:
            result = await db.execute(
                select(Document)
                .options(selectinload(Document.sections))
                .where(Document.id == UUID(document_id))
            )
            doc = result.scalar_one_or_none()
            
            if not doc:
                raise ValueError(f"Document {document_id} not found")
            
            search_service = SearchService()
            await search_service.initialize()
            
            total_sections = len(doc.sections)
            embeddings_created = 0
            errors = []
            
            for i, section in enumerate(doc.sections):
                try:
                    if not section.content.strip():
                        continue
                    
                    embedding_id = await search_service.add_section(
                        section_id=str(section.id),
                        content=section.content,
                        metadata={
                            "document_id": str(doc.id),
                            "file_path": doc.file_path,
                            "section_title": section.section_title,
                            "order": section.order,
                        },
                    )
                    
                    section.embedding_id = embedding_id
                    embeddings_created += 1
                    
                    await update_task_progress(
                        self,
                        i + 1,
                        total_sections,
                        f"Generated {embeddings_created}/{total_sections} embeddings"
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to generate embedding for section {section.id}: {e}")
                    errors.append({
                        "section_id": str(section.id),
                        "error": str(e)
                    })
            
            await db.commit()
            await search_service.close()
            
            return {
                "document_id": document_id,
                "total_sections": total_sections,
                "embeddings_created": embeddings_created,
                "errors": errors,
            }
    
    return run_async(_generate())


@celery_app.task(name="app.tasks.document_tasks.reindex_document")
def reindex_document_task(document_id: str) -> dict:

    logger.info(f"Reindexing document {document_id}")
    
    async def _reindex():
        async with DBSessionContext() as db:
            result = await db.execute(
                select(Document)
                .options(selectinload(Document.sections))
                .where(Document.id == UUID(document_id))
            )
            doc = result.scalar_one_or_none()
            
            if not doc:
                raise ValueError(f"Document {document_id} not found")

            service = DocumentService(db)
            updated_doc = await service.update_document(
                file_path=doc.file_path,
                content=doc.content,
                generate_embeddings=True,
            )
            
            return {
                "document_id": document_id,
                "file_path": doc.file_path,
                "sections_indexed": len(updated_doc.sections),
            }
    
    return run_async(_reindex())


@celery_app.task(
    bind=True,
    name="app.tasks.document_tasks.bulk_embed_documents"
)
def bulk_embed_documents_task(self, document_ids: list[str]) -> dict:

    logger.info(f"Bulk embedding {len(document_ids)} documents")
    
    async def _bulk_embed():
        results = []
        
        for i, doc_id in enumerate(document_ids):
            try:
                result = generate_embeddings_task(doc_id)
                results.append({
                    "document_id": doc_id,
                    "success": True,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Failed to embed document {doc_id}: {e}")
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(e)
                })

            await update_task_progress(
                self,
                i + 1,
                len(document_ids),
                f"Processed {i + 1}/{len(document_ids)} documents"
            )
        
        successful = sum(1 for r in results if r["success"])
        
        return {
            "total_documents": len(document_ids),
            "successful": successful,
            "failed": len(document_ids) - successful,
            "results": results,
        }
    
    return run_async(_bulk_embed())


@celery_app.task(name="app.tasks.document_tasks.delete_document_embeddings")
def delete_document_embeddings_task(document_id: str) -> dict:

    logger.info(f"Deleting embeddings for document {document_id}")
    
    async def _delete():
        search_service = SearchService()
        await search_service.initialize()
        
        deleted_count = await search_service.delete_by_document(document_id)
        
        await search_service.close()
        
        return {
            "document_id": document_id,
            "sections_deleted": deleted_count,
        }
    
    return run_async(_delete())