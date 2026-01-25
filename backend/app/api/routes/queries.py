from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db
from app.api.utils import get_query_or_404
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion
from app.models.document import DocumentSection
from app.schemas.query import (
    QueryCreate,
    QueryResponse,
    QueryDetailResponse,
    QuerySuggestionListItem,
    QueryProcessResponse,
)
from app.schemas.suggestion import SuggestionResponse
from app.schemas.tasks import TaskStatusResponse, TaskProgressInfo
from app.ai.orchestrator import QueryOrchestrator
from app.services.event_service import (
    DirectEventPublisher,
    RedisEventSubscriber,
    EventEmitter,
    EventType,
)
from app.tasks.query_tasks import process_query_async
from app.utils.celery_helpers import get_task_info

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=QueryResponse, status_code=201)
async def create_query(
    query_in: QueryCreate,
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    query = Query(
        query_text=query_in.query_text,
        status=QueryStatus.PENDING,
        status_message="Query created, waiting to process",
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
    db: AsyncSession = Depends(get_db),
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
            select(func.count(EditSuggestion.id)).where(
                EditSuggestion.query_id == query.id
            )
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
    db: AsyncSession = Depends(get_db),
) -> QueryDetailResponse:
    
    query = await get_query_or_404(
        db,
        query_id,
        options=[
            selectinload(Query.suggestions)
            .selectinload(EditSuggestion.section)
            .selectinload(DocumentSection.document)
        ],
    )

    suggestion_responses = [
        SuggestionResponse(
            id=s.id,
            query_id=s.query_id,
            document_id=s.document_id,
            section_id=s.section_id,
            original_text=s.original_text,
            suggested_text=s.suggested_text,
            reasoning=s.reasoning,
            confidence=s.confidence,
            status=s.status,
            edited_text=s.edited_text,
            created_at=s.created_at,
            updated_at=s.updated_at,
            section_title=s.section.section_title if s.section else None,
            file_path=(
                s.section.document.file_path
                if s.section and s.section.document
                else None
            ),
        )
        for s in query.suggestions
    ]

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
        suggestions=suggestion_responses,
    )


@router.get("/{query_id}/suggestions", response_model=list[QuerySuggestionListItem])
async def get_query_suggestions(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
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
            created_at=s.created_at,
        )
        for s in suggestions
    ]


@router.post("/{query_id}/process/stream")
async def process_query_stream(
    query_id: UUID,
    use_celery: bool = QueryParam(
        default=False,
        description="Use Celery worker (subscribes to Redis events)",
    ),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    query = await get_query_or_404(db, query_id)

    if query.status not in (QueryStatus.PENDING, QueryStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Query already {query.status.value}",
        )

    if use_celery:
        return await _stream_from_celery(query_id, query.query_text)
    else:
        return await _stream_direct(query_id, query.query_text, db)


async def _stream_direct(
    query_id: UUID,
    query_text: str,
    db: AsyncSession,
) -> EventSourceResponse:
    publisher = DirectEventPublisher(query_id)
    emitter = EventEmitter(publisher, query_id)

    async def event_generator():
        import asyncio

        async def run_orchestrator():
            try:
                orchestrator = QueryOrchestrator(db, emitter)
                await orchestrator.process(query_id, query_text)
            finally:
                await emitter.close()

        task = asyncio.create_task(run_orchestrator())

        try:
            async for event in publisher.events():
                yield {
                    "event": event.event.value,
                    "data": json.dumps(event.data),
                }
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return EventSourceResponse(event_generator())


async def _stream_from_celery(
    query_id: UUID,
    query_text: str,
) -> EventSourceResponse:
    
    subscriber = RedisEventSubscriber(query_id)
    

    task = process_query_async.delay(str(query_id), query_text)
    logger.info(f"Started Celery task {task.id} for query {query_id}")

    async def event_generator():
        yield {
            "event": "task_started",
            "data": json.dumps({"task_id": task.id, "query_id": str(query_id)}),
        }

        try:
            async for event in subscriber.events():
                if event.event == EventType.HEARTBEAT:
                    yield {"event": "heartbeat", "data": "{}"}
                    continue

                yield {
                    "event": event.event.value,
                    "data": json.dumps(event.data, default=str),
                }
                
                if event.event in (EventType.COMPLETED, EventType.ERROR):
                    break
                    
        except Exception as e:
            logger.error(f"Error in event stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
        finally:
            await subscriber.close()

    return EventSourceResponse(event_generator())


@router.post("/{query_id}/process", response_model=QueryProcessResponse)
async def process_query_celery(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> QueryProcessResponse:
    query = await get_query_or_404(db, query_id)

    if query.status not in (QueryStatus.PENDING, QueryStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Query already {query.status.value}",
        )

    task = process_query_async.delay(str(query_id), query.query_text)
    logger.info(f"Started Celery task {task.id} for query {query_id}")

    return QueryProcessResponse(
        message="Processing started in background",
        query_id=query_id,
        task_id=task.id,
    )


@router.get("/{query_id}/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    query_id: UUID,
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskStatusResponse:

    await get_query_or_404(db, query_id)
    task_info = get_task_info(task_id)

    progress = None
    if task_info.get("progress"):
        progress = TaskProgressInfo(**task_info["progress"])

    return TaskStatusResponse(
        task_id=task_id,
        query_id=str(query_id),
        state=task_info["state"],
        status=task_info["status"],
        ready=task_info["ready"],
        successful=task_info.get("successful"),
        failed=task_info.get("failed"),
        result=task_info.get("result"),
        error=task_info.get("error"),
        progress=progress,
    )


@router.delete("/{query_id}", status_code=204)
async def delete_query(
    query_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    query = await get_query_or_404(db, query_id)
    await db.delete(query)
    await db.commit()