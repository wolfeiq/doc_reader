"""Document service with section parsing and embedding integration."""

import hashlib
import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentSection
from app.services.search_service import SearchService
from app.services.dependency_service import DependencyService

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document management with embedding integration."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.search_service = SearchService()
        self.dependency_service = DependencyService(db)

    @staticmethod
    def calculate_checksum(content: str) -> str:
        """Calculate SHA-256 checksum of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def parse_sections(content: str) -> list[dict]:
        """Parse markdown content into sections based on headers."""
        sections = []
        lines = content.split('\n')
        
        current_section = {
            "title": "",
            "content_lines": [],
            "start_line": 1,
            "level": 0
        }
        
        for i, line in enumerate(lines, start=1):
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if header_match:
                # Save previous section if it has content
                if current_section["content_lines"] or current_section["title"]:
                    sections.append({
                        "title": current_section["title"],
                        "content": '\n'.join(current_section["content_lines"]).strip(),
                        "start_line": current_section["start_line"],
                        "end_line": i - 1,
                        "level": current_section["level"]
                    })
                
                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                current_section = {
                    "title": title,
                    "content_lines": [],
                    "start_line": i,
                    "level": level
                }
            else:
                current_section["content_lines"].append(line)
        
        # Don't forget the last section
        if current_section["content_lines"] or current_section["title"]:
            sections.append({
                "title": current_section["title"],
                "content": '\n'.join(current_section["content_lines"]).strip(),
                "start_line": current_section["start_line"],
                "end_line": len(lines),
                "level": current_section["level"]
            })
        
        return sections

    async def create_document(
        self,
        file_path: str,
        content: str,
        generate_embeddings: bool = True
    ) -> Document:
        """Create a document with sections and embeddings."""
        
        # Check if document exists
        existing = await self.db.execute(
            select(Document).where(Document.file_path == file_path)
        )
        if existing.scalar_one_or_none():
            return await self.update_document(file_path, content, generate_embeddings)
        
        # Parse sections
        parsed_sections = self.parse_sections(content)
        
        # Extract title from first H1 or filename
        title = file_path.split('/')[-1].replace('.md', '')
        for section in parsed_sections:
            if section["level"] == 1:
                title = section["title"]
                break
        
        # Create document
        doc = Document(
            file_path=file_path,
            title=title,
            content=content,
            checksum=self.calculate_checksum(content)
        )
        self.db.add(doc)
        await self.db.flush()
        
        # Create sections
        for i, section_data in enumerate(parsed_sections):
            section = DocumentSection(
                document_id=doc.id,
                section_title=section_data["title"] or f"Section {i + 1}",
                content=section_data["content"],
                order=i,
                start_line=section_data["start_line"],
                end_line=section_data["end_line"]
            )
            self.db.add(section)
            await self.db.flush()
            
            # Generate embedding
            if generate_embeddings and section_data["content"].strip():
                embedding_id = await self.search_service.add_section(
                    section_id=str(section.id),
                    content=section_data["content"],
                    metadata={
                        "document_id": str(doc.id),
                        "file_path": file_path,
                        "section_title": section.section_title,
                        "order": i
                    }
                )
                section.embedding_id = embedding_id
        
        await self.db.commit()
        
        # Build dependencies (after commit so all sections exist)
        await self.db.refresh(doc, ["sections"])
        for section in doc.sections:
            await self.dependency_service.parse_and_store_dependencies(section)
        await self.db.commit()
        
        logger.info(f"Created document {file_path} with {len(parsed_sections)} sections")
        return doc

    async def update_document(
        self,
        file_path: str,
        content: str,
        generate_embeddings: bool = True
    ) -> Document:
        """Update an existing document, re-parsing sections and embeddings."""
        
        # Get existing document
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.file_path == file_path)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            return await self.create_document(file_path, content, generate_embeddings)
        
        # Check if content changed
        new_checksum = self.calculate_checksum(content)
        if doc.checksum == new_checksum:
            logger.info(f"Document {file_path} unchanged, skipping update")
            return doc
        
        # Delete old embeddings
        await self.search_service.delete_by_document(str(doc.id))
        
        # Delete old sections
        for section in doc.sections:
            await self.db.delete(section)
        await self.db.flush()
        
        # Update document
        doc.content = content
        doc.checksum = new_checksum
        
        # Re-parse and create new sections
        parsed_sections = self.parse_sections(content)
        
        # Update title
        for section in parsed_sections:
            if section["level"] == 1:
                doc.title = section["title"]
                break
        
        for i, section_data in enumerate(parsed_sections):
            section = DocumentSection(
                document_id=doc.id,
                section_title=section_data["title"] or f"Section {i + 1}",
                content=section_data["content"],
                order=i,
                start_line=section_data["start_line"],
                end_line=section_data["end_line"]
            )
            self.db.add(section)
            await self.db.flush()
            
            if generate_embeddings and section_data["content"].strip():
                embedding_id = await self.search_service.add_section(
                    section_id=str(section.id),
                    content=section_data["content"],
                    metadata={
                        "document_id": str(doc.id),
                        "file_path": file_path,
                        "section_title": section.section_title,
                        "order": i
                    }
                )
                section.embedding_id = embedding_id
        
        await self.db.commit()
        
        # Rebuild dependencies
        await self.db.refresh(doc, ["sections"])
        for section in doc.sections:
            await self.dependency_service.parse_and_store_dependencies(section)
        await self.db.commit()
        
        logger.info(f"Updated document {file_path} with {len(parsed_sections)} sections")
        return doc

    async def get_document(self, document_id: UUID) -> Document | None:
        """Get a document by ID with sections."""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_document_by_path(self, file_path: str) -> Document | None:
        """Get a document by file path."""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.file_path == file_path)
        )
        return result.scalar_one_or_none()

    async def list_documents(self, skip: int = 0, limit: int = 100) -> list[Document]:
        """List all documents."""
        result = await self.db.execute(
            select(Document)
            .order_by(Document.file_path)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_document(self, document_id: UUID) -> bool:
        """Delete a document and its sections/embeddings."""
        doc = await self.get_document(document_id)
        if not doc:
            return False
        
        # Delete from vector store
        await self.search_service.delete_by_document(str(document_id))
        
        # Delete from DB (cascade handles sections)
        await self.db.delete(doc)
        await self.db.commit()
        
        logger.info(f"Deleted document {doc.file_path}")
        return True

    async def get_section(self, section_id: UUID) -> DocumentSection | None:
        """Get a section by ID."""
        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == section_id)
        )
        return result.scalar_one_or_none()

    async def apply_suggestion_to_section(
        self,
        section_id: UUID,
        new_content: str
    ) -> DocumentSection | None:
        """Apply new content to a section and update embeddings."""
        section = await self.get_section(section_id)
        if not section:
            return None
        
        old_content = section.content
        section.content = new_content
        
        # Update embedding
        if section.embedding_id:
            await self.search_service.reindex_section(
                section_id=str(section.id),
                content=new_content,
                metadata={
                    "document_id": str(section.document_id),
                    "file_path": section.document.file_path if section.document else None,
                    "section_title": section.section_title,
                    "order": section.order
                }
            )
        
        # Update full document content
        if section.document:
            await self._rebuild_document_content(section.document_id)
        
        await self.db.commit()
        logger.info(f"Applied changes to section {section_id}")
        return section

    async def _rebuild_document_content(self, document_id: UUID):
        """Rebuild full document content from sections."""
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return
        
        # Sort sections and rebuild content
        sorted_sections = sorted(doc.sections, key=lambda s: s.order)
        parts = []
        for section in sorted_sections:
            if section.section_title:
                # Determine header level (default to h2)
                parts.append(f"## {section.section_title}")
            if section.content:
                parts.append(section.content)
            parts.append("")  # Empty line between sections
        
        doc.content = '\n'.join(parts)
        doc.checksum = self.calculate_checksum(doc.content)
