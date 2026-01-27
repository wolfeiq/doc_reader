"""
Application Configuration
=========================

Centralized configuration using Pydantic Settings for type-safe environment variables.
All config is loaded from environment variables or .env file.

Environment Setup:
------------------
For local development, create a .env file in /backend with:
    POSTGRES_SERVER=localhost
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=yourpassword
    POSTGRES_DB=pluno
    REDIS_HOST=localhost
    CHROMA_HOST=localhost
    OPENAI_API_KEY=sk-...

For Railway deployment:
    - Set variables in Railway dashboard under "Variables"
    - Use Railway's PostgreSQL/Redis plugins which auto-inject connection vars
    - POSTGRES_SERVER becomes the Railway internal hostname

Production Security:
--------------------
- Never commit .env files to git
- Use secret management (Railway Secrets, AWS Secrets Manager)
- Rotate API keys regularly
- Consider using different OpenAI keys per environment
"""

from functools import lru_cache
from typing import Literal, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl, validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic Settings provides:
    - Automatic type coercion (str -> int, etc.)
    - Validation with clear error messages
    - .env file support
    - Case-insensitive matching
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # POSTGRES_USER == postgres_user
        extra="ignore",  # Ignore unknown env vars without error
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    app_name: str = "Doc Updater"
    debug: bool = False  # Set DEBUG=true for verbose logging
    environment: Literal["development", "staging", "production"] = "development"

    # -------------------------------------------------------------------------
    # PostgreSQL Database Configuration
    # -------------------------------------------------------------------------
    # Railway provides these automatically when you add a PostgreSQL plugin
    # For local dev, these default to standard postgres settings
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_server: str = "localhost"  # Railway: use internal hostname
    postgres_port: int = 5432
    postgres_db: str = "pluno"

    @property
    def database_url(self) -> str:
        """
        Construct async PostgreSQL connection URL.
        Uses asyncpg driver for async SQLAlchemy support.

        Production Note: Railway provides DATABASE_URL directly.
        You could override this property to use that instead.
        """
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"

    # -------------------------------------------------------------------------
    # Redis Configuration
    # -------------------------------------------------------------------------
    # Used for: Celery broker, result backend, and SSE event streaming
    # Railway provides a Redis plugin that auto-injects REDIS_URL
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None  # Set for production Redis

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL with optional authentication."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # -------------------------------------------------------------------------
    # ChromaDB Vector Store Configuration
    # -------------------------------------------------------------------------
    # ChromaDB stores document embeddings for semantic search
    # Production: Consider using Pinecone, Weaviate, or Qdrant for managed service
    chroma_host: str = "localhost"
    chroma_port: int = 8002
    chroma_collection_name: str = "documentation"

    # -------------------------------------------------------------------------
    # OpenAI API Configuration
    # -------------------------------------------------------------------------
    # Required for: AI suggestions, semantic search embeddings
    # Cost Consideration: gpt-4o is powerful but expensive
    # Production: Monitor usage, implement token budgets, consider gpt-4o-mini
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = "gpt-4o"  # Main model for analysis/suggestions
    openai_embedding_model: str = "text-embedding-3-small"  # Fast, cheap embeddings

    # -------------------------------------------------------------------------
    # API Configuration
    # -------------------------------------------------------------------------
    api_prefix: str = "/api"  # All routes prefixed with /api

    # CORS origins - frontend URLs allowed to make requests
    # Production: Set to your Vercel deployment URL
    # Example: CORS_ORIGINS=https://myapp.vercel.app,https://www.myapp.com
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """
        Parse CORS origins from comma-separated string or list.
        Allows setting CORS_ORIGINS="http://a.com,http://b.com" in env.
        """
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        elif isinstance(v, list):
            return v
        raise ValueError(v)

    # -------------------------------------------------------------------------
    # Celery Task Queue Configuration
    # -------------------------------------------------------------------------
    # Celery handles background processing (query analysis, embeddings)
    # Defaults to using Redis for both broker and results
    celery_broker_url: str | None = None  # Override for separate broker
    celery_result_backend: str | None = None  # Override for separate backend

    @property
    def celery_broker(self) -> str:
        """Message broker URL - where tasks are queued."""
        return self.celery_broker_url or self.redis_url

    @property
    def celery_backend(self) -> str:
        """Result backend URL - where task results are stored."""
        return self.celery_result_backend or self.redis_url

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    This is important because loading from .env has I/O overhead.
    """
    return Settings()


# Global settings instance - import this throughout the app
# Usage: from app.config import settings
settings = get_settings()