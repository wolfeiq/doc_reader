import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import DocumentSection
    from app.models.document_base import Document
    from app.models.suggestion import EditSuggestion


class UserAction(str, Enum):

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"


class EditHistory(Base, TimestampMixin):

    __tablename__ = "edit_history"

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
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    suggestion_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("edit_suggestions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    old_content: Mapped[str] = mapped_column(Text, nullable=False)
    new_content: Mapped[str] = mapped_column(Text, nullable=False)
    user_action: Mapped[UserAction] = mapped_column(
        SQLEnum(UserAction),
        nullable=False,
        index=True,
    )
    

    query_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


    document: Mapped["Document"] = relationship("Document", back_populates="history")
    suggestion: Mapped[Optional["EditSuggestion"]] = relationship(
        "EditSuggestion", back_populates="history_entries"
    )