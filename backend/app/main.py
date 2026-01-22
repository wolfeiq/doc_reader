import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import documents, history, queries, suggestions
from app.config import settings
from app.db import close_db, init_db
from app.services.search_service import search_service


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(f"Starting {settings.app_name}...")

    await init_db()
    logger.info("Database initialized")

    await search_service.initialize()
    logger.info("Search service initialized")
    
    yield

    logger.info("Shutting down...")
    await search_service.close()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description="AI-powered documentation update assistant",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    documents.router,
    prefix=f"{settings.api_prefix}/documents",
    tags=["documents"],
)
app.include_router(
    queries.router,
    prefix=f"{settings.api_prefix}/queries",
    tags=["queries"],
)
app.include_router(
    suggestions.router,
    prefix=f"{settings.api_prefix}/suggestions",
    tags=["suggestions"],
)
app.include_router(
    history.router,
    prefix=f"{settings.api_prefix}/history",
    tags=["history"],
)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    search_stats = await search_service.get_collection_stats()
    return {
        "status": "healthy",
        "search_service": search_stats,
    }