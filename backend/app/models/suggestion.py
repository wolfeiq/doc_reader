import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Float, ForeignKey, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import DocumentSection
    from app.models.query import Query
    from app.models.history import EditHistory


class SuggestionStatus(str, Enum):

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited" 


class EditSuggestion(Base, TimestampMixin):

    __tablename__ = "edit_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    edited_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus),
        nullable=False,
        default=SuggestionStatus.PENDING,
        index=True,
    )

    query: Mapped["Query"] = relationship("Query", back_populates="suggestions")
    section: Mapped["DocumentSection"] = relationship(
        "DocumentSection", back_populates="suggestions"
    )
    history_entries: Mapped[list["EditHistory"]] = relationship(
        "EditHistory",
        back_populates="suggestion",
        cascade="all, delete-orphan",
    )