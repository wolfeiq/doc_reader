from __future__ import annotations
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.document import DocumentSection

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
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    source_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="CASCADE"),
    )
    target_section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_sections.id", ondelete="CASCADE"),
    )
    dependency_type: Mapped[str] = mapped_column(String(50), default="reference")

    source_section: Mapped[DocumentSection] = relationship(
        foreign_keys=[source_section_id],
        back_populates="source_dependencies",
    )
    target_section: Mapped[DocumentSection] = relationship(
        foreign_keys=[target_section_id],
        back_populates="target_dependencies",
    )
