from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",     
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Doc Updater"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"
    

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/pluno",
        description="PostgreSQL connection string",
    )

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_db: int = Field(default=0, ge=0, le=15)
    redis_password: str | None = None
    
    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8002, ge=1, le=65535)
    chroma_collection_name: str = "documentation"

    openai_api_key: str = Field(..., env="OPENAI_API_KEY", description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    api_prefix: str = "/api"

    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    
    @property
    def celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url
    
    @property
    def celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()