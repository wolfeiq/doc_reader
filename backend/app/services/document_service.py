from __future__ import annotations
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.services.dependency_service import DependencyService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


@dataclass
class ParsedSection:
    title: str
    content: str
    start_line: int
    end_line: int
    level: int


class DocumentService:

    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._search_service: SearchService | None = None
        self._dependency_service: DependencyService | None = None

    @property
    def search_service(self) -> SearchService:
        if self._search_service is None:
            self._search_service = SearchService()
        return self._search_service

    @property
    def dependency_service(self) -> DependencyService:
        if self._dependency_service is None:
            self._dependency_service = DependencyService(self.db)
        return self._dependency_service

    @staticmethod
    def calculate_checksum(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def parse_sections(cls, content: str) -> list[ParsedSection]:
        if not content.strip():
            return []

        sections: list[ParsedSection] = []
        lines = content.split("\n")

        current_title = ""
        current_lines: list[str] = []
        current_start = 1
        current_level = 0

        in_code_block = False
        in_html_block = False
        in_table = False
        in_blockquote = False
        in_list = False
        code_fence_marker = None  
        html_tag_stack = []

        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            
            if stripped.startswith("```") or stripped.startswith("~~~"):
                if not in_code_block:
                    in_code_block = True
                    code_fence_marker = stripped[:3]
                elif stripped.startswith(code_fence_marker):
                    in_code_block = False
                    code_fence_marker = None
            
            if not in_code_block:
                opening_tags = re.findall(r'<(\w+)(?:\s|>)', stripped)
                for tag in opening_tags:
                    if tag.lower() in ['div', 'section', 'article', 'pre', 'table', 'ul', 'ol', 'blockquote']:
                        html_tag_stack.append(tag.lower())
                        in_html_block = True

                closing_tags = re.findall(r'</(\w+)>', stripped)
                for tag in closing_tags:
                    if tag.lower() in html_tag_stack:
                        html_tag_stack.remove(tag.lower())
                
                in_html_block = len(html_tag_stack) > 0

            if not in_code_block and '|' in line and not in_html_block:
                in_table = True
            elif in_table and stripped and '|' not in line and not stripped.startswith('-'):
                in_table = False
            
            if not in_code_block and stripped.startswith('>'):
                in_blockquote = True
            elif in_blockquote and stripped and not stripped.startswith('>'):
                in_blockquote = False
            
            if not in_code_block and (
                re.match(r'^[\*\-\+]\s', stripped) or
                re.match(r'^\d+\.\s', stripped)
            ):
                in_list = True
            elif in_list and stripped and not re.match(r'^[\*\-\+\d]', stripped):
                if not line.startswith((' ', '\t')) and stripped:
                    in_list = False

            header_match = cls.HEADER_PATTERN.match(line)

            in_any_block = (
                in_code_block or 
                in_html_block or 
                in_table or 
                in_blockquote or
                in_list
            )

            if header_match and not in_any_block:
                if current_lines or current_title:
                    sections.append(
                        ParsedSection(
                            title=current_title,
                            content="\n".join(current_lines).strip(),
                            start_line=current_start,
                            end_line=i - 1,
                            level=current_level,
                        )
                    )
                
                current_level = len(header_match.group(1))
                current_title = header_match.group(2).strip()
                current_lines = []
                current_start = i
            else:
                current_lines.append(line)

        if current_lines or current_title:
            sections.append(
                ParsedSection(
                    title=current_title,
                    content="\n".join(current_lines).strip(),
                    start_line=current_start,
                    end_line=len(lines),
                    level=current_level,
                )
            )

        return sections

    def _extract_title(self, sections: list[ParsedSection], file_path: str) -> str:
        for section in sections:
            if section.level == 1 and section.title:
                return section.title
        return file_path.split("/")[-1].replace(".md", "").replace("-", " ").title()

    async def create_document(
        self,
        file_path: str,
        content: str,
        generate_embeddings: bool = True,
    ) -> Document:
        existing = await self.get_document_by_path(file_path)
        if existing:
            return await self.update_document(file_path, content, generate_embeddings)

        parsed_sections = self.parse_sections(content)
        title = self._extract_title(parsed_sections, file_path)
        
        doc = Document(
            file_path=file_path,
            title=title,
            content=content,
            checksum=self.calculate_checksum(content),
        )
        self.db.add(doc)
        await self.db.flush()

        for i, parsed in enumerate(parsed_sections):
            section = DocumentSection(
                document_id=doc.id,
                section_title=parsed.title or f"Section {i + 1}",
                content=parsed.content,
                order=i,
                start_line=parsed.start_line,
                end_line=parsed.end_line,
            )
            self.db.add(section)
            await self.db.flush()

            if generate_embeddings and parsed.content.strip():
                try:
                    embedding_id = await self.search_service.add_section(
                        section_id=str(section.id),
                        content=parsed.content,
                        metadata={
                            "document_id": str(doc.id),
                            "file_path": file_path,
                            "section_title": section.section_title,
                            "order": i,
                        },
                    )
                    section.embedding_id = embedding_id
                except Exception as e:
                    logger.warning(f"Failed to generate embedding for section: {e}")

        await self.db.commit()

        await self._build_section_dependencies(doc)

        logger.info(
            f"Created document '{file_path}' with {len(parsed_sections)} sections"
        )
        return doc

    async def _build_section_dependencies(self, doc: Document) -> None:
        await self.db.refresh(doc, ["sections"])
        for section in doc.sections:
            try:
                await self.dependency_service.parse_and_store_dependencies(section)
            except Exception as e:
                logger.warning(
                    f"Failed to build dependencies for section {section.id}: {e}"
                )
        await self.db.commit()

    async def update_document(
        self,
        file_path: str,
        content: str,
        generate_embeddings: bool = True,
    ) -> Document:

        doc = await self.get_document_by_path(file_path)
        if not doc:
            return await self.create_document(file_path, content, generate_embeddings)

        new_checksum = self.calculate_checksum(content)
        if doc.checksum == new_checksum:
            logger.debug(f"Document '{file_path}' unchanged, skipping update")
            return doc
        
        await self.search_service.delete_by_document(str(doc.id))
        for section in doc.sections:
            await self.db.delete(section)
        await self.db.flush()

        doc.content = content
        doc.checksum = new_checksum

        parsed_sections = self.parse_sections(content)
        doc.title = self._extract_title(parsed_sections, file_path)

        for i, parsed in enumerate(parsed_sections):
            section = DocumentSection(
                document_id=doc.id,
                section_title=parsed.title or f"Section {i + 1}",
                content=parsed.content,
                order=i,
                start_line=parsed.start_line,
                end_line=parsed.end_line,
            )
            self.db.add(section)
            await self.db.flush()

            if generate_embeddings and parsed.content.strip():
                try:
                    section.embedding_id = await self.search_service.add_section(
                        section_id=str(section.id),
                        content=parsed.content,
                        metadata={
                            "document_id": str(doc.id),
                            "file_path": file_path,
                            "section_title": section.section_title,
                            "order": i,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to update embedding: {e}")

        await self.db.commit()
        await self._build_section_dependencies(doc)

        logger.info(
            f"Updated document '{file_path}' with {len(parsed_sections)} sections"
        )
        return doc

    async def get_document(self, document_id: UUID) -> Document | None:
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_document_by_path(self, file_path: str) -> Document | None:

        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.file_path == file_path)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Document]:

        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .order_by(Document.file_path)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def delete_document(self, document_id: UUID) -> bool:

        doc = await self.get_document(document_id)
        if not doc:
            return False

        await self.search_service.delete_by_document(str(document_id))
        await self.db.delete(doc)
        await self.db.commit()

        logger.info(f"Deleted document '{doc.file_path}'")
        return True

    async def get_section(self, section_id: UUID) -> DocumentSection | None:
        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == section_id)
        )
        return result.scalar_one_or_none()

    async def apply_suggestion_to_section(
        self,
        section_id: UUID,
        new_content: str,
    ) -> DocumentSection | None:
 
        section = await self.get_section(section_id)
        if not section:
            return None

        section.content = new_content


        if section.embedding_id:
            try:
                await self.search_service.add_section(
                    section_id=str(section.id),
                    content=new_content,
                    metadata={
                        "document_id": str(section.document_id),
                        "file_path": (
                            section.document.file_path 
                            if section.document 
                            else None
                        ),
                        "section_title": section.section_title,
                        "order": section.order,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to update embedding: {e}")

        if section.document:
            await self._rebuild_document_content(section.document_id)

        await self.db.commit()
        logger.info(f"Applied changes to section {section_id}")
        return section

    async def _rebuild_document_content(self, document_id: UUID) -> None:

        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return

        parts: list[str] = []
        for section in sorted(doc.sections, key=lambda s: s.order):
            if section.section_title:
                parts.append(f"## {section.section_title}")
            if section.content:
                parts.append(section.content)
            parts.append("")  # Blank line between sections

        doc.content = "\n".join(parts).strip()
        doc.checksum = self.calculate_checksum(doc.content)