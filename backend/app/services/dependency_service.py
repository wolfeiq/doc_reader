import re
import logging
from pathlib import Path
from uuid import UUID
from typing import Literal, Sequence
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.models.section_dependency import SectionDependency
from app.schemas.document import (
    DependencyGraphResponse,
    DependencyNode,
    DependencyEdge,
)

logger = logging.getLogger(__name__)


class DependencyService:
    MARKDOWN_LINK_PATTERN: re.Pattern[str] = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    EXPLICIT_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
        r'(?:see|refer to|check|read|described in|explained in)\s+(?:the\s+)?'
        r'["\']([^"\']{3,})["\'](?:\s+section)?',
        re.IGNORECASE
    )

    CODE_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
        r'`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*){1,})`'
    )

    COMMON_CODE_WORDS: set[str] = {
        'id', 'name', 'type', 'value', 'data', 'item', 'user', 'result',
        'error', 'status', 'code', 'message', 'text', 'true', 'false',
        'null', 'none', 'self', 'this', 'var', 'let', 'const'
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_and_store_dependencies(
        self, 
        section: DocumentSection
    ) -> Sequence[SectionDependency]:
        dependencies: list[SectionDependency] = []

        if not section.document:
            await self.db.refresh(section, ["document"])
        
        references = self._extract_references(
            section.content, 
            section.document.file_path if section.document else ""
        )
        
        for ref_type, ref_value, anchor in references:
            target_section = await self._resolve_reference(
                ref_value, 
                anchor,
                section.document_id,
                section.document.file_path if section.document else ""
            )
            
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

    def _extract_references(
        self, 
        content: str, 
        current_file_path: str
    ) -> list[tuple[str, str, str | None]]:
        references: list[tuple[str, str, str | None]] = []
        seen = set()  # Avoid duplicates


        for match in self.MARKDOWN_LINK_PATTERN.finditer(content):
            link_text, link_url = match.groups()
            
            if link_url.startswith(('http://', 'https://', 'mailto:')):
                continue
            
            if link_url.startswith('#'):
                anchor = link_url[1:] 
                ref_key = f"anchor:{anchor}"
                if ref_key not in seen:
                    references.append(('anchor', current_file_path, anchor))
                    seen.add(ref_key)
                continue
            
            if '#' in link_url:
                file_path, anchor = link_url.split('#', 1)
            else:
                file_path = link_url
                anchor = None

            normalized_path = self._normalize_path(file_path, current_file_path)
            ref_key = f"link:{normalized_path}:{anchor}"
            
            if ref_key not in seen and normalized_path:
                references.append(('link', normalized_path, anchor))
                seen.add(ref_key)

        for match in self.EXPLICIT_REFERENCE_PATTERN.finditer(content):
            reference_text = match.group(1).strip()
            
            if len(reference_text) < 3 or len(reference_text) > 100:
                continue
            
            ref_key = f"reference:{reference_text}"
            if ref_key not in seen:
                references.append(('reference', reference_text, None))
                seen.add(ref_key)

        for match in self.CODE_REFERENCE_PATTERN.finditer(content):
            code_ref = match.group(1)
            
            if code_ref.lower() in self.COMMON_CODE_WORDS:
                continue
            
            ref_key = f"code:{code_ref}"
            if ref_key not in seen:
                references.append(('code', code_ref, None))
                seen.add(ref_key)
        
        return references

    def _normalize_path(self, ref_path: str, current_path: str) -> str:
        try:
            current_dir = str(Path(current_path).parent)
            
            if ref_path.startswith('../') or ref_path.startswith('./'):
                resolved = Path(current_dir) / ref_path
                normalized = resolved.resolve()
            else:
                normalized = (Path(current_dir) / ref_path).resolve()

            path_str = str(normalized)
            if not path_str.endswith('.md'):
                path_str += '.md'
            
            return path_str
        except Exception as e:
            logger.debug(f"Failed to normalize path {ref_path}: {e}")
            clean = ref_path.strip()
            if not clean.endswith('.md') and '/' in clean:
                clean += '.md'
            return clean

    @staticmethod
    def _generate_slug(title: str) -> str:
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')

    async def _resolve_reference(
        self, 
        reference: str, 
        anchor: str | None,
        current_doc_id: UUID,
        current_file_path: str
    ) -> DocumentSection | None:
        if anchor:
            anchor_slug = self._generate_slug(anchor)
            if reference.endswith('.md') or '/' in reference:
                result = await self.db.execute(
                    select(DocumentSection)
                    .join(Document)
                    .where(
                        or_(
                            Document.file_path == reference,
                            Document.file_path.endswith(reference),
                            Document.file_path.like(f'%/{reference}')
                        )
                    )
                    .where(
                        or_(
                            func.lower(DocumentSection.section_title) == anchor.lower(),
                            func.lower(DocumentSection.section_title).like(f'%{anchor.lower()}%')
                        )
                    )
                    .limit(1)
                )
                section = result.scalar_one_or_none()
                if section:
                    return section
            
            result = await self.db.execute(
                select(DocumentSection)
                .where(DocumentSection.document_id == current_doc_id)
                .where(
                    or_(
                        func.lower(DocumentSection.section_title) == anchor.lower(),
                        func.lower(DocumentSection.section_title).like(f'%{anchor.lower()}%')
                    )
                )
                .limit(1)
            )
            section = result.scalar_one_or_none()
            if section:
                return section
        

        if reference.endswith('.md') or '/' in reference:
            result = await self.db.execute(
                select(DocumentSection)
                .join(Document)
                .where(
                    or_(
                        Document.file_path == reference,
                        Document.file_path.endswith(reference),
                        Document.file_path.like(f'%/{reference}')
                    )
                )
                .order_by(DocumentSection.order)
                .limit(1)
            )
            section = result.scalar_one_or_none()
            if section:
                return section
            
            filename = reference.split('/')[-1].replace('.md', '')
            result = await self.db.execute(
                select(DocumentSection)
                .join(Document)
                .where(Document.file_path.like(f'%{filename}%'))
                .order_by(DocumentSection.order)
                .limit(1)
            )
            section = result.scalar_one_or_none()
            if section:
                return section
        
        result = await self.db.execute(
            select(DocumentSection)
            .where(func.lower(DocumentSection.section_title) == reference.lower())
            .limit(1)
        )
        section = result.scalar_one_or_none()
        if section:
            return section

        if len(reference) >= 5:
            result = await self.db.execute(
                select(DocumentSection)
                .where(func.lower(DocumentSection.section_title).like(f'%{reference.lower()}%'))
                .limit(1)
            )
            section = result.scalar_one_or_none()
            if section:
                return section
            
        if '.' in reference or '_' in reference:
            result = await self.db.execute(
                select(DocumentSection)
                .where(DocumentSection.content.like(f'%{reference}%'))
                .limit(1)
            )
            section = result.scalar_one_or_none()
            if section:
                return section
        
        return None

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