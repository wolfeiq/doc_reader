from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool
from app.config import settings
from app.db.base import Base

pool_config = (
    {"poolclass": AsyncAdaptedQueuePool, "pool_size": 5, "max_overflow": 10}
    if settings.is_production
    else {"pool_size": 2, "max_overflow": 5}
)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,  
    connect_args={"command_timeout": 60},
    **pool_config,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

AsyncSessionLocal = async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()