from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.suggestion import EditSuggestion


class QueryStatus(str, Enum):

    PENDING = "pending"
    PROCESSING = "processing"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (QueryStatus.COMPLETED, QueryStatus.FAILED)

    @property
    def is_active(self) -> bool:
        return self in (
            QueryStatus.PROCESSING,
            QueryStatus.SEARCHING,
            QueryStatus.ANALYZING,
            QueryStatus.GENERATING,
        )


class Query(Base, TimestampMixin):

    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[QueryStatus] = mapped_column(
        SQLEnum(QueryStatus, name="querystatus"),
        nullable=False,
        default=QueryStatus.PENDING,
        index=True,
    )
    status_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    suggestions: Mapped[list[EditSuggestion]] = relationship(
        back_populates="query",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def suggestion_count(self) -> int:
        return len(self.suggestions) if self.suggestions else 0

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at and self.created_at:
            return (self.completed_at - self.created_at).total_seconds()
        return None