"""
Database Session Management
===========================

This module configures SQLAlchemy async engine and session factory for PostgreSQL.
Uses asyncpg driver for non-blocking database operations.

Connection Pattern:
-------------------
We use the "session-per-request" pattern where each HTTP request gets its own
database session via FastAPI's dependency injection (get_db).

The session auto-commits on success and rolls back on exception, ensuring
data consistency without manual commit calls in route handlers.

Production Considerations:
--------------------------
- Pool size is tuned based on environment (2 dev, 5 prod)
- pool_pre_ping catches stale connections (important for serverless)
- pool_recycle prevents connection timeout issues
- command_timeout prevents stuck queries

For Railway/Serverless:
-----------------------
- Consider using PgBouncer for connection pooling at scale
- Railway's PostgreSQL has connection limits - monitor with pg_stat_activity
- For high-traffic, consider read replicas
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.config import settings
from app.db.base import Base

# =============================================================================
# Connection Pool Configuration
# =============================================================================
# Production uses larger pool to handle more concurrent requests
# Development uses smaller pool to save resources

pool_config = (
    {"poolclass": AsyncAdaptedQueuePool, "pool_size": 5, "max_overflow": 10}
    if settings.is_production
    else {"pool_size": 2, "max_overflow": 5}
)

# =============================================================================
# SQLAlchemy Async Engine
# =============================================================================
# The engine manages the connection pool and dialect

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL queries in debug mode
    future=True,  # Use SQLAlchemy 2.0 style
    pool_pre_ping=True,  # Test connections before using (catches stale)
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={"command_timeout": 60},  # 60s query timeout
    **pool_config,
)

# =============================================================================
# Session Factory
# =============================================================================
# Creates new session instances with consistent configuration

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit (avoid lazy loads)
    autocommit=False,  # Explicit transaction control
    autoflush=False,  # Don't auto-flush (explicit flush/commit)
)

# Alias for backwards compatibility
AsyncSessionLocal = async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.

    Usage in routes:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...

    Transaction Behavior:
    - Session is created at request start
    - Auto-commits on successful request completion
    - Auto-rollbacks on any exception
    - Session is closed after request

    Why auto-commit at the end?
    ---------------------------
    This pattern (Unit of Work) ensures that either ALL changes in a request
    succeed together, or NONE of them persist. Routes use db.flush() for
    intermediate operations (getting IDs) and rely on this final commit.

    Production Note:
    ----------------
    For read-only endpoints, you could use a separate read-only session
    with autocommit=True for better performance. Consider adding:
        async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()  # Commit all changes at end of request
        except Exception:
            await session.rollback()  # Rollback on any error
            raise


async def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in SQLAlchemy models if they don't exist.
    Called on application startup.

    Production Note:
    ----------------
    For production, use Alembic migrations instead:
    - Tracks schema changes over time
    - Supports rollbacks
    - Handles data migrations
    - Team-friendly version control

    Example Alembic setup:
        alembic init migrations
        alembic revision --autogenerate -m "Add users table"
        alembic upgrade head
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close all database connections.

    Called on application shutdown to cleanly dispose of connection pool.
    Ensures no connections are left hanging.
    """
    await engine.dispose()