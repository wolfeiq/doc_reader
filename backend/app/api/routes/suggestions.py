import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.api.utils import get_suggestion_or_404
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.models.history import EditHistory, UserAction
from app.models.document import DocumentSection
from app.services.document_service import DocumentService
from app.schemas.suggestion import (
    SuggestionResponse, 
    SuggestionUpdate,
    SuggestionActionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{suggestion_id}", response_model=SuggestionResponse)
async def get_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SuggestionResponse:

    suggestion = await get_suggestion_or_404(
        db,
        suggestion_id,
        options=[selectinload(EditSuggestion.section)],
    )
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
        section_title=suggestion.section.section_title if suggestion.section else None,
        file_path=(
            suggestion.section.document.file_path 
            if suggestion.section and suggestion.section.document 
            else None
        ),
    )


@router.patch("/{suggestion_id}", response_model=SuggestionResponse)
async def update_suggestion(
    suggestion_id: UUID,
    update: SuggestionUpdate,
    db: AsyncSession = Depends(get_db)
) -> SuggestionResponse:
    suggestion = await get_suggestion_or_404(
        db,
        suggestion_id,
        options=[selectinload(EditSuggestion.section)],
    )

    if update.status is not None:
        suggestion.status = update.status
    if update.edited_text is not None:
        suggestion.edited_text = update.edited_text

    await db.commit()
    await db.refresh(suggestion)

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
        section_title=suggestion.section.section_title if suggestion.section else None,
        file_path=(
            suggestion.section.document.file_path 
            if suggestion.section and suggestion.section.document 
            else None
        ),
    )


@router.post("/{suggestion_id}/accept", response_model=SuggestionActionResponse)
async def accept_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SuggestionActionResponse:
    suggestion = await get_suggestion_or_404(
        db,
        suggestion_id,
        options=[
            selectinload(EditSuggestion.section).selectinload(DocumentSection.document),
            selectinload(EditSuggestion.query),
        ],
    )

    if suggestion.status == SuggestionStatus.ACCEPTED:
        raise HTTPException(400, "Suggestion already applied")

    if not suggestion.section:
        raise HTTPException(400, "Section not found")

    new_content = suggestion.edited_text or suggestion.suggested_text
    old_content = suggestion.original_text

    doc_service = DocumentService(db)
    await doc_service.apply_suggestion_to_section(
        section_id=suggestion.section_id,
        new_content=new_content
    )

    suggestion.status = SuggestionStatus.ACCEPTED

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

    return SuggestionActionResponse(
        success=True,
        suggestion_id=suggestion_id,
        section_id=suggestion.section_id,
        message="Suggestion applied successfully"
    )


@router.post("/{suggestion_id}/reject", response_model=SuggestionActionResponse)
async def reject_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SuggestionActionResponse:
    suggestion = await get_suggestion_or_404(
        db,
        suggestion_id,
        options=[
            selectinload(EditSuggestion.section).selectinload(DocumentSection.document),
            selectinload(EditSuggestion.query),
        ],
    )

    if suggestion.status != SuggestionStatus.PENDING:
        raise HTTPException(
            400,
            f"Cannot reject suggestion with status {suggestion.status.value}"
        )

    suggestion.status = SuggestionStatus.REJECTED

    history = EditHistory(
        document_id=suggestion.section.document_id if suggestion.section else None,
        section_id=suggestion.section_id,
        suggestion_id=suggestion.id,
        old_content=suggestion.original_text,
        new_content=suggestion.original_text,  # No change
        user_action=UserAction.REJECTED,
        query_text=suggestion.query.query_text if suggestion.query else None,
        file_path=(
            suggestion.section.document.file_path 
            if suggestion.section and suggestion.section.document 
            else None
        ),
        section_title=suggestion.section.section_title if suggestion.section else None
    )
    db.add(history)
    await db.commit()

    logger.info(f"Rejected suggestion {suggestion_id}")

    return SuggestionActionResponse(
        success=True,
        suggestion_id=suggestion_id,
        section_id=suggestion.section_id,
        message="Suggestion rejected"
    )

