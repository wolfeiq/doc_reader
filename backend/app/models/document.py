import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.suggestion import EditSuggestion
    from app.models.history import EditHistory


class Document(Base, TimestampMixin):

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    file_path: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False) 


    sections: Mapped[list["DocumentSection"]] = relationship(
        "DocumentSection",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    history: Mapped[list["EditHistory"]] = relationship(
        "EditHistory",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class DocumentSection(Base, TimestampMixin):

    __tablename__ = "document_sections"

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
    section_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(nullable=False, default=0)
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  
    start_line: Mapped[Optional[int]] = mapped_column(nullable=True)
    end_line: Mapped[Optional[int]] = mapped_column(nullable=True)


    document: Mapped["Document"] = relationship("Document", back_populates="sections")
    suggestions: Mapped[list["EditSuggestion"]] = relationship(
        "EditSuggestion",
        back_populates="section",
        cascade="all, delete-orphan",
    )
    
    source_dependencies: Mapped[list["SectionDependency"]] = relationship(
        "SectionDependency",
        foreign_keys="SectionDependency.source_section_id",
        back_populates="source_section",
        cascade="all, delete-orphan",
    )
    target_dependencies: Mapped[list["SectionDependency"]] = relationship(
        "SectionDependency",
        foreign_keys="SectionDependency.target_section_id",
        back_populates="target_section",
        cascade="all, delete-orphan",
    )


class SectionDependency(Base, TimestampMixin):

    __tablename__ = "section_dependencies"

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
        String(50), nullable=False, default="reference"
    )  

    source_section: Mapped["DocumentSection"] = relationship(
        "DocumentSection",
        foreign_keys=[source_section_id],
        back_populates="source_dependencies",
    )
    target_section: Mapped["DocumentSection"] = relationship(
        "DocumentSection",
        foreign_keys=[target_section_id],
        back_populates="target_dependencies",
    )