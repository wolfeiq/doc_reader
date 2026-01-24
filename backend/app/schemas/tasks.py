"""
Schemas for Celery task responses and status.

This module provides two types of schemas:
1. Pydantic models for API response validation
2. TypedDict for Celery task return type hints (static type checking)
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from pydantic import BaseModel, Field


# =============================================================================
# Pydantic Models (for API responses)
# =============================================================================


class TaskProgressInfo(BaseModel):
    """Progress information for a running task."""

    current: int = Field(ge=0)
    total: int = Field(ge=0)
    percent: float = Field(ge=0.0, le=100.0)
    message: str = ""


class TaskStatusResponse(BaseModel):
    """Response for task status endpoint."""

    task_id: str
    query_id: str | None = None
    state: str
    status: str  # Alias for state
    ready: bool = False
    successful: bool | None = None
    failed: bool | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: TaskProgressInfo | None = None


# =============================================================================
# TypedDict (for Celery task return types - static type checking)
# =============================================================================


# --- Query Tasks ---


class QueryProcessResultDict(TypedDict):
    """Return type for process_query_async task."""

    query_id: str
    status: str
    searches_performed: int
    sections_analyzed: int
    suggestions_created: int
    error: NotRequired[str | None]


class CleanupResultDict(TypedDict):
    """Return type for cleanup_old_queries task."""

    deleted_count: int
    cutoff_date: str


# --- Document Tasks ---


class EmbeddingErrorDict(TypedDict):
    """Error info for failed embedding generation."""

    section_id: str
    error: str


class GenerateEmbeddingsResultDict(TypedDict):
    """Return type for generate_embeddings task."""

    document_id: str
    total_sections: int
    embeddings_created: int
    errors: list[EmbeddingErrorDict]


class ReindexResultDict(TypedDict):
    """Return type for reindex_document task."""

    document_id: str
    file_path: str
    sections_indexed: int


class BulkEmbedItemResultDict(TypedDict):
    """Result for a single document in bulk embed."""

    document_id: str
    success: bool
    result: NotRequired[GenerateEmbeddingsResultDict]
    error: NotRequired[str]


class BulkEmbedResultDict(TypedDict):
    """Return type for bulk_embed_documents task."""

    total_documents: int
    successful: int
    failed: int
    results: list[BulkEmbedItemResultDict]


class DeleteEmbeddingsResultDict(TypedDict):
    """Return type for delete_document_embeddings task."""

    document_id: str
    sections_deleted: int


# --- Sync Tasks ---


class RebuildDependenciesResultDict(TypedDict):
    """Return type for rebuild_all_dependencies task."""

    success: bool
    total_dependencies: int


class SyncErrorDict(TypedDict):
    """Error info for sync failures."""

    document_id: str
    section_id: NotRequired[str]
    error: str


class SyncChromaDBResultDict(TypedDict):
    """Return type for sync_chromadb task."""

    success: bool
    documents_processed: int
    total_sections: int
    sections_synced: int
    errors: list[SyncErrorDict]


class VerifyIntegrityResultDict(TypedDict):
    """Return type for verify_chromadb_integrity task."""

    total_sections_in_db: int
    total_embeddings_in_chromadb: int
    sections_missing_embeddings: int
    missing_embedding_ids: list[str]
    chromadb_initialized: bool


class CleanupOrphanedResultDict(TypedDict):
    """Return type for cleanup_orphaned_embeddings task."""

    valid_sections: int
    chromadb_count: int
    message: str


class ServiceHealthDict(TypedDict):
    """Individual service health status."""

    database: bool
    chromadb: bool
    redis: bool


class HealthCheckResultDict(TypedDict):
    """Return type for health_check task."""

    healthy: bool
    services: ServiceHealthDict