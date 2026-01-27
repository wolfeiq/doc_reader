"""
Document Model
==============

Represents a documentation file in the system. Documents are typically
Markdown files that contain technical documentation, guides, or references.

Document Ingestion:
-------------------
Documents are loaded from the filesystem and stored in the database.
The content is parsed to extract sections (based on Markdown headings),
and each section gets a vector embedding in ChromaDB.

Checksum for Change Detection:
------------------------------
The checksum field stores a SHA-256 hash of the file content.
This enables efficient change detection during re-indexing:
- If checksum matches, skip re-processing (no changes)
- If checksum differs, re-parse sections and update embeddings

File Path as Unique Identifier:
-------------------------------
The file_path is unique and indexed, serving as a natural key.
This allows referencing documents by path in APIs and AI prompts.

Production Considerations:
--------------------------
- Add file size limits to prevent memory issues
- Consider blob storage (S3) for very large documents
- Add last_synced_at to track freshness
- Implement incremental updates (only changed sections)
- Add document categories/tags for organization
"""

from __future__ import annotations
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import DocumentSection
    from app.models.history import EditHistory


class Document(Base, TimestampMixin):
    """
    A documentation file stored in the system.

    Attributes:
        file_path: Unique path identifier (e.g., "docs/api/auth.md")
        title: Document title (from first H1 or filename)
        content: Full raw content of the document
        checksum: SHA-256 hash for change detection

    Relationships:
        sections: Parsed sections of this document (cascade delete)
        history: Edit history entries for this document
    """
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_path: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    sections: Mapped[list[DocumentSection]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentSection.order",
    )

    history: Mapped[list[EditHistory]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
