import hashlib
import re
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentSection, SectionDependency
from app.schemas.document import DocumentCreate, DocumentUpdate


class DocumentService:
    """Service for document operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def calculate_checksum(content: str) -> str:
        """Calculate SHA-256 checksum of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Document]:
        """Get all documents."""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .offset(skip)
            .limit(limit)
            .order_by(Document.file_path)
        )
        return list(result.scalars().all())

    async def get_by_id(self, document_id: UUID) -> Optional[Document]:
        """Get a document by ID."""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_file_path(self, file_path: str) -> Optional[Document]:
        """Get a document by file path."""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.file_path == file_path)
        )
        return result.scalar_one_or_none()

    async def create(self, data: DocumentCreate) -> Document:
        """Create a new document."""
        checksum = self.calculate_checksum(data.content)
        
        # Extract title from content if not provided
        title = data.title
        if not title:
            # Try to extract from first heading
            match = re.match(r"^#\s+(.+)$", data.content, re.MULTILINE)
            if match:
                title = match.group(1).strip()
            else:
                title = data.file_path.split("/")[-1].replace(".md", "").replace("_", " ").title()

        document = Document(
            file_path=data.file_path,
            title=title,
            content=data.content,
            checksum=checksum,
        )
        self.db.add(document)
        await self.db.flush()

        # Parse and create sections
        sections = self._parse_sections(data.content)
        for i, section_data in enumerate(sections):
            section = DocumentSection(
                document_id=document.id,
                section_title=section_data["title"],
                content=section_data["content"],
                order=i,
                start_line=section_data.get("start_line"),
                end_line=section_data.get("end_line"),
            )
            self.db.add(section)

        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def update(self, document_id: UUID, data: DocumentUpdate) -> Optional[Document]:
        """Update a document."""
        document = await self.get_by_id(document_id)
        if not document:
            return None

        if data.content is not None:
            document.content = data.content
            document.checksum = self.calculate_checksum(data.content)
            
            # Delete old sections
            for section in document.sections:
                await self.db.delete(section)
            
            # Create new sections
            sections = self._parse_sections(data.content)
            for i, section_data in enumerate(sections):
                section = DocumentSection(
                    document_id=document.id,
                    section_title=section_data["title"],
                    content=section_data["content"],
                    order=i,
                    start_line=section_data.get("start_line"),
                    end_line=section_data.get("end_line"),
                )
                self.db.add(section)

        if data.title is not None:
            document.title = data.title

        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def delete(self, document_id: UUID) -> bool:
        """Delete a document."""
        document = await self.get_by_id(document_id)
        if not document:
            return False
        
        await self.db.delete(document)
        await self.db.flush()
        return True

    async def get_section_by_id(self, section_id: UUID) -> Optional[DocumentSection]:
        """Get a section by ID."""
        result = await self.db.execute(
            select(DocumentSection).where(DocumentSection.id == section_id)
        )
        return result.scalar_one_or_none()

    async def update_section_content(
        self, section_id: UUID, new_content: str
    ) -> Optional[DocumentSection]:
        """Update a section's content and rebuild the full document."""
        section = await self.get_section_by_id(section_id)
        if not section:
            return None

        # Update section content
        section.content = new_content
        
        # Rebuild full document content
        document = await self.get_by_id(section.document_id)
        if document:
            # Sort sections by order and rebuild
            sections = sorted(document.sections, key=lambda s: s.order)
            full_content = "\n\n".join(
                f"{'#' * (1 if i == 0 else 2)} {s.section_title}\n\n{s.content}" 
                if s.section_title else s.content
                for i, s in enumerate(sections)
            )
            document.content = full_content
            document.checksum = self.calculate_checksum(full_content)

        await self.db.flush()
        return section

    def _parse_sections(self, content: str) -> list[dict]:
        """Parse markdown content into sections based on headers."""
        sections = []
        lines = content.split("\n")
        current_section = {"title": None, "content": [], "start_line": 1}
        
        for i, line in enumerate(lines, 1):
            # Check for headers (# or ##)
            header_match = re.match(r"^(#{1,3})\s+(.+)$", line)
            
            if header_match:
                # Save previous section if it has content
                if current_section["content"] or current_section["title"]:
                    current_section["end_line"] = i - 1
                    current_section["content"] = "\n".join(current_section["content"]).strip()
                    if current_section["content"] or current_section["title"]:
                        sections.append(current_section)
                
                # Start new section
                current_section = {
                    "title": header_match.group(2).strip(),
                    "content": [],
                    "start_line": i,
                }
            else:
                current_section["content"].append(line)
        
        # Don't forget the last section
        if current_section["content"] or current_section["title"]:
            current_section["end_line"] = len(lines)
            current_section["content"] = "\n".join(current_section["content"]).strip()
            sections.append(current_section)
        
        return sections

    async def get_document_count(self) -> int:
        """Get total document count."""
        result = await self.db.execute(select(func.count(Document.id)))
        return result.scalar() or 0

    async def get_section_count(self) -> int:
        """Get total section count."""
        result = await self.db.execute(select(func.count(DocumentSection.id)))
        return result.scalar() or 0
