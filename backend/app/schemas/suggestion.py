from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.suggestion import SuggestionStatus


class SuggestionBase(BaseModel):
    original_text: str
    suggested_text: str
    reasoning: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class SuggestionCreate(SuggestionBase):
    query_id: UUID
    section_id: UUID


class SuggestionUpdate(BaseModel):
    status: Optional[SuggestionStatus] = None
    edited_text: Optional[str] = None


class SuggestionResponse(SuggestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query_id: UUID
    section_id: UUID
    status: SuggestionStatus
    edited_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    section_title: Optional[str] = None
    file_path: Optional[str] = None


class SuggestionWithContext(SuggestionResponse):
    full_section_content: str = ""
    affected_sections: list[dict] = Field(default_factory=list)


class SuggestionApplyRequest(BaseModel):
    use_edited_text: bool = False


class SuggestionActionResponse(BaseModel):
    success: bool
    suggestion_id: UUID
    section_id: Optional[UUID] = None
    message: str


class SuggestionApplyResponse(BaseModel):
    success: bool
    message: str
    history_id: Optional[UUID] = None
    new_document_content: Optional[str] = None


class BulkSuggestionUpdate(BaseModel):
    suggestion_ids: list[UUID]
    status: SuggestionStatus
