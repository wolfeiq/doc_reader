from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


    app_name: str = "Doc Updater"
    debug: bool = False
    environment: str = "development"


    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/doc_reader"


    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection_name: str = "documentation"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"


    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


    api_prefix: str = "/api"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()