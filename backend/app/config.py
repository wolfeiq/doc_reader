from functools import lru_cache
from typing import Literal, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl, validator

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

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_server: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "pluno"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"

    redis_host: str = "localhost" 
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    
    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
 
    chroma_host: str = "localhost"
    chroma_port: int = 8002
    chroma_collection_name: str = "documentation"

    openai_api_key: str = Field(..., description="OpenAI API key") 
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"


    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


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