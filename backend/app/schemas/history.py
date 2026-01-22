from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.models.history import UserAction


class HistoryBase(BaseModel):
    old_content: str
    new_content: str
    user_action: UserAction


class HistoryCreate(HistoryBase):

    document_id: UUID
    section_id: Optional[UUID] = None
    suggestion_id: Optional[UUID] = None
    query_text: Optional[str] = None
    file_path: Optional[str] = None
    section_title: Optional[str] = None


class HistoryResponse(HistoryBase):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    section_id: Optional[UUID] = None
    suggestion_id: Optional[UUID] = None
    query_text: Optional[str] = None
    file_path: Optional[str] = None
    section_title: Optional[str] = None
    created_at: datetime


class HistoryListResponse(BaseModel):
    items: list[HistoryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class HistoryFilter(BaseModel):

    document_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    user_action: Optional[UserAction] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None