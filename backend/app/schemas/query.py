from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.query import QueryStatus

if TYPE_CHECKING:
    from app.schemas.suggestion import SuggestionResponse


class QueryCreate(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=5000)


class QueryResponse(BaseModel):
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
    suggestions: list[SuggestionResponse] = Field(default_factory=list)


class QuerySuggestionListItem(BaseModel):
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
    message: str
    query_id: UUID
    task_id: str | None = None


class StreamEvent(BaseModel):
    event: str
    data: dict[str, object]


class StatusUpdateEvent(BaseModel):
    status: QueryStatus
    message: str


class SearchProgressEvent(BaseModel):
    sections_found: int
    message: str


class SuggestionGeneratedEvent(BaseModel):
    suggestion_id: UUID
    section_title: str | None = None
    file_path: str
    confidence: float = Field(ge=0.0, le=1.0)
    preview: str


class ErrorEvent(BaseModel):
    error: str
    details: str | None = None


class CompletedEvent(BaseModel):
    total_suggestions: int
    query_id: UUID


# Rebuild models that use forward references
def _rebuild_forward_refs() -> None:

    from app.schemas.suggestion import SuggestionResponse

    QueryDetailResponse.model_rebuild()


_rebuild_forward_refs()