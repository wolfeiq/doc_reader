"""API routes for document management."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.document import Document, DocumentSection
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.services.document_service import DocumentService
from app.services.dependency_service import DependencyService
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentListResponse,
    DocumentPreview
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentListResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all documents."""
    doc_service = DocumentService(db)
    docs = await doc_service.list_documents(skip=skip, limit=limit)
    
    # Add section counts
    result = []
    for doc in docs:
        section_count = len(doc.sections) if hasattr(doc, 'sections') and doc.sections else 0
        result.append({
            "id": doc.id,
            "file_path": doc.file_path,
            "title": doc.title,
            "checksum": doc.checksum,
            "section_count": section_count,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at
        })
    
    return result


@router.post("/", response_model=DocumentResponse, status_code=201)
async def create_document(
    doc_in: DocumentCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create or update a document."""
    doc_service = DocumentService(db)
    doc = await doc_service.create_document(
        file_path=doc_in.file_path,
        content=doc_in.content
    )
    await db.refresh(doc, ["sections"])
    return doc


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload a markdown document."""
    if not file.filename.endswith('.md'):
        raise HTTPException(status_code=400, detail="Only .md files are supported")
    
    content = await file.read()
    content_str = content.decode('utf-8')
    
    doc_service = DocumentService(db)
    doc = await doc_service.create_document(
        file_path=file.filename,
        content=content_str
    )
    await db.refresh(doc, ["sections"])
    return doc


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a document with its sections."""
    doc_service = DocumentService(db)
    doc = await doc_service.get_document(document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return doc


@router.get("/{document_id}/preview", response_model=DocumentPreview)
async def preview_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Preview document with pending suggestions applied."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.sections))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get pending suggestions for this document's sections
    section_ids = [s.id for s in doc.sections]
    suggestions_result = await db.execute(
        select(EditSuggestion)
        .where(
            EditSuggestion.section_id.in_(section_ids),
            EditSuggestion.status == SuggestionStatus.PENDING
        )
    )
    pending_suggestions = {s.section_id: s for s in suggestions_result.scalars()}
    
    # Build preview content with suggestions applied
    preview_sections = []
    has_changes = False
    
    for section in sorted(doc.sections, key=lambda s: s.order):
        suggestion = pending_suggestions.get(section.id)
        if suggestion:
            has_changes = True
            preview_sections.append({
                "section_id": str(section.id),
                "section_title": section.section_title,
                "original_content": section.content,
                "preview_content": suggestion.edited_text or suggestion.suggested_text,
                "suggestion_id": str(suggestion.id),
                "confidence": suggestion.confidence
            })
        else:
            preview_sections.append({
                "section_id": str(section.id),
                "section_title": section.section_title,
                "original_content": section.content,
                "preview_content": section.content,
                "suggestion_id": None,
                "confidence": None
            })
    
    return {
        "id": doc.id,
        "file_path": doc.file_path,
        "title": doc.title,
        "sections": preview_sections,
        "has_pending_changes": has_changes,
        "pending_suggestion_count": len(pending_suggestions)
    }


@router.get("/{document_id}/sections")
async def get_document_sections(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all sections of a document."""
    result = await db.execute(
        select(DocumentSection)
        .where(DocumentSection.document_id == document_id)
        .order_by(DocumentSection.order)
    )
    sections = result.scalars().all()
    
    if not sections:
        # Check if document exists
        doc_result = await db.execute(select(Document).where(Document.id == document_id))
        if not doc_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Document not found")
    
    return [
        {
            "id": str(s.id),
            "section_title": s.section_title,
            "content": s.content,
            "order": s.order,
            "start_line": s.start_line,
            "end_line": s.end_line
        }
        for s in sections
    ]


@router.get("/{document_id}/dependencies")
async def get_document_dependencies(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get dependency graph for a document."""
    dep_service = DependencyService(db)
    graph = await dep_service.build_dependency_graph(document_id)
    return graph


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a document."""
    doc_service = DocumentService(db)
    success = await doc_service.delete_document(document_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")


@router.post("/{document_id}/reindex")
async def reindex_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Reindex a document's embeddings."""
    doc_service = DocumentService(db)
    doc = await doc_service.get_document(document_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Re-create document (this rebuilds embeddings)
    updated_doc = await doc_service.update_document(
        file_path=doc.file_path,
        content=doc.content
    )
    
    return {
        "success": True,
        "document_id": str(document_id),
        "sections_indexed": len(updated_doc.sections) if updated_doc.sections else 0
    }
