import re
import logging
from uuid import UUID
from typing import Literal, Sequence
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentSection, SectionDependency
from app.schemas.document import (
    DependencyGraphResponse,
    DependencyNode,
    DependencyEdge,
)

logger = logging.getLogger(__name__)


class DependencyService:

    LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    REFERENCE_PATTERN = re.compile(
        r'(?:see|refer to|check|read)\s+["\']?([^"\'.\n]+)["\']?', 
        re.IGNORECASE
    )
    CODE_REFERENCE_PATTERN = re.compile(
        r'`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)`'
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_and_store_dependencies(
        self, 
        section: DocumentSection
    ) -> Sequence[SectionDependency]:
        dependencies: list[SectionDependency] = []

        references = self._extract_references(section.content)
        
        for ref_type, ref_value in references:
            target_section = await self._resolve_reference(ref_value, section.document_id)
            
            if target_section and target_section.id != section.id:
                existing = await self.db.execute(
                    select(SectionDependency).where(
                        SectionDependency.source_section_id == section.id,
                        SectionDependency.target_section_id == target_section.id
                    )
                )
                if not existing.scalar_one_or_none():
                    dep = SectionDependency(
                        source_section_id=section.id,
                        target_section_id=target_section.id,
                        dependency_type=ref_type
                    )
                    self.db.add(dep)
                    dependencies.append(dep)
        
        if dependencies:
            await self.db.flush()
            logger.info(f"Found {len(dependencies)} dependencies for section {section.id}")
        
        return dependencies

    def _extract_references(self, content: str) -> list[tuple[str, str]]:

        references: list[tuple[str, str]] = []

        for match in self.LINK_PATTERN.finditer(content):
            link_text, link_url = match.groups()
            if not link_url.startswith(('http://', 'https://', '#')):
                references.append(('link', link_url))
        

        for match in self.REFERENCE_PATTERN.finditer(content):
            references.append(('reference', match.group(1).strip()))
        
        for match in self.CODE_REFERENCE_PATTERN.finditer(content):
            references.append(('code', match.group(1)))
        
        return references

    async def _resolve_reference(
        self, 
        reference: str, 
        current_doc_id: UUID
    ) -> DocumentSection | None:
        if reference.endswith('.md'):
            result = await self.db.execute(
                select(DocumentSection)
                .join(Document)
                .where(Document.file_path.ilike(f'%{reference}%'))
                .limit(1)
            )
            section = result.scalar_one_or_none()
            if section:
                return section
        
        result = await self.db.execute(
            select(DocumentSection)
            .where(DocumentSection.section_title.ilike(f'%{reference}%'))
            .limit(1)
        )
        section = result.scalar_one_or_none()
        if section:
            return section

        result = await self.db.execute(
            select(DocumentSection)
            .where(DocumentSection.content.ilike(f'%{reference}%'))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_dependencies(
        self,
        section_id: UUID,
        direction: Literal["incoming", "outgoing", "both"] = "both"
    ) -> dict[str, list[dict[str, str | None]]]:

        result: dict[str, list[dict[str, str | None]]] = {
            "incoming": [], 
            "outgoing": []
        }
        
        if direction in ("outgoing", "both"):
            query = (
                select(SectionDependency)
                .options(selectinload(SectionDependency.target_section))
                .where(SectionDependency.source_section_id == section_id)
            )
            deps = await self.db.execute(query)
            for dep in deps.scalars():
                result["outgoing"].append({
                    "dependency_id": str(dep.id),
                    "section_id": str(dep.target_section_id),
                    "section_title": (
                        dep.target_section.section_title 
                        if dep.target_section else None
                    ),
                    "dependency_type": dep.dependency_type
                })
        
        if direction in ("incoming", "both"):
            query = (
                select(SectionDependency)
                .options(selectinload(SectionDependency.source_section))
                .where(SectionDependency.target_section_id == section_id)
            )
            deps = await self.db.execute(query)
            for dep in deps.scalars():
                result["incoming"].append({
                    "dependency_id": str(dep.id),
                    "section_id": str(dep.source_section_id),
                    "section_title": (
                        dep.source_section.section_title 
                        if dep.source_section else None
                    ),
                    "dependency_type": dep.dependency_type
                })
        
        return result

    async def build_dependency_graph(
        self, 
        document_id: UUID | None = None
    ) -> DependencyGraphResponse:

        query = select(DocumentSection).options(
            selectinload(DocumentSection.document)
        )
        if document_id:
            query = query.where(DocumentSection.document_id == document_id)
        
        sections_result = await self.db.execute(query)
        sections = sections_result.scalars().all()
        
        nodes: list[DependencyNode] = []
        for section in sections:
            nodes.append(
                DependencyNode(
                    section_id=section.id,
                    section_title=section.section_title,
                    file_path=section.document.file_path if section.document else "",
                    document_id=section.document_id,
                )
            )

        section_ids = [s.id for s in sections]
        edges: list[DependencyEdge] = []
        
        if section_ids:
            deps_result = await self.db.execute(
                select(SectionDependency).where(
                    or_(
                        SectionDependency.source_section_id.in_(section_ids),
                        SectionDependency.target_section_id.in_(section_ids)
                    )
                )
            )
            
            for dep in deps_result.scalars():
                edges.append(
                    DependencyEdge(
                        source_section_id=dep.source_section_id,
                        target_section_id=dep.target_section_id,
                        dependency_type=dep.dependency_type,
                    )
                )
        
        return DependencyGraphResponse(nodes=nodes, edges=edges)

    async def rebuild_all_dependencies(self) -> int:

        await self.db.execute(
            SectionDependency.__table__.delete()
        )
        

        result = await self.db.execute(
            select(DocumentSection).options(
                selectinload(DocumentSection.document)
            )
        )
        sections = result.scalars().all()
        
        total = 0
        for section in sections:
            deps = await self.parse_and_store_dependencies(section)
            total += len(deps)
        
        await self.db.commit()
        logger.info(f"Rebuilt dependency graph: {total} dependencies")
        return total