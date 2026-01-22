from __future__ import annotations
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.history import EditHistory
    from app.models.suggestion import EditSuggestion


class Document(Base, TimestampMixin):

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)


    sections: Mapped[list[DocumentSection]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentSection.order",  # Always return sorted
    )
    history: Mapped[list[EditHistory]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentSection(Base, TimestampMixin):
    """A section within a document, identified by headers."""

    __tablename__ = "document_sections"
    __table_args__ = (
        Index("ix_section_document_order", "document_id", "order"),
    )

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
    section_title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(nullable=False, default=0)
    embedding_id: Mapped[str | None] = mapped_column(String(100))
    start_line: Mapped[int | None] = mapped_column()
    end_line: Mapped[int | None] = mapped_column()

    document: Mapped[Document] = relationship(back_populates="sections")
    suggestions: Mapped[list[EditSuggestion]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
    )
    source_dependencies: Mapped[list[SectionDependency]] = relationship(
        foreign_keys="SectionDependency.source_section_id",
        back_populates="source_section",
        cascade="all, delete-orphan",
    )
    target_dependencies: Mapped[list[SectionDependency]] = relationship(
        foreign_keys="SectionDependency.target_section_id",
        back_populates="target_section",
        cascade="all, delete-orphan",
    )


class SectionDependency(Base, TimestampMixin):

    __tablename__ = "section_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "source_section_id",
            "target_section_id",
            "dependency_type",
            name="uq_dependency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="reference",
    )

    source_section: Mapped[DocumentSection] = relationship(
        foreign_keys=[source_section_id],
        back_populates="source_dependencies",
    )
    target_section: Mapped[DocumentSection] = relationship(
        foreign_keys=[target_section_id],
        back_populates="target_dependencies",
    )