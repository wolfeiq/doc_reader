from __future__ import annotations
import logging
from typing import Annotated
from uuid import UUID
from backend.app.api.utils.helper import (
    decode_upload_file, 
    get_document_or_404, 
    get_pending_suggestions_by_section, 
    get_sections_or_404
)
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.document import Document, DocumentSection
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentPreviewResponse,
    DocumentResponse,
    DocumentSectionInfo,
    DependencyGraphResponse,
    ReindexResponse,
    SectionPreview,
)
from app.services.dependency_service import DependencyService
from app.services.document_service import DocumentService

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
    db: DBSession
) -> DocumentResponse:

    service = DocumentService(db)
    doc = await service.create_document(file_path=doc_in.file_path, content=doc_in.content)
    await db.refresh(doc, ["sections"])
    
    return DocumentResponse(
        id=doc.id,
        file_path=doc.file_path,
        title=doc.title,
        content=doc.content,
        checksum=doc.checksum,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        sections=[
            section for section in doc.sections
        ] if doc.sections else []
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    db: DBSession, 
    file: UploadFile = File(...)
) -> DocumentResponse:

    content_str = await decode_upload_file(file)
    service = DocumentService(db)
    doc = await service.create_document(file_path=file.filename or "untitled", content=content_str)
    await db.refresh(doc, ["sections"])
    
    return DocumentResponse(
        id=doc.id,
        file_path=doc.file_path,
        title=doc.title,
        content=doc.content,
        checksum=doc.checksum,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        sections=[
            section for section in doc.sections
        ] if doc.sections else []
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
        sections=[
            section for section in doc.sections
        ] if doc.sections else []
    )


@router.get("/{document_id}/preview", response_model=DocumentPreviewResponse)
async def preview_document(
    document_id: UUID, 
    db: DBSession
) -> DocumentPreviewResponse:
    doc = await get_document_or_404(db, document_id)
    section_ids = [s.id for s in doc.sections]
    pending_by_section = await get_pending_suggestions_by_section(db, section_ids)

    preview_sections: list[SectionPreview] = []
    for section in sorted(doc.sections, key=lambda s: s.order):
        suggestion = pending_by_section.get(section.id)
        preview_sections.append(
            SectionPreview(
                section_id=section.id,
                section_title=section.section_title,
                original_content=section.content,
                preview_content=(
                    suggestion.edited_text or suggestion.suggested_text 
                    if suggestion else section.content
                ),
                suggestion_id=suggestion.id if suggestion else None,
                confidence=suggestion.confidence if suggestion else None,
            )
        )

    return DocumentPreviewResponse(
        id=doc.id,
        file_path=doc.file_path,
        title=doc.title,
        sections=preview_sections,
        has_pending_changes=bool(pending_by_section),
        pending_suggestion_count=len(pending_by_section),
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


@router.post("/{document_id}/reindex", response_model=ReindexResponse)
async def reindex_document(
    document_id: UUID, 
    db: DBSession
) -> ReindexResponse:

    doc = await get_document_or_404(db, document_id)
    service = DocumentService(db)
    updated_doc = await service.update_document(file_path=doc.file_path, content=doc.content)
    
    return ReindexResponse(
        success=True,
        document_id=document_id,
        sections_indexed=len(updated_doc.sections) if updated_doc.sections else 0,
    )