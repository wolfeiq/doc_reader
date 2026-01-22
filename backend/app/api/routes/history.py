"""API routes for edit history."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.history import EditHistory, UserAction
from app.schemas.history import HistoryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/history", tags=["history"])


@router.get("/", response_model=list[HistoryResponse])
async def list_history(
    skip: int = 0,
    limit: int = 20,
    action: UserAction | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List edit history with optional action filter."""
    # Get total count
    count_stmt = select(func.count(EditHistory.id))
    if action:
        count_stmt = count_stmt.where(EditHistory.user_action == action)
    total = (await db.execute(count_stmt)).scalar() or 0
    
    # Get records
    stmt = select(EditHistory).order_by(EditHistory.created_at.desc())
    if action:
        stmt = stmt.where(EditHistory.user_action == action)
    stmt = stmt.offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    entries = result.scalars().all()
    
    return entries


@router.get("/document/{document_id}", response_model=list[HistoryResponse])
async def get_document_history(
    document_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get history for a specific document."""
    result = await db.execute(
        select(EditHistory)
        .where(EditHistory.document_id == document_id)
        .order_by(EditHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/section/{section_id}", response_model=list[HistoryResponse])
async def get_section_history(
    section_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get history for a specific section."""
    result = await db.execute(
        select(EditHistory)
        .where(EditHistory.section_id == section_id)
        .order_by(EditHistory.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{history_id}", response_model=HistoryResponse)
async def get_history_entry(
    history_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a single history entry."""
    result = await db.execute(
        select(EditHistory).where(EditHistory.id == history_id)
    )
    entry = result.scalar_one_or_none()
    
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    
    return entry


@router.get("/stats/summary")
async def get_history_stats(db: AsyncSession = Depends(get_db)):
    """Get summary statistics for edit history."""
    # Total by action
    result = await db.execute(
        select(EditHistory.user_action, func.count(EditHistory.id))
        .group_by(EditHistory.user_action)
    )
    by_action = {row[0].value: row[1] for row in result}
    
    # Recent activity (last 7 days)
    from datetime import datetime, timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent = await db.execute(
        select(func.count(EditHistory.id))
        .where(EditHistory.created_at >= week_ago)
    )
    
    return {
        "by_action": by_action,
        "total": sum(by_action.values()),
        "last_7_days": recent.scalar() or 0
    }
