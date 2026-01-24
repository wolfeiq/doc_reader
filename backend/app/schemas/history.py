from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserAction(str, Enum):

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"
    REVERTED = "reverted"


class HistoryBase(BaseModel):
 
    old_content: str
    new_content: str
    user_action: UserAction


class HistoryCreate(HistoryBase):

    document_id: UUID
    section_id: UUID | None = None
    suggestion_id: UUID | None = None
    query_text: str | None = None
    file_path: str | None = None
    section_title: str | None = None


class HistoryResponse(HistoryBase):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    section_id: UUID | None = None
    suggestion_id: UUID | None = None
    query_text: str | None = None
    file_path: str | None = None
    section_title: str | None = None
    created_at: datetime


class HistoryListResponse(BaseModel):

    items: list[HistoryResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_pages: int = Field(ge=0)


class HistoryFilter(BaseModel):

    document_id: UUID | None = None
    section_id: UUID | None = None
    user_action: UserAction | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class HistoryStatsResponse(BaseModel):

    by_action: dict[str, int] = Field(default_factory=dict)
    total: int = Field(ge=0)
    last_7_days: int = Field(ge=0)