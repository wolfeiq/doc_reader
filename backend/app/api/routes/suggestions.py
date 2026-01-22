"""API routes for edit suggestions."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.models.history import EditHistory, UserAction
from app.services.document_service import DocumentService
from app.schemas.suggestion import SuggestionResponse, SuggestionUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.get("/{suggestion_id}", response_model=SuggestionResponse)
async def get_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a suggestion by ID."""
    result = await db.execute(
        select(EditSuggestion)
        .options(selectinload(EditSuggestion.section))
        .where(EditSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    return suggestion


@router.patch("/{suggestion_id}", response_model=SuggestionResponse)
async def update_suggestion(
    suggestion_id: UUID,
    update: SuggestionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a suggestion (status, edited_text)."""
    result = await db.execute(
        select(EditSuggestion)
        .options(selectinload(EditSuggestion.section))
        .where(EditSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    if update.status:
        suggestion.status = update.status
    if update.edited_text is not None:
        suggestion.edited_text = update.edited_text
    
    await db.commit()
    await db.refresh(suggestion)
    
    return suggestion


@router.post("/{suggestion_id}/accept", response_model=dict)
async def accept_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Accept and apply a suggestion to the document."""
    result = await db.execute(
        select(EditSuggestion)
        .options(
            selectinload(EditSuggestion.section).selectinload(
                __import__('app.models.document', fromlist=['DocumentSection']).DocumentSection.document
            ),
            selectinload(EditSuggestion.query)
        )
        .where(EditSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    if suggestion.status == SuggestionStatus.APPLIED:
        raise HTTPException(status_code=400, detail="Suggestion already applied")
    
    if not suggestion.section:
        raise HTTPException(status_code=400, detail="Section not found")
    
    # Use edited_text if user modified, otherwise use suggested_text
    new_content = suggestion.edited_text or suggestion.suggested_text
    old_content = suggestion.original_text
    
    # Apply to section
    doc_service = DocumentService(db)
    await doc_service.apply_suggestion_to_section(
        section_id=suggestion.section_id,
        new_content=new_content
    )
    
    # Update suggestion status
    suggestion.status = SuggestionStatus.APPLIED
    
    # Create history entry
    history = EditHistory(
        document_id=suggestion.section.document_id,
        section_id=suggestion.section_id,
        suggestion_id=suggestion.id,
        old_content=old_content,
        new_content=new_content,
        user_action=UserAction.ACCEPTED,
        query_text=suggestion.query.query_text if suggestion.query else None,
        file_path=suggestion.section.document.file_path if suggestion.section.document else None,
        section_title=suggestion.section.section_title
    )
    db.add(history)
    
    await db.commit()
    
    logger.info(f"Applied suggestion {suggestion_id}")
    
    return {
        "success": True,
        "suggestion_id": str(suggestion_id),
        "section_id": str(suggestion.section_id),
        "message": "Suggestion applied successfully"
    }


@router.post("/{suggestion_id}/reject", response_model=dict)
async def reject_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Reject a suggestion."""
    result = await db.execute(
        select(EditSuggestion)
        .options(
            selectinload(EditSuggestion.section),
            selectinload(EditSuggestion.query)
        )
        .where(EditSuggestion.id == suggestion_id)
    )
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    if suggestion.status != SuggestionStatus.PENDING:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot reject suggestion with status {suggestion.status.value}"
        )
    
    suggestion.status = SuggestionStatus.REJECTED
    
    # Create history entry
    history = EditHistory(
        document_id=suggestion.section.document_id if suggestion.section else None,
        section_id=suggestion.section_id,
        suggestion_id=suggestion.id,
        old_content=suggestion.original_text,
        new_content=suggestion.original_text,  # No change
        user_action=UserAction.REJECTED,
        query_text=suggestion.query.query_text if suggestion.query else None,
        file_path=suggestion.section.document.file_path if suggestion.section and suggestion.section.document else None,
        section_title=suggestion.section.section_title if suggestion.section else None
    )
    db.add(history)
    
    await db.commit()
    
    logger.info(f"Rejected suggestion {suggestion_id}")
    
    return {
        "success": True,
        "suggestion_id": str(suggestion_id),
        "message": "Suggestion rejected"
    }


@router.post("/{suggestion_id}/apply", response_model=dict)
async def apply_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Alias for accept - apply a suggestion to the document."""
    return await accept_suggestion(suggestion_id, db)
