import logging
from datetime import datetime, timedelta
from uuid import UUID
from backend.app.api.utils.helper import get_history_or_404, list_history_entries
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, Row
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.history import EditHistory, UserAction
from app.schemas.history import HistoryResponse, HistoryStatsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=list[HistoryResponse])
async def list_history(
    skip: int = 0,
    limit: int = 20,
    action: UserAction | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[HistoryResponse]:
    return await list_history_entries(db, skip=skip, limit=limit, action=action)


@router.get("/document/{document_id}", response_model=list[HistoryResponse])
async def get_document_history(
    document_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
) -> list[HistoryResponse]:
    return await list_history_entries(db, skip=skip, limit=limit, document_id=document_id)


@router.get("/section/{section_id}", response_model=list[HistoryResponse])
async def get_section_history(
    section_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> list[HistoryResponse]:
    return await list_history_entries(db, section_id=section_id)


@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history_entry(
    history_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> HistoryResponse:
    return await get_history_or_404(db, history_id)


@router.get("/stats/summary", response_model=HistoryStatsResponse)
async def get_history_stats(db: AsyncSession = Depends(get_db)) -> HistoryStatsResponse:
    result = await db.execute(
        select(EditHistory.user_action, func.count(EditHistory.id))
        .group_by(EditHistory.user_action)
    )
    
    by_action: dict[str, int] = {}
    for row in result:
        action: UserAction = row[0]
        count: int = row[1]
        by_action[action.value] = count

    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_result = await db.execute(
        select(func.count(EditHistory.id))
        .where(EditHistory.created_at >= week_ago)
    )
    recent_count = recent_result.scalar() or 0
    
    return HistoryStatsResponse(
        by_action=by_action,
        total=sum(by_action.values()),
        last_7_days=recent_count
    )