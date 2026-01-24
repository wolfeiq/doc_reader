"""Query schemas for API request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.query import QueryStatus

if TYPE_CHECKING:
    from app.schemas.suggestion import SuggestionResponse


class QueryCreate(BaseModel):
    """Request schema for creating a new query."""

    query_text: str = Field(..., min_length=1, max_length=5000)


class QueryResponse(BaseModel):
    """Response schema for query list/detail endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query_text: str
    status: QueryStatus
    status_message: str | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    suggestion_count: int = 0


class QueryDetailResponse(QueryResponse):
    """Extended response with embedded suggestions."""

    suggestions: list[SuggestionResponse] = Field(default_factory=list)


class QuerySuggestionListItem(BaseModel):
    """Lightweight suggestion item for query suggestion lists."""

    id: UUID
    section_id: UUID
    section_title: str | None = None
    original_text: str
    suggested_text: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: str
    created_at: datetime


class QueryProcessResponse(BaseModel):
    """Response when starting async query processing."""

    message: str
    query_id: UUID
    task_id: str | None = None


class StreamEvent(BaseModel):
    """Generic SSE event wrapper."""

    event: str
    data: dict[str, object]


class StatusUpdateEvent(BaseModel):
    """Event for query status changes."""

    status: QueryStatus
    message: str


class SearchProgressEvent(BaseModel):
    """Event for search progress updates."""

    sections_found: int
    message: str


class SuggestionGeneratedEvent(BaseModel):
    """Event when a suggestion is created."""

    suggestion_id: UUID
    section_title: str | None = None
    file_path: str
    confidence: float = Field(ge=0.0, le=1.0)
    preview: str


class ErrorEvent(BaseModel):
    """Event for processing errors."""

    error: str
    details: str | None = None


class CompletedEvent(BaseModel):
    """Event when processing completes."""

    total_suggestions: int
    query_id: UUID


# Rebuild models that use forward references
def _rebuild_forward_refs() -> None:

    from app.schemas.suggestion import SuggestionResponse

    QueryDetailResponse.model_rebuild()


_rebuild_forward_refs()