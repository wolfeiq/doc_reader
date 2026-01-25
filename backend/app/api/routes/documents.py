from __future__ import annotations
import logging
from typing import Annotated
from uuid import UUID
from backend.app.api.utils.helper import (
    decode_upload_file, 
    get_document_or_404, 
    get_pending_suggestions_by_section,
    get_recent_history_by_section, 
    get_sections_or_404
)
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.history import EditHistory, UserAction
from app.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentPreviewResponse,
    DocumentResponse,
    DocumentSectionInfo,
    DependencyGraphResponse,
    ReindexResponse,
    SectionPreview,
    ChangeType,
)
from app.services.dependency_service import DependencyService
from app.services.document_service import DocumentService
from app.tasks.document_tasks import (
    generate_embeddings_task,
    reindex_document_task,
)
from app.utils.celery_helpers import get_task_info

logger = logging.getLogger(__name__)
router = APIRouter()

DBSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/", response_model=list[DocumentListResponse])
async def list_documents(
    db: DBSession,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DocumentListResponse]:
    service = DocumentService(db)
    docs = await service.list_documents(skip=skip, limit=limit)
    return [
        DocumentListResponse(
            id=doc.id,
            file_path=doc.file_path,
            title=doc.title,
            checksum=doc.checksum,
            section_count=len(doc.sections) if doc.sections else 0,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in docs
    ]


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc_in: DocumentCreate, 
    db: DBSession,
    async_embeddings: bool = Query(default=True, description="Generate embeddings asynchronously")
) -> DocumentResponse:

    service = DocumentService(db)
    

    doc = await service.create_document(
        file_path=doc_in.file_path, 
        content=doc_in.content,
        generate_embeddings=not async_embeddings 
    )
    await db.refresh(doc, ["sections"])

    if async_embeddings:
        task = generate_embeddings_task.delay(str(doc.id))
        logger.info(f"Started embedding task {task.id} for document {doc.id}")
    
    return DocumentResponse(
        id=doc.id,
        file_path=doc.file_path,
        title=doc.title,
        content=doc.content,
        checksum=doc.checksum,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        sections=list(doc.sections) if doc.sections else []
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: DBSession, 
    file: UploadFile = File(...),
    async_embeddings: bool = Query(default=True, description="Generate embeddings asynchronously")
) -> DocumentResponse:
    content_str = await decode_upload_file(file)
    service = DocumentService(db)
    
    doc = await service.create_document(
        file_path=file.filename or "untitled", 
        content=content_str,
        generate_embeddings=not async_embeddings
    )
    await db.refresh(doc, ["sections"])
    
    if async_embeddings:
        task = generate_embeddings_task.delay(str(doc.id))
        logger.info(f"Started embedding task {task.id} for document {doc.id}")
    
    return DocumentResponse(
        id=doc.id,
        file_path=doc.file_path,
        title=doc.title,
        content=doc.content,
        checksum=doc.checksum,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        sections=list(doc.sections) if doc.sections else []
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID, 
    db: DBSession
) -> DocumentResponse:
    service = DocumentService(db)
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Document not found"
        )
    
    return DocumentResponse(
        id=doc.id,
        file_path=doc.file_path,
        title=doc.title,
        content=doc.content,
        checksum=doc.checksum,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        sections=list(doc.sections) if doc.sections else []
    )



@router.get("/{document_id}/preview", response_model=DocumentPreviewResponse)
async def preview_document(
    document_id: UUID, 
    db: DBSession,
    include_history_hours: int = Query(
        default=24, 
        ge=0, 
        le=168,  
        description="Include accepted/rejected changes from the last N hours (0 to disable)"
    ),
) -> DocumentPreviewResponse:
    doc = await get_document_or_404(db, document_id)
    section_ids = [s.id for s in doc.sections]

    pending_by_section = await get_pending_suggestions_by_section(db, section_ids)
    
    history_by_section: dict[UUID, EditHistory] = {}
    if include_history_hours > 0:
        history_by_section = await get_recent_history_by_section(
            db, section_ids, hours=include_history_hours
        )

    preview_sections: list[SectionPreview] = []
    recent_change_count = 0
    
    for section in sorted(doc.sections, key=lambda s: s.order):
        suggestion = pending_by_section.get(section.id)
        history = history_by_section.get(section.id)
        
        if suggestion:

            preview_sections.append(
                SectionPreview(
                    section_id=section.id,
                    section_title=section.section_title,
                    original_content=section.content,
                    preview_content=(
                        suggestion.edited_text or suggestion.suggested_text
                    ),
                    suggestion_id=suggestion.id,
                    confidence=suggestion.confidence,
                    change_type=ChangeType.PENDING,
                    changed_at=suggestion.created_at.isoformat() if suggestion.created_at else None,
                )
            )
        elif history:
            recent_change_count += 1
            change_type = (
                ChangeType.ACCEPTED 
                if history.user_action == UserAction.ACCEPTED 
                else ChangeType.REJECTED
            )
            preview_sections.append(
                SectionPreview(
                    section_id=section.id,
                    section_title=section.section_title,
                    original_content=history.old_content,
                    preview_content=history.new_content,
                    suggestion_id=history.suggestion_id,
                    history_id=history.id,
                    confidence=None,
                    change_type=change_type,
                    changed_at=history.created_at.isoformat() if history.created_at else None,
                )
            )
        else:
            preview_sections.append(
                SectionPreview(
                    section_id=section.id,
                    section_title=section.section_title,
                    original_content=section.content,
                    preview_content=section.content,
                    suggestion_id=None,
                    confidence=None,
                    change_type=ChangeType.NONE,
                )
            )

    return DocumentPreviewResponse(
        id=doc.id,
        file_path=doc.file_path,
        title=doc.title,
        sections=preview_sections,
        has_pending_changes=bool(pending_by_section),
        pending_suggestion_count=len(pending_by_section),
        has_recent_changes=recent_change_count > 0,
        recent_change_count=recent_change_count,
    )


@router.get("/{document_id}/sections", response_model=list[DocumentSectionInfo])
async def get_document_sections(
    document_id: UUID, 
    db: DBSession
) -> list[DocumentSectionInfo]:
    sections = await get_sections_or_404(db, document_id)
    return [
        DocumentSectionInfo(
            id=s.id,
            section_title=s.section_title,
            content=s.content,
            order=s.order,
            start_line=s.start_line,
            end_line=s.end_line,
        )
        for s in sections
    ]


@router.get("/{document_id}/dependencies", response_model=DependencyGraphResponse)
async def get_document_dependencies(
    document_id: UUID, 
    db: DBSession
) -> DependencyGraphResponse:
    service = DependencyService(db)
    return await service.build_dependency_graph(document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID, 
    db: DBSession
) -> None:

    service = DocumentService(db)
    success = await service.delete_document(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Document not found"
        )


@router.post("/{document_id}/reindex")
async def reindex_document(
    document_id: UUID, 
    db: DBSession
) -> dict:

    doc = await get_document_or_404(db, document_id)
    
    task = reindex_document_task.delay(str(document_id))
    
    logger.info(f"Started reindex task {task.id} for document {document_id}")
    
    return {
        "message": "Reindexing started in background",
        "document_id": str(document_id),
        "task_id": task.id,
    }


@router.get("/{document_id}/task/{task_id}")
async def get_document_task_status(
    document_id: UUID,
    task_id: str,
    db: DBSession
) -> dict:

    await get_document_or_404(db, document_id)

    task_info = get_task_info(task_id)
    
    return {
        "document_id": str(document_id),
        **task_info
    }