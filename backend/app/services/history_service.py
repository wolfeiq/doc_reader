"""History service for tracking edits."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.history import EditHistory, UserAction

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for managing edit history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_entry(
        self,
        document_id: UUID | None,
        section_id: UUID | None,
        suggestion_id: UUID | None,
        old_content: str,
        new_content: str,
        user_action: UserAction,
        query_text: str | None = None,
        file_path: str | None = None,
        section_title: str | None = None
    ) -> EditHistory:
        """Create a history entry."""
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
    ) -> list[EditHistory]:
        """Get history for a document."""
        result = await self.db.execute(
            select(EditHistory)
            .where(EditHistory.document_id == document_id)
            .order_by(EditHistory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_section_history(self, section_id: UUID) -> list[EditHistory]:
        """Get history for a section."""
        result = await self.db.execute(
            select(EditHistory)
            .where(EditHistory.section_id == section_id)
            .order_by(EditHistory.created_at.desc())
        )
        return list(result.scalars().all())
