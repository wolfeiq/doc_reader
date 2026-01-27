"""
Query Processing Celery Tasks
=============================

This module contains Celery tasks for asynchronous query processing.
These tasks run in Celery workers, separate from the FastAPI web server.

Why Background Processing?
--------------------------
AI query processing can take 30-60+ seconds due to:
- Multiple OpenAI API calls (embeddings, chat completions)
- Vector similarity searches
- Database operations

Running this synchronously would:
- Block the HTTP request (poor UX)
- Risk timeout errors
- Prevent horizontal scaling

How It Works:
-------------
1. API endpoint receives query, creates DB record, returns immediately
2. API dispatches Celery task with query ID
3. Celery worker picks up task and processes
4. Worker publishes progress events to Redis
5. Frontend subscribes to Redis events via SSE
6. Worker saves results and marks query complete

Error Handling:
---------------
The QueryProcessingTask base class handles failures:
- Logs errors with context
- Marks query as FAILED in database
- Supports automatic retries (3 attempts)

Production Considerations:
--------------------------
- Monitor task queue depth with Flower
- Set up dead letter queue for permanent failures
- Implement circuit breakers for OpenAI API
- Add task prioritization (premium users first)
- Consider task chaining for complex workflows
- Add Prometheus metrics for task duration/success rate
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from billiard.einfo import ExceptionInfo

from celery import Task
from sqlalchemy import select

from app.celery_app import celery_app
from app.models.query import Query, QueryStatus
from app.ai.orchestrator import QueryOrchestrator
from app.services.event_service import RedisEventPublisher, EventEmitter
from app.schemas.tasks import QueryProcessResultDict, CleanupResultDict
from app.utils.celery_helpers import run_async, DBSessionContext

logger = logging.getLogger(__name__)


class QueryProcessingTask(Task):
    """
    Custom Celery Task base class with failure handling.

    Extends Celery's Task to automatically mark queries as FAILED
    in the database when task execution fails. This ensures the
    frontend always knows the query's true status.
    """
    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[str, ...],
        kwargs: dict[str, Any],
        einfo: ExceptionInfo,
    ) -> None:
        logger.error(f"Query processing task {task_id} failed: {exc}")
        query_id = args[0] if args else kwargs.get("query_id")
        if query_id:
            run_async(self._mark_query_failed(query_id, str(exc)))

    async def _mark_query_failed(self, query_id: str, error: str) -> None:
        async with DBSessionContext() as db:
            result = await db.execute(
                select(Query).where(Query.id == UUID(query_id))
            )
            query = result.scalar_one_or_none()
            if query:
                query.status = QueryStatus.FAILED
                query.error_message = error
                await db.commit()


@celery_app.task(
    bind=True,
    base=QueryProcessingTask,
    name="app.tasks.query_tasks.process_query_async",
    max_retries=3,
    default_retry_delay=60,
)
def process_query_async(
    self: Task,
    query_id: str,
    query_text: str,
) -> QueryProcessResultDict:
    logger.info(f"Starting Celery processing for query {query_id}")

    async def _process() -> QueryProcessResultDict:
        publisher = RedisEventPublisher(query_id)
        emitter = EventEmitter(publisher, query_id)

        try:
            async with DBSessionContext() as db:
                orchestrator = QueryOrchestrator(db, emitter)
                result = await orchestrator.process(UUID(query_id), query_text)

                return QueryProcessResultDict(
                    query_id=result.get("query_id", query_id),
                    status=result.get("status", "unknown"),
                    searches_performed=result.get("searches_performed", 0),
                    sections_analyzed=result.get("sections_analyzed", 0),
                    suggestions_created=result.get("suggestions_created", 0),
                    error=result.get("error"),
                )
        finally:
            await emitter.close()

    return run_async(_process())


@celery_app.task(name="app.tasks.query_tasks.cleanup_old_queries")
def cleanup_old_queries(days_old: int = 30) -> CleanupResultDict:
    logger.info(f"Cleaning up queries older than {days_old} days")

    async def _cleanup() -> CleanupResultDict:
        async with DBSessionContext() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            result = await db.execute(
                select(Query).where(
                    Query.created_at < cutoff_date,
                    Query.status.in_([QueryStatus.COMPLETED, QueryStatus.FAILED]),
                )
            )
            queries = result.scalars().all()

            count = len(queries)
            for query in queries:
                await db.delete(query)

            await db.commit()

            return CleanupResultDict(
                deleted_count=count,
                cutoff_date=cutoff_date.isoformat(),
            )

    return run_async(_cleanup())