from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.query import QueryStatus
from app.schemas.suggestion import SuggestionResponse

class QueryCreate(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=5000)


class QueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    query_text: str
    status: QueryStatus
    status_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    suggestion_count: int = 0


class QueryDetailResponse(QueryResponse):
    suggestions: list["SuggestionResponse"] = Field(default_factory=list)


class QuerySuggestionListItem(BaseModel):

    id: UUID
    section_id: UUID
    section_title: Optional[str] = None
    original_text: str
    suggested_text: str
    reasoning: str
    confidence: float
    status: str
    created_at: datetime


class QueryProcessResponse(BaseModel):
    message: str
    query_id: UUID


class StreamEvent(BaseModel):
    event: str
    data: dict


class StatusUpdateEvent(BaseModel):
    status: QueryStatus
    message: str


class SearchProgressEvent(BaseModel):
    sections_found: int
    message: str


class SuggestionGeneratedEvent(BaseModel):
    suggestion_id: UUID
    section_title: Optional[str]
    file_path: str
    confidence: float
    preview: str 


class ErrorEvent(BaseModel):
    error: str
    details: Optional[str] = None


class CompletedEvent(BaseModel):
    total_suggestions: int
    query_id: UUID
