import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text, func
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


class Query(Base, TimestampMixin):

    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[QueryStatus] = mapped_column(
        SQLEnum(QueryStatus),
        nullable=False,
        default=QueryStatus.PENDING,
        index=True,
    )
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    suggestions: Mapped[list["EditSuggestion"]] = relationship(
        "EditSuggestion",
        back_populates="query",
        cascade="all, delete-orphan",
        lazy="selectin",
    )