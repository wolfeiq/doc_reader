from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from pydantic import BaseModel, Field

class TaskProgressInfo(BaseModel):
    current: int = Field(ge=0)
    total: int = Field(ge=0)
    percent: float = Field(ge=0.0, le=100.0)
    message: str = ""


class TaskStatusResponse(BaseModel):
    task_id: str
    query_id: str | None = None
    state: str
    status: str 
    ready: bool = False
    successful: bool | None = None
    failed: bool | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: TaskProgressInfo | None = None


class QueryProcessResultDict(TypedDict):
    query_id: str
    status: str
    searches_performed: int
    sections_analyzed: int
    suggestions_created: int
    error: NotRequired[str | None]


class CleanupResultDict(TypedDict):
    deleted_count: int
    cutoff_date: str


class EmbeddingErrorDict(TypedDict):
    section_id: str
    error: str


class GenerateEmbeddingsResultDict(TypedDict):
    document_id: str
    total_sections: int
    embeddings_created: int
    errors: list[EmbeddingErrorDict]


class ReindexResultDict(TypedDict):
    document_id: str
    file_path: str
    sections_indexed: int


class BulkEmbedItemResultDict(TypedDict):
    document_id: str
    success: bool
    result: NotRequired[GenerateEmbeddingsResultDict]
    error: NotRequired[str]


class BulkEmbedResultDict(TypedDict):
    total_documents: int
    successful: int
    failed: int
    results: list[BulkEmbedItemResultDict]


class DeleteEmbeddingsResultDict(TypedDict):
    document_id: str
    sections_deleted: int

class RebuildDependenciesResultDict(TypedDict):
    success: bool
    total_dependencies: int


class SyncErrorDict(TypedDict):
    document_id: str
    section_id: NotRequired[str]
    error: str


class SyncChromaDBResultDict(TypedDict):
    success: bool
    documents_processed: int
    total_sections: int
    sections_synced: int
    errors: list[SyncErrorDict]


class VerifyIntegrityResultDict(TypedDict):
    total_sections_in_db: int
    total_embeddings_in_chromadb: int
    sections_missing_embeddings: int
    missing_embedding_ids: list[str]
    chromadb_initialized: bool


class CleanupOrphanedResultDict(TypedDict):
    valid_sections: int
    chromadb_count: int
    message: str


class ServiceHealthDict(TypedDict):
    database: bool
    chromadb: bool
    redis: bool


class HealthCheckResultDict(TypedDict):
    healthy: bool
    services: ServiceHealthDict