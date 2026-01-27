"""
Doc Reader Backend - FastAPI Application Entry Point
=====================================================

This is the main FastAPI application for the AI-powered documentation update assistant.
The app helps users maintain documentation by analyzing queries and suggesting edits
to existing documentation sections.

Architecture Overview:
----------------------
- FastAPI for async REST API with automatic OpenAPI documentation
- PostgreSQL (via asyncpg) for persistent storage of documents, queries, suggestions
- Redis for Celery task queue and real-time event streaming (SSE)
- ChromaDB for vector embeddings and semantic search
- OpenAI GPT-4 for AI-powered analysis and suggestions

Deployment Notes (Vercel/Railway):
----------------------------------
- Railway: Deploy this backend as a Docker container or directly from the repo
- The app uses asynccontextmanager for proper startup/shutdown lifecycle
- Environment variables should be set in Railway's dashboard
- For production, set ENVIRONMENT=production to enable optimized pool settings

Production Considerations:
--------------------------
- Add rate limiting middleware (slowapi) to prevent API abuse
- Implement proper authentication (JWT/OAuth2) - currently open
- Add request ID middleware for distributed tracing
- Consider adding Sentry or similar for error monitoring
- Add prometheus metrics endpoint for observability
- Implement API versioning for backwards compatibility
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import admin, documents, history, queries, suggestions
from app.config import settings
from app.db import close_db, init_db
from app.services.search_service import search_service


# Configure logging - uses DEBUG in development for detailed traces
# Production should use INFO or WARNING to reduce noise
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown.

    Startup sequence:
    1. Initialize database tables (creates if not exist)
    2. Connect to ChromaDB vector store

    Shutdown sequence:
    1. Close ChromaDB connection
    2. Dispose database connection pool

    Production Note:
    ----------------
    In a fully-fledged production app, you would also:
    - Run database migrations (Alembic) instead of create_all
    - Warm up connection pools
    - Pre-load ML models or embeddings cache
    - Register with service discovery (Consul/etcd)
    - Initialize distributed tracing (Jaeger/Zipkin)
    """
    logger.info(f"Starting {settings.app_name}...")

    # Initialize database - creates tables if they don't exist
    # Production: Use Alembic migrations instead for schema versioning
    await init_db()
    logger.info("Database initialized")

    # Connect to ChromaDB for vector similarity search
    # This is lazy-initialized but we call it here to fail fast on startup
    await search_service.initialize()
    logger.info("Search service initialized")

    yield  # Application runs here

    # Graceful shutdown - close connections cleanly
    logger.info("Shutting down...")
    await search_service.close()
    await close_db()
    logger.info("Shutdown complete")


# FastAPI application instance
# The lifespan parameter replaces the deprecated @app.on_event decorators
app = FastAPI(
    title=settings.app_name,
    description="AI-powered documentation update assistant",
    version="0.1.0",
    lifespan=lifespan,
    # Production: Add these for better API documentation
    # docs_url="/api/docs" if not settings.is_production else None,
    # redoc_url="/api/redoc" if not settings.is_production else None,
)


# CORS Middleware - allows frontend to make cross-origin requests
# Production Security Note:
# - Currently allows all methods/headers which is permissive
# - For production, restrict to specific origins (your Vercel domain)
# - Consider adding: allow_origin_regex for wildcard subdomains
# - Add expose_headers for custom headers the frontend needs to read
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Set via CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["*"],  # Production: restrict to ["GET", "POST", "PATCH", "DELETE"]
    allow_headers=["*"],  # Production: restrict to needed headers
)


# =============================================================================
# API Routes
# =============================================================================
# Routes are organized by domain entity. Each router handles CRUD + custom actions.
# Prefix: /api/v1/... (configurable via API_PREFIX env var)
#
# Production Note: Consider versioning your API (v1, v2) for backwards compatibility
# when making breaking changes. You can mount multiple versions simultaneously.

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
app.include_router(
    admin.router,
    prefix=f"{settings.api_prefix}",
    tags=["admin"],
)


# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get("/")
async def root():
    """
    Root endpoint - basic API information.
    Useful for quick "is it running?" checks.
    """
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """
    Health check endpoint for load balancers and container orchestrators.

    Railway/Vercel will use this to determine if the service is healthy.
    Returns ChromaDB stats to verify vector store connectivity.

    Production Improvements:
    ------------------------
    - Check database connectivity (SELECT 1)
    - Check Redis connectivity (PING)
    - Return degraded status if non-critical services are down
    - Add response time metrics
    - Implement readiness vs liveness probes separately
    """
    search_stats = search_service.get_collection_stats()
    return {
        "status": "healthy",
        "search_service": search_stats,
        # Production: Add more health indicators
        # "database": "connected",
        # "redis": "connected",
        # "uptime_seconds": get_uptime(),
    }