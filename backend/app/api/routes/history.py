from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models.history import UserAction
from app.schemas.history import HistoryFilter, HistoryListResponse, HistoryResponse
from app.services.history_service import HistoryService

router = APIRouter()


@router.get("", response_model=HistoryListResponse)
async def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_id: Optional[UUID] = None,
    user_action: Optional[UserAction] = None,
    db: AsyncSession = Depends(get_db),
):
    service = HistoryService(db)
    
    filters = HistoryFilter(
        document_id=document_id,
        user_action=user_action,
    )
    
    skip = (page - 1) * page_size
    items, total = await service.get_all(
        skip=skip,
        limit=page_size,
        filters=filters,
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return HistoryListResponse(
        items=[
            HistoryResponse(
                id=h.id,
                document_id=h.document_id,
                section_id=h.section_id,
                suggestion_id=h.suggestion_id,
                old_content=h.old_content,
                new_content=h.new_content,
                user_action=h.user_action,
                query_text=h.query_text,
                file_path=h.file_path,
                section_title=h.section_title,
                created_at=h.created_at,
            )
            for h in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/recent", response_model=list[HistoryResponse])
async def get_recent_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = HistoryService(db)
    items = await service.get_recent(limit=limit)
    
    return [
        HistoryResponse(
            id=h.id,
            document_id=h.document_id,
            section_id=h.section_id,
            suggestion_id=h.suggestion_id,
            old_content=h.old_content,
            new_content=h.new_content,
            user_action=h.user_action,
            query_text=h.query_text,
            file_path=h.file_path,
            section_title=h.section_title,
            created_at=h.created_at,
        )
        for h in items
    ]


@router.get("/stats")
async def get_history_stats(
    db: AsyncSession = Depends(get_db),
):
    service = HistoryService(db)
    return await service.get_stats()


@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history_entry(
    history_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = HistoryService(db)
    history = await service.get_by_id(history_id)
    
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History entry not found",
        )
    
    return HistoryResponse(
        id=history.id,
        document_id=history.document_id,
        section_id=history.section_id,
        suggestion_id=history.suggestion_id,
        old_content=history.old_content,
        new_content=history.new_content,
        user_action=history.user_action,
        query_text=history.query_text,
        file_path=history.file_path,
        section_title=history.section_title,
        created_at=history.created_at,
    )


@router.get("/document/{document_id}", response_model=list[HistoryResponse])
async def get_document_history(
    document_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    service = HistoryService(db)
    items = await service.get_by_document(document_id, skip=skip, limit=limit)
    
    return [
        HistoryResponse(
            id=h.id,
            document_id=h.document_id,
            section_id=h.section_id,
            suggestion_id=h.suggestion_id,
            old_content=h.old_content,
            new_content=h.new_content,
            user_action=h.user_action,
            query_text=h.query_text,
            file_path=h.file_path,
            section_title=h.section_title,
            created_at=h.created_at,
        )
        for h in items
    ]
