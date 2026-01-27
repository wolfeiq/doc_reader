"""
FastAPI Dependencies
====================

Dependency injection functions for FastAPI routes.
These provide database sessions and service instances to route handlers.

FastAPI Dependency Injection:
-----------------------------
FastAPI's Depends() system provides clean separation of concerns:
- Routes don't create their own DB connections
- Services are instantiated with proper sessions
- Resources are automatically cleaned up

Usage in routes:
    @router.get("/documents")
    async def list_docs(
        service: DocumentService = Depends(get_document_service)
    ):
        return await service.list_documents()

Production Considerations:
--------------------------
- Add authentication dependency (get_current_user)
- Add rate limiting dependency
- Add request tracing/logging dependency
- Consider caching service instances per request
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services import DocumentService, HistoryService, search_service
from app.services.search_service import SearchService


async def get_document_service(
    db: AsyncSession = None,
) -> AsyncGenerator[DocumentService, None]:
    """
    Provide a DocumentService instance with a database session.

    The session lifecycle is managed by get_db() - commits on success,
    rolls back on exception.
    """
    async for session in get_db():
        yield DocumentService(session)


async def get_history_service(
    db: AsyncSession = None,
) -> AsyncGenerator[HistoryService, None]:
    """Provide a HistoryService for audit log operations."""
    async for session in get_db():
        yield HistoryService(session)


def get_search_service() -> SearchService:
    """
    Return the global SearchService instance.

    SearchService is a singleton because:
    - ChromaDB client is expensive to create
    - Connection pooling is handled internally
    - Embeddings cache is shared
    """
    return search_service
