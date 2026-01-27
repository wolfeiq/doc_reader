"""
Document Section Model
======================

Represents a section within a document. Documents are split into sections
for granular AI analysis and suggestion generation.

Why Split Documents into Sections?
----------------------------------
1. Token Efficiency: AI models have context limits; sections fit better
2. Targeted Suggestions: Edits apply to specific sections, not whole docs
3. Semantic Search: Sections are individually embedded in ChromaDB
4. Dependency Tracking: Sections can reference other sections

Section Identification:
-----------------------
Sections are identified by headers (# Heading) in Markdown documents.
Each section gets its own embedding for semantic similarity search.

Production Considerations:
--------------------------
- Consider adding full-text search index for content column
- Add soft delete (deleted_at) for audit trail
- Consider content versioning for rollback capability
- Large documents may need section size limits
"""

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
    """
    A section of a document (typically a heading + its content).

    Attributes:
        document_id: Parent document reference
        section_title: Section heading (e.g., "## Installation")
        content: Full text content of the section
        order: Position within document (0-indexed)
        embedding_id: ChromaDB vector ID for semantic search
        start_line/end_line: Source file line numbers (for diffs)

    Relationships:
        document: Parent Document
        suggestions: AI-generated edit suggestions for this section
        source_dependencies: Sections this one depends on
        target_dependencies: Sections that depend on this one
    """
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
