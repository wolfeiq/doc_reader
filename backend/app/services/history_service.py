"""
History Service - Edit Audit Trail Management
==============================================

This service maintains an audit log of all document edits.
Every accept/reject action on suggestions is recorded for:

1. Accountability - Track who changed what and when
2. Rollback capability - Store old content for potential undo
3. Analytics - Understand edit patterns and AI suggestion quality
4. Compliance - Audit trail for regulated industries

Data Model:
-----------
EditHistory records contain:
- document_id: Which document was affected
- section_id: Which specific section changed
- suggestion_id: Link to the AI suggestion that triggered the edit
- old_content: Previous text (for rollback)
- new_content: New text after edit
- user_action: ACCEPTED, REJECTED, or MANUAL_EDIT
- query_text: Original user query that generated the suggestion
- file_path, section_title: Denormalized for faster queries

Why Denormalize file_path/section_title?
----------------------------------------
These fields exist on Document/Section models, but we copy them here because:
1. Documents/sections may be deleted, but history should persist
2. Faster queries without JOINs for history listing
3. Historical accuracy - captures the title AT TIME OF EDIT

Production Considerations:
--------------------------
- Add retention policy (auto-delete after N days/months)
- Consider partitioning by date for large tables
- Add compression for old_content/new_content (can be large)
- Index on created_at for time-range queries
"""

import logging
from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.history import EditHistory, UserAction

logger = logging.getLogger(__name__)


class HistoryService:
    """
    Service for managing edit history audit trail.

    Tracks all document modifications with before/after snapshots.
    Used by the suggestion accept/reject flow and manual edits.

    Usage:
        async with get_db() as db:
            service = HistoryService(db)
            await service.create_entry(
                document_id=doc.id,
                section_id=section.id,
                suggestion_id=suggestion.id,
                old_content="old text",
                new_content="new text",
                user_action=UserAction.ACCEPTED,
            )
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session."""
        self.db = db

    async def create_entry(
        self,
        document_id: UUID,
        section_id: UUID | None,
        suggestion_id: UUID | None,
        old_content: str,
        new_content: str,
        user_action: UserAction,
        query_text: str | None = None,
        file_path: str | None = None,
        section_title: str | None = None
    ) -> EditHistory:
        """
        Create a new edit history entry.

        Records a document modification with full context for auditing.
        Called automatically when suggestions are accepted/rejected.

        Args:
            document_id: UUID of the modified document
            section_id: UUID of the modified section (optional for doc-level changes)
            suggestion_id: UUID of the AI suggestion that triggered this edit
            old_content: Content BEFORE the edit (for rollback)
            new_content: Content AFTER the edit
            user_action: One of ACCEPTED, REJECTED, MANUAL_EDIT
            query_text: Original user query (e.g., "Update API version to v2")
            file_path: Document file path (denormalized for persistence)
            section_title: Section title (denormalized for persistence)

        Returns:
            The created EditHistory record

        Example:
            entry = await service.create_entry(
                document_id=doc.id,
                section_id=section.id,
                suggestion_id=suggestion.id,
                old_content="version: 1.0",
                new_content="version: 2.0",
                user_action=UserAction.ACCEPTED,
                query_text="Update to version 2.0",
            )
        """
        entry = EditHistory(
            document_id=document_id,
            section_id=section_id,
            suggestion_id=suggestion_id,
            old_content=old_content,
            new_content=new_content,
            user_action=user_action,
            query_text=query_text,
            file_path=file_path,
            section_title=section_title
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_document_history(
        self,
        document_id: UUID,
        limit: int = 50
    ) -> Sequence[EditHistory]:
        """
        Get edit history for an entire document.

        Returns all edits across all sections of a document,
        ordered by most recent first. Useful for document-level
        audit views and "recent changes" displays.

        Args:
            document_id: UUID of the document to query
            limit: Maximum entries to return (default 50, prevents huge responses)

        Returns:
            List of EditHistory records, newest first

        Note:
            Results are capped at `limit` to prevent memory issues
            on documents with long edit histories. Implement pagination
            if you need full history access.
        """
        result = await self.db.execute(
            select(EditHistory)
            .where(EditHistory.document_id == document_id)
            .order_by(EditHistory.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_section_history(
        self,
        section_id: UUID
    ) -> Sequence[EditHistory]:
        """
        Get edit history for a specific section.

        Returns all edits to a single section, useful for
        understanding how a particular piece of content evolved.
        No limit applied - sections typically have fewer edits.

        Args:
            section_id: UUID of the section to query

        Returns:
            List of EditHistory records for this section, newest first

        Use Cases:
            - "View changes" button on a section
            - Diff view showing section evolution
            - Rollback to previous version
        """
        result = await self.db.execute(
            select(EditHistory)
            .where(EditHistory.section_id == section_id)
            .order_by(EditHistory.created_at.desc())
        )
        return result.scalars().all()