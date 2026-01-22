from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentPreview,
    DocumentResponse,
    DocumentUpdate,
)
from app.services.document_service import DocumentService
from app.services.search_service import search_service

router = APIRouter()


@router.get("", response_model=list[DocumentListResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all documents."""
    service = DocumentService(db)
    documents = await service.get_all(skip=skip, limit=limit)
    
    # Convert to list response (without full content)
    return [
        DocumentListResponse(
            id=doc.id,
            file_path=doc.file_path,
            title=doc.title,
            checksum=doc.checksum,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            section_count=len(doc.sections),
        )
        for doc in documents
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific document by ID."""
    service = DocumentService(db)
    document = await service.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    return document


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new document."""
    service = DocumentService(db)
    
    # Check if document already exists
    existing = await service.get_by_file_path(data.file_path)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with this file path already exists",
        )
    
    document = await service.create(data)
    
    # Index sections in ChromaDB
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
    
    return document


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a document."""
    service = DocumentService(db)
    
    # Get existing document to delete old embeddings
    existing = await service.get_by_id(document_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Delete old embeddings
    for section in existing.sections:
        await search_service.delete_section(section.id)
    
    # Update document
    document = await service.update(document_id, data)
    
    # Index new sections
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
    
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document."""
    service = DocumentService(db)
    
    # Get document to delete embeddings
    document = await service.get_by_id(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Delete embeddings
    for section in document.sections:
        await search_service.delete_section(section.id)
    
    # Delete document
    await service.delete(document_id)


@router.get("/{document_id}/preview", response_model=DocumentPreview)
async def preview_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a preview of the document with pending changes applied."""
    service = DocumentService(db)
    document = await service.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # TODO: Get pending suggestions and apply them to generate preview
    # For now, just return the current content
    return DocumentPreview(
        document=document,
        preview_content=document.content,
        pending_changes=[],
    )


@router.get("/stats/overview")
async def get_document_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get document statistics."""
    service = DocumentService(db)
    search_stats = await search_service.get_collection_stats()
    
    return {
        "total_documents": await service.get_document_count(),
        "total_sections": await service.get_section_count(),
        "search_index": search_stats,
    }
