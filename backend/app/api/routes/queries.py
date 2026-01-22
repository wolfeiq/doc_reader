"""API routes for query management."""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion
from app.schemas.query import QueryCreate, QueryResponse, QueryDetailResponse
from app.ai.orchestrator import process_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/queries", tags=["queries"])


@router.post("/", response_model=QueryResponse, status_code=201)
async def create_query(
    query_in: QueryCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new query."""
    query = Query(
        query_text=query_in.query_text,
        status=QueryStatus.PENDING,
        status_message="Query created, waiting to process"
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    
    logger.info(f"Created query {query.id}: {query_in.query_text[:50]}...")
    return query


@router.get("/", response_model=list[QueryResponse])
async def list_queries(
    skip: int = 0,
    limit: int = 50,
    status: QueryStatus | None = None,
    db: AsyncSession = Depends(get_db)
):
    """List queries with optional status filter."""
    stmt = select(Query).order_by(Query.created_at.desc())
    
    if status:
        stmt = stmt.where(Query.status == status)
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    queries = result.scalars().all()
    
    # Add suggestion counts
    for query in queries:
        count_result = await db.execute(
            select(func.count(EditSuggestion.id))
            .where(EditSuggestion.query_id == query.id)
        )
        query.suggestion_count = count_result.scalar() or 0
    
    return queries


@router.get("/{query_id}", response_model=QueryDetailResponse)
async def get_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get query details with suggestions."""
    result = await db.execute(
        select(Query)
        .options(selectinload(Query.suggestions))
        .where(Query.id == query_id)
    )
    query = result.scalar_one_or_none()
    
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    
    query.suggestion_count = len(query.suggestions)
    return query


@router.get("/{query_id}/suggestions")
async def get_query_suggestions(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all suggestions for a query."""
    # Verify query exists
    query_result = await db.execute(select(Query).where(Query.id == query_id))
    if not query_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Query not found")
    
    result = await db.execute(
        select(EditSuggestion)
        .options(selectinload(EditSuggestion.section))
        .where(EditSuggestion.query_id == query_id)
        .order_by(EditSuggestion.confidence.desc())
    )
    suggestions = result.scalars().all()
    
    return [
        {
            "id": str(s.id),
            "section_id": str(s.section_id),
            "section_title": s.section.section_title if s.section else None,
            "original_text": s.original_text,
            "suggested_text": s.suggested_text,
            "reasoning": s.reasoning,
            "confidence": s.confidence,
            "status": s.status.value,
            "created_at": s.created_at.isoformat()
        }
        for s in suggestions
    ]


@router.post("/{query_id}/process")
async def process_query_stream(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Start processing a query and stream results via SSE."""
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    
    if query.status not in (QueryStatus.PENDING, QueryStatus.FAILED):
        raise HTTPException(
            status_code=400, 
            detail=f"Query already {query.status.value}"
        )
    
    async def event_generator():
        async for event in process_query(query_id, query.query_text, db):
            yield {
                "event": event["event"],
                "data": json.dumps(event["data"])
            }
    
    return EventSourceResponse(event_generator())


@router.post("/{query_id}/process/sync")
async def process_query_sync(
    query_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start processing a query in background (non-streaming)."""
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    
    if query.status not in (QueryStatus.PENDING, QueryStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Query already {query.status.value}"
        )
    
    async def run_processing():
        async for _ in process_query(query_id, query.query_text, db):
            pass  # Consume all events
    
    background_tasks.add_task(run_processing)
    
    return {"message": "Processing started", "query_id": str(query_id)}


@router.delete("/{query_id}", status_code=204)
async def delete_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a query and its suggestions."""
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    
    await db.delete(query)
    await db.commit()
