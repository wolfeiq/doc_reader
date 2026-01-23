from __future__ import annotations
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document_base import Document 
    from app.models.suggestion import EditSuggestion
    from app.models.section_dependency import SectionDependency


class DocumentSection(Base, TimestampMixin):
    __tablename__ = "document_sections"
    __table_args__ = (
        Index("ix_section_document_order", "document_id", "order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )

    section_title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(default=0)
    embedding_id: Mapped[str | None] = mapped_column(String(100))  # ADD THIS
    start_line: Mapped[int | None] = mapped_column()  # ADD THIS
    end_line: Mapped[int | None] = mapped_column()
    document: Mapped[Document] = relationship(back_populates="sections")

    suggestions: Mapped[list[EditSuggestion]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )

    source_dependencies: Mapped[list[SectionDependency]] = relationship(
        foreign_keys="SectionDependency.source_section_id",
        back_populates="source_section",
    )
    target_dependencies: Mapped[list[SectionDependency]] = relationship(
        foreign_keys="SectionDependency.target_section_id",
        back_populates="target_section",
    )
