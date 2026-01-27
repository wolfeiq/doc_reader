"""
Query Model - User Documentation Update Requests
=================================================

A Query represents a user's request to update documentation.
Example: "Update the API docs to reflect the new authentication flow"

Query Lifecycle:
----------------
1. PENDING    - Query created, waiting to be processed
2. PROCESSING - Celery worker picked up the task
3. SEARCHING  - Finding relevant document sections via vector search
4. ANALYZING  - AI analyzing sections for needed updates
5. GENERATING - Creating specific edit suggestions
6. COMPLETED  - All suggestions generated successfully
7. FAILED     - Error occurred during processing

Real-time Updates:
------------------
Query status changes are streamed to the frontend via Server-Sent Events (SSE).
The frontend can show a progress indicator as the query moves through stages.

Production Considerations:
--------------------------
- Add user_id foreign key for multi-tenant support
- Consider query prioritization (priority column)
- Add cost tracking (tokens_used, estimated_cost)
- Implement query deduplication (hash of query_text)
"""

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
    """
    Query processing status enum.

    Stored as PostgreSQL ENUM type for type safety and storage efficiency.
    The status progression forms a state machine for query processing.
    """

    PENDING = "pending"        # Awaiting processing
    PROCESSING = "processing"  # Worker started
    SEARCHING = "searching"    # Vector similarity search
    ANALYZING = "analyzing"    # AI reading sections
    GENERATING = "generating"  # Creating suggestions
    COMPLETED = "completed"    # Success - suggestions ready
    FAILED = "failed"          # Error occurred

    @property
    def is_terminal(self) -> bool:
        """Check if query has finished (success or failure)."""
        return self in (QueryStatus.COMPLETED, QueryStatus.FAILED)

    @property
    def is_active(self) -> bool:
        """Check if query is currently being processed."""
        return self in (
            QueryStatus.PROCESSING,
            QueryStatus.SEARCHING,
            QueryStatus.ANALYZING,
            QueryStatus.GENERATING,
        )


class Query(Base, TimestampMixin):
    """
    User's documentation update request.

    Attributes:
        query_text: The user's natural language request
        status: Current processing stage (see QueryStatus)
        status_message: Human-readable status description
        completed_at: When processing finished (success or failure)
        error_message: Error details if status is FAILED

    Relationships:
        suggestions: Generated edit suggestions (cascade delete)

    Usage:
        query = Query(query_text="Update API authentication docs")
        db.add(query)
        await db.flush()
        # Process asynchronously via Celery
        process_query_async.delay(str(query.id), query.query_text)
    """

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