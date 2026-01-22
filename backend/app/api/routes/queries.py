import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse
from app.db import get_db
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion
from app.schemas.query import QueryCreate, QueryDetailResponse, QueryResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def create_query(
    data: QueryCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    
    # -> { "query_text": "We don't support as_tool..." }

    query = Query(
        query_text=data.query_text,
        status=QueryStatus.PENDING,
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    
    logger.info(f"Created query {query.id}: {data.query_text[:50]}...")
    
    # creates the query record 
    
    return QueryResponse(
        id=query.id,
        query_text=query.query_text,
        status=query.status,
        status_message=query.status_message,
        completed_at=query.completed_at,
        error_message=query.error_message,
        created_at=query.created_at,
        updated_at=query.updated_at,
        suggestion_count=0,
    )


@router.get("/{query_id}", response_model=QueryDetailResponse)
async def get_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific query with its suggestions."""
    result = await db.execute(
        select(Query)
        .options(selectinload(Query.suggestions))
        .where(Query.id == query_id)
    )
    query = result.scalar_one_or_none()
    
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    
    # Build response with suggestions
    suggestions = []
    for s in query.suggestions:
        # Get section info
        section_result = await db.execute(
            select(s.__class__).where(s.__class__.id == s.id)
        )
        suggestions.append({
            "id": s.id,
            "query_id": s.query_id,
            "section_id": s.section_id,
            "original_text": s.original_text,
            "suggested_text": s.suggested_text,
            "reasoning": s.reasoning,
            "confidence": s.confidence,
            "status": s.status,
            "edited_text": s.edited_text,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
            "section_title": None,  # TODO: Join with section
            "file_path": None,  # TODO: Join with document
        })
    
    return QueryDetailResponse(
        id=query.id,
        query_text=query.query_text,
        status=query.status,
        status_message=query.status_message,
        completed_at=query.completed_at,
        error_message=query.error_message,
        created_at=query.created_at,
        updated_at=query.updated_at,
        suggestion_count=len(query.suggestions),
        suggestions=suggestions,
    )


@router.get("/{query_id}/stream")
async def stream_query_progress(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Stream query processing progress via SSE."""
    # Verify query exists
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    
    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events for query progress."""
        from app.ai.orchestrator import process_query
        from app.db.session import async_session_maker
        from app.services.search_service import search_service
        
        try:
            # Use a new session for the background processing
            async with async_session_maker() as session:
                async for event in process_query(
                    query_id=query_id,
                    query_text=query.query_text,
                    db=session,
                    search_service=search_service,
                ):
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"]),
                    }
                    
        except Exception as e:
            logger.error(f"Error processing query {query_id}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
    
    return EventSourceResponse(event_generator())


@router.get("", response_model=list[QueryResponse])
async def list_queries(
    skip: int = 0,
    limit: int = 50,
    status_filter: QueryStatus = None,
    db: AsyncSession = Depends(get_db),
):
    """List all queries."""
    query = select(Query).options(selectinload(Query.suggestions))
    
    if status_filter:
        query = query.where(Query.status == status_filter)
    
    query = query.order_by(Query.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    queries = result.scalars().all()
    
    return [
        QueryResponse(
            id=q.id,
            query_text=q.query_text,
            status=q.status,
            status_message=q.status_message,
            completed_at=q.completed_at,
            error_message=q.error_message,
            created_at=q.created_at,
            updated_at=q.updated_at,
            suggestion_count=len(q.suggestions),
        )
        for q in queries
    ]


@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a query and its suggestions."""
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found",
        )
    
    await db.delete(query)
    await db.commit()
