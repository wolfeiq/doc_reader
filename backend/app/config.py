from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/doc_reader",
        description="PostgreSQL connection string",
    )


    chroma_host: str = "localhost"
    chroma_port: int = Field(default=8000, ge=1, le=65535)
    chroma_collection_name: str = "documentation"

    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    api_prefix: str = "/api"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()