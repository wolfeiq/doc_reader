from uuid import UUID
from xml.dom.minidom import Document
from backend.app.models.document import DocumentSection
from backend.app.models.history import EditHistory, UserAction
from backend.app.models.query import Query
from fastapi import  HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.suggestion import EditSuggestion, SuggestionStatus
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def get_suggestion_or_404(
    db: AsyncSession,
    suggestion_id: UUID,
    *,
    options: list = None,
) -> EditSuggestion:
    stmt = select(EditSuggestion).where(EditSuggestion.id == suggestion_id)
    if options:
        stmt = stmt.options(*options)

    result = await db.execute(stmt)
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(404, "Suggestion not found")
    return suggestion


async def get_query_or_404(db: AsyncSession, query_id: UUID) -> Query:
    result = await db.execute(
        select(Query).where(Query.id == query_id)
    )
    query = result.scalar_one_or_none()
    if not query:
        raise HTTPException(404, "Query not found")
    return query


async def get_history_or_404(db: AsyncSession, history_id: UUID) -> EditHistory:

    result = await db.execute(select(EditHistory).where(EditHistory.id == history_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    return entry


async def list_history_entries(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    action: UserAction | None = None,
    document_id: UUID | None = None,
    section_id: UUID | None = None
) -> list[EditHistory]:

    stmt = select(EditHistory).order_by(EditHistory.created_at.desc())
    
    if action:
        stmt = stmt.where(EditHistory.user_action == action)
    if document_id:
        stmt = stmt.where(EditHistory.document_id == document_id)
    if section_id:
        stmt = stmt.where(EditHistory.section_id == section_id)
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_document_or_404(db: AsyncSession, document_id: UUID) -> Document:
    """Fetch document or raise 404."""
    result = await db.execute(
        select(Document).options(selectinload(Document.sections)).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


async def get_sections_or_404(db: AsyncSession, document_id: UUID) -> list[DocumentSection]:
    """Fetch all sections of a document or raise 404 if document doesn't exist."""
    result = await db.execute(
        select(DocumentSection)
        .where(DocumentSection.document_id == document_id)
        .order_by(DocumentSection.order)
    )
    sections = result.scalars().all()
    if not sections:
        doc_exists = await db.scalar(select(Document.id).where(Document.id == document_id))
        if not doc_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return sections


async def get_pending_suggestions_by_section(
    db: AsyncSession, section_ids: list[UUID]
) -> dict[UUID, EditSuggestion]:
    if not section_ids:
        return {}
    result = await db.execute(
        select(EditSuggestion)
        .where(EditSuggestion.section_id.in_(section_ids), EditSuggestion.status == SuggestionStatus.PENDING)
    )
    return {s.section_id: s for s in result.scalars()}


async def decode_upload_file(file: UploadFile) -> str:

    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .md files are supported")
    content = await file.read()
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be UTF-8 encoded")
