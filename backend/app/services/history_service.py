from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.history import EditHistory, UserAction
from app.schemas.history import HistoryCreate, HistoryFilter


class HistoryService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: HistoryCreate) -> EditHistory:
        history = EditHistory(
            document_id=data.document_id,
            section_id=data.section_id,
            suggestion_id=data.suggestion_id,
            old_content=data.old_content,
            new_content=data.new_content,
            user_action=data.user_action,
            query_text=data.query_text,
            file_path=data.file_path,
            section_title=data.section_title,
        )
        self.db.add(history)
        await self.db.flush()
        await self.db.refresh(history)
        return history

    async def get_by_id(self, history_id: UUID) -> Optional[EditHistory]:
        result = await self.db.execute(
            select(EditHistory).where(EditHistory.id == history_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        filters: Optional[HistoryFilter] = None,
    ) -> tuple[list[EditHistory], int]:

        query = select(EditHistory)
        count_query = select(func.count(EditHistory.id))

        conditions = []
        if filters:
            if filters.document_id:
                conditions.append(EditHistory.document_id == filters.document_id)
            if filters.section_id:
                conditions.append(EditHistory.section_id == filters.section_id)
            if filters.user_action:
                conditions.append(EditHistory.user_action == filters.user_action)
            if filters.start_date:
                conditions.append(EditHistory.created_at >= filters.start_date)
            if filters.end_date:
                conditions.append(EditHistory.created_at <= filters.end_date)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))


        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0


        query = query.order_by(EditHistory.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_by_document(
        self, document_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[EditHistory]:
        result = await self.db.execute(
            select(EditHistory)
            .where(EditHistory.document_id == document_id)
            .order_by(EditHistory.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 20) -> list[EditHistory]:
        result = await self.db.execute(
            select(EditHistory)
            .order_by(EditHistory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_stats(self) -> dict:
        total_result = await self.db.execute(select(func.count(EditHistory.id)))
        total = total_result.scalar() or 0
        stats = {"total": total, "by_action": {}}
        for action in UserAction:
            count_result = await self.db.execute(
                select(func.count(EditHistory.id)).where(
                    EditHistory.user_action == action
                )
            )
            stats["by_action"][action.value] = count_result.scalar() or 0

        return stats