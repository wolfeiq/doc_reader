from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services import DocumentService, HistoryService, search_service


async def get_document_service(
    db: AsyncSession = None,
) -> AsyncGenerator[DocumentService, None]:
    async for session in get_db():
        yield DocumentService(session)


async def get_history_service(
    db: AsyncSession = None,
) -> AsyncGenerator[HistoryService, None]:
    async for session in get_db():
        yield HistoryService(session)


def get_search_service():
    return search_service
