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
from app.schemas.query import (
    QueryCreate, 
    QueryResponse, 
    QueryDetailResponse,
    QuerySuggestionListItem,
    QueryProcessResponse,
)
from app.ai.orchestrator import process_query
from app.api.utils import get_query_or_404

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=QueryResponse, status_code=201)
async def create_query(
    query_in: QueryCreate,
    db: AsyncSession = Depends(get_db)
) -> QueryResponse:
    query = Query(
        query_text=query_in.query_text,
        status=QueryStatus.PENDING,
        status_message="Query created, waiting to process"
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    
    logger.info(f"Created query {query.id}: {query_in.query_text[:50]}...")
    
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


@router.get("/", response_model=list[QueryResponse])
async def list_queries(
    skip: int = 0,
    limit: int = 50,
    status: QueryStatus | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[QueryResponse]:
    stmt = select(Query).order_by(Query.created_at.desc())
    
    if status:
        stmt = stmt.where(Query.status == status)
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    queries = result.scalars().all()
    

    responses: list[QueryResponse] = []
    for query in queries:
        count_result = await db.execute(
            select(func.count(EditSuggestion.id))
            .where(EditSuggestion.query_id == query.id)
        )
        suggestion_count = count_result.scalar() or 0
        
        responses.append(
            QueryResponse(
                id=query.id,
                query_text=query.query_text,
                status=query.status,
                status_message=query.status_message,
                completed_at=query.completed_at,
                error_message=query.error_message,
                created_at=query.created_at,
                updated_at=query.updated_at,
                suggestion_count=suggestion_count,
            )
        )
    
    return responses


@router.get("/{query_id}", response_model=QueryDetailResponse)
async def get_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> QueryDetailResponse:
    query = await get_query_or_404(
        db,
        query_id,
        options=[selectinload(Query.suggestions)]
    )
    
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
        suggestions=[
            # Convert to SuggestionResponse
            suggestion for suggestion in query.suggestions
        ]
    )


@router.get("/{query_id}/suggestions", response_model=list[QuerySuggestionListItem])
async def get_query_suggestions(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> list[QuerySuggestionListItem]:
    await get_query_or_404(db, query_id)
    
    result = await db.execute(
        select(EditSuggestion)
        .options(selectinload(EditSuggestion.section))
        .where(EditSuggestion.query_id == query_id)
        .order_by(EditSuggestion.confidence.desc())
    )
    suggestions = result.scalars().all()
    
    return [
        QuerySuggestionListItem(
            id=s.id,
            section_id=s.section_id,
            section_title=s.section.section_title if s.section else None,
            original_text=s.original_text,
            suggested_text=s.suggested_text,
            reasoning=s.reasoning,
            confidence=s.confidence,
            status=s.status.value,
            created_at=s.created_at
        )
        for s in suggestions
    ]


@router.post("/{query_id}/process")
async def process_query_stream(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> EventSourceResponse:
    query = await get_query_or_404(db, query_id)
    
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


@router.post("/{query_id}/process/sync", response_model=QueryProcessResponse)
async def process_query_sync(
    query_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> QueryProcessResponse:
    query = await get_query_or_404(db, query_id)
    
    if query.status not in (QueryStatus.PENDING, QueryStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Query already {query.status.value}"
        )
    
    async def run_processing() -> None:
        async for _ in process_query(query_id, query.query_text, db):
            pass  # Consume all events
    
    background_tasks.add_task(run_processing)
    
    return QueryProcessResponse(
        message="Processing started",
        query_id=query_id
    )


@router.delete("/{query_id}", status_code=204)
async def delete_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> None:

    query = await get_query_or_404(db, query_id)
    await db.delete(query)
    await db.commit()