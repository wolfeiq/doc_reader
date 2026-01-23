import logging
from uuid import UUID
from sqlalchemy import select
from celery import Task
from datetime import datetime, timedelta
from app.celery_app import celery_app
from app.models.query import Query, QueryStatus
from app.ai.orchestrator import process_query
from app.utils.celery_helpers import (
    run_async,
    DBSessionContext,
    update_task_progress,
)

logger = logging.getLogger(__name__)


class QueryProcessingTask(Task):

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Query processing task {task_id} failed: {exc}")
        query_id = args[0] if args else kwargs.get("query_id")
        if query_id:
            run_async(self._mark_query_failed(query_id, str(exc)))
    
    async def _mark_query_failed(self, query_id: str, error: str):
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
def process_query_async(self, query_id: str, query_text: str) -> dict:

    logger.info(f"Starting async processing for query {query_id}")
    
    async def _process():
        async with DBSessionContext() as db:
            result = await db.execute(
                select(Query).where(Query.id == UUID(query_id))
            )
            query = result.scalar_one_or_none()
            
            if not query:
                raise ValueError(f"Query {query_id} not found")
            
            query.status = QueryStatus.PROCESSING
            query.status_message = "Processing with Celery worker..."
            await db.commit()
    
            suggestions_count = 0
            searches_count = 0
            
            async for event in process_query(UUID(query_id), query_text, db):
                event_type = event.get("event")
                
                if event_type == "search_complete":
                    searches_count += 1
                    await update_task_progress(
                        self,
                        searches_count,
                        10,
                        f"Performed {searches_count} searches"
                    )
                
                elif event_type == "suggestion":
                    suggestions_count += 1
                    await update_task_progress(
                        self,
                        suggestions_count,
                        20,
                        f"Generated {suggestions_count} suggestions"
                    )
                
                elif event_type == "error":
                    error = event.get("data", {}).get("error", "Unknown error")
                    raise Exception(f"Query processing error: {error}")
            await db.refresh(query)
            
            return {
                "query_id": query_id,
                "status": query.status.value,
                "suggestions_created": suggestions_count,
                "searches_performed": searches_count,
                "message": query.status_message,
            }
    
    return run_async(_process())


@celery_app.task(name="app.tasks.query_tasks.cleanup_old_queries")
def cleanup_old_queries(days_old: int = 30) -> dict:
    
    logger.info(f"Cleaning up queries older than {days_old} days")
    
    async def _cleanup():
        async with DBSessionContext() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            result = await db.execute(
                select(Query).where(
                    Query.created_at < cutoff_date,
                    Query.status.in_([QueryStatus.COMPLETED, QueryStatus.FAILED])
                )
            )
            queries = result.scalars().all()
            
            count = len(queries)
            for query in queries:
                await db.delete(query)
            
            await db.commit()
            
            return {
                "deleted_count": count,
                "cutoff_date": cutoff_date.isoformat(),
            }
    
    return run_async(_cleanup())