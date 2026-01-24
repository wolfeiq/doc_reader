"""
Celery helper utilities for async task execution and progress tracking.
"""

from __future__ import annotations

import asyncio
import logging
from functools import wraps
from typing import Any, Coroutine, TypeVar

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """
    Run an async coroutine from a sync context (Celery task).
    
    Creates a new event loop if one doesn't exist.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)


async def get_db_session() -> AsyncSession:
    """Get a new database session."""
    return AsyncSessionLocal()


class DBSessionContext:
    """
    Async context manager for database sessions in Celery tasks.
    
    Handles session lifecycle with automatic commit/rollback.
    """

    def __init__(self) -> None:
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        self.session = AsyncSessionLocal()
        return self.session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self.session:
            if exc_type:
                await self.session.rollback()
            else:
                try:
                    await self.session.commit()
                except Exception:
                    await self.session.rollback()
                    raise
            await self.session.close()


def with_db_session(func: Any) -> Any:
    """Decorator that injects a database session as the first argument."""
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with DBSessionContext() as db:
            return await func(db, *args, **kwargs)
    return wrapper


def celery_task_wrapper(async_func: Any) -> Any:
    """Decorator to wrap an async function for use as a Celery task."""
    @wraps(async_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return run_async(async_func(*args, **kwargs))
    return wrapper


def update_task_progress(
    task: Task,
    current: int,
    total: int,
    message: str = "",
) -> None:
    """
    Update Celery task progress metadata.
    
    Args:
        task: The bound Celery task (self from @celery_app.task(bind=True))
        current: Current progress value
        total: Total expected value
        message: Optional progress message
    """
    percent = int((current / total) * 100) if total > 0 else 0

    task.update_state(
        state="PROGRESS",
        meta={
            "current": current,
            "total": total,
            "percent": percent,
            "message": message,
        },
    )


def get_task_info(task_id: str) -> dict[str, Any]:
    """
    Get information about a Celery task by ID.
    
    Returns a dict with state, result, and progress information.
    """
    task = celery_app.AsyncResult(task_id)

    response: dict[str, Any] = {
        "task_id": task_id,
        "state": task.state,
        "status": task.state,  # Alias for compatibility
        "ready": task.ready(),
        "successful": task.successful() if task.ready() else None,
        "failed": task.failed() if task.ready() else None,
    }

    if task.state == "PROGRESS":
        response["progress"] = task.info
    elif task.successful():
        response["result"] = task.result
    elif task.failed():
        response["error"] = str(task.info)

    return response


def revoke_task(task_id: str, terminate: bool = False) -> bool:
    """
    Revoke (cancel) a Celery task.
    
    Args:
        task_id: The task ID to revoke
        terminate: If True, forcefully terminate the task
        
    Returns:
        True if revocation was sent (doesn't guarantee task was stopped)
    """
    try:
        task = celery_app.AsyncResult(task_id)
        task.revoke(terminate=terminate)
        logger.info(f"Revoked task {task_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to revoke task {task_id}: {e}")
        return False