from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db import get_db
from app.models.document import Document, DocumentSection
from app.models.history import UserAction
from app.models.query import Query
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.schemas.history import HistoryCreate
from app.schemas.suggestion import (
    BulkSuggestionUpdate,
    SuggestionApplyRequest,
    SuggestionApplyResponse,
    SuggestionResponse,
    SuggestionUpdate,
    SuggestionWithContext,
)
from app.services.document_service import DocumentService
from app.services.history_service import HistoryService
from app.services.search_service import search_service

router = APIRouter()


@router.get("/{suggestion_id}", response_model=SuggestionWithContext)
async def get_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EditSuggestion).where(EditSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )
    
    section_result = await db.execute(
        select(DocumentSection)
        .options(selectinload(DocumentSection.document))
        .where(DocumentSection.id == suggestion.section_id)
    )
    section = section_result.scalar_one_or_none()
    
    section_title = None
    file_path = None
    full_content = ""
    
    if section:
        section_title = section.section_title
        full_content = section.content
        if section.document:
            file_path = section.document.file_path
    
    # TODO: Get affected sections (dependencies)
    affected_sections = []
    
    return SuggestionWithContext(
        id=suggestion.id,
        query_id=suggestion.query_id,
        section_id=suggestion.section_id,
        original_text=suggestion.original_text,
        suggested_text=suggestion.suggested_text,
        reasoning=suggestion.reasoning,
        confidence=suggestion.confidence,
        status=suggestion.status,
        edited_text=suggestion.edited_text,
        created_at=suggestion.created_at,
        updated_at=suggestion.updated_at,
        section_title=section_title,
        file_path=file_path,
        full_section_content=full_content,
        affected_sections=affected_sections,
    )


@router.patch("/{suggestion_id}", response_model=SuggestionResponse)
async def update_suggestion(
    suggestion_id: UUID,
    data: SuggestionUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EditSuggestion).where(EditSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )
    
    if data.status is not None:
        suggestion.status = data.status
    
    if data.edited_text is not None:
        suggestion.edited_text = data.edited_text
        suggestion.status = SuggestionStatus.EDITED
    
    await db.commit()
    await db.refresh(suggestion)

    section_result = await db.execute(
        select(DocumentSection)
        .options(selectinload(DocumentSection.document))
        .where(DocumentSection.id == suggestion.section_id)
    )
    section = section_result.scalar_one_or_none()
    
    return SuggestionResponse(
        id=suggestion.id,
        query_id=suggestion.query_id,
        section_id=suggestion.section_id,
        original_text=suggestion.original_text,
        suggested_text=suggestion.suggested_text,
        reasoning=suggestion.reasoning,
        confidence=suggestion.confidence,
        status=suggestion.status,
        edited_text=suggestion.edited_text,
        created_at=suggestion.created_at,
        updated_at=suggestion.updated_at,
        section_title=section.section_title if section else None,
        file_path=section.document.file_path if section and section.document else None,
    )


@router.post("/{suggestion_id}/apply", response_model=SuggestionApplyResponse)
async def apply_suggestion(
    suggestion_id: UUID,
    data: SuggestionApplyRequest,
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(EditSuggestion).where(EditSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )
    
    if suggestion.status == SuggestionStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot apply rejected suggestion",
        )
    
    section_result = await db.execute(
        select(DocumentSection)
        .options(selectinload(DocumentSection.document))
        .where(DocumentSection.id == suggestion.section_id)
    )
    section = section_result.scalar_one_or_none()
    
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )
    
    if data.use_edited_text and suggestion.edited_text:
        new_text = suggestion.edited_text
        action = UserAction.EDITED
    else:
        new_text = suggestion.suggested_text
        action = UserAction.ACCEPTED
    
    old_content = section.content
    
    doc_service = DocumentService(db)
    await doc_service.update_section_content(section.id, new_text)

    suggestion.status = SuggestionStatus.ACCEPTED
  
    history_service = HistoryService(db)
    
    query_result = await db.execute(
        select(Query).where(Query.id == suggestion.query_id)
    )
    query = query_result.scalar_one_or_none()
    
    history = await history_service.create(
        HistoryCreate(
            document_id=section.document_id,
            section_id=section.id,
            suggestion_id=suggestion.id,
            old_content=old_content,
            new_content=new_text,
            user_action=action,
            query_text=query.query_text if query else None,
            file_path=section.document.file_path if section.document else None,
            section_title=section.section_title,
        )
    )
    
    await search_service.update_section(
        section_id=section.id,
        content=new_text,
        metadata={
            "document_id": str(section.document_id),
            "file_path": section.document.file_path if section.document else "",
            "section_title": section.section_title or "",
            "order": section.order,
        },
    )
    
    await db.commit()
    
    await db.refresh(section)
    document = await doc_service.get_by_id(section.document_id)
    
    return SuggestionApplyResponse(
        success=True,
        message="Suggestion applied successfully",
        history_id=history.id,
        new_document_content=document.content if document else None,
    )


@router.post("/bulk", response_model=list[SuggestionResponse])
async def bulk_update_suggestions(
    data: BulkSuggestionUpdate,
    db: AsyncSession = Depends(get_db),
):
    updated = []
    
    for suggestion_id in data.suggestion_ids:
        result = await db.execute(
            select(EditSuggestion).where(EditSuggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()
        
        if suggestion:
            suggestion.status = data.status
            updated.append(suggestion)
    
    await db.commit()
    
    responses = []
    for s in updated:
        section_result = await db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == s.section_id)
        )
        section = section_result.scalar_one_or_none()
        
        responses.append(
            SuggestionResponse(
                id=s.id,
                query_id=s.query_id,
                section_id=s.section_id,
                original_text=s.original_text,
                suggested_text=s.suggested_text,
                reasoning=s.reasoning,
                confidence=s.confidence,
                status=s.status,
                edited_text=s.edited_text,
                created_at=s.created_at,
                updated_at=s.updated_at,
                section_title=section.section_title if section else None,
                file_path=section.document.file_path if section and section.document else None,
            )
        )
    
    return responses
