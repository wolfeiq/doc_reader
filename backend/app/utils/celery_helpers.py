import asyncio
import logging
from typing import TypeVar, Coroutine, Any
from functools import wraps
from sqlalchemy.ext.asyncio import AsyncSession
from app.celery_app import celery_app
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


async def get_db_session() -> AsyncSession:
    return AsyncSessionLocal()


class DBSessionContext:

    def __init__(self):
        self.session: AsyncSession | None = None
    
    async def __aenter__(self) -> AsyncSession:
        self.session = AsyncSessionLocal()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
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


def with_db_session(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with DBSessionContext() as db:
            return await func(db, *args, **kwargs)
    return wrapper


def celery_task_wrapper(async_func):
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        return run_async(async_func(*args, **kwargs))
    return wrapper


async def update_task_progress(task: Any, current: int, total: int, message: str = ""):

    percent = int((current / total) * 100) if total > 0 else 0
    
    task.update_state(
        state="PROGRESS",
        meta={
            "current": current,
            "total": total,
            "percent": percent,
            "message": message,
        }
    )


def get_task_info(task_id: str) -> dict[str, Any]:
    
    task = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "state": task.state,
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