"""Suggestion schemas for API request/response validation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.suggestion import SuggestionStatus


class SuggestionBase(BaseModel):
    """Base fields shared across suggestion schemas."""

    original_text: str
    suggested_text: str
    reasoning: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class SuggestionCreate(SuggestionBase):
    """Request schema for creating a suggestion."""

    query_id: UUID
    section_id: UUID


class SuggestionUpdate(BaseModel):
    """Request schema for updating a suggestion."""

    status: SuggestionStatus | None = None
    edited_text: str | None = None


class SuggestionResponse(SuggestionBase):
    """Response schema for suggestion endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query_id: UUID
    section_id: UUID
    status: SuggestionStatus
    edited_text: str | None = None
    created_at: datetime
    updated_at: datetime
    section_title: str | None = None
    file_path: str | None = None


class SuggestionWithContext(SuggestionResponse):
    """Extended response with additional section context."""

    full_section_content: str = ""
    affected_sections: list[dict[str, object]] = Field(default_factory=list)


class SuggestionApplyRequest(BaseModel):
    """Request schema for applying a suggestion."""

    use_edited_text: bool = False


class SuggestionActionResponse(BaseModel):
    """Response for accept/reject actions."""

    success: bool
    suggestion_id: UUID
    section_id: UUID | None = None
    message: str


class SuggestionApplyResponse(BaseModel):
    """Response after applying a suggestion."""

    success: bool
    message: str
    history_id: UUID | None = None
    new_document_content: str | None = None


class BulkSuggestionUpdate(BaseModel):
    """Request for bulk updating suggestion status."""

    suggestion_ids: list[UUID] = Field(..., min_length=1)
    status: SuggestionStatus