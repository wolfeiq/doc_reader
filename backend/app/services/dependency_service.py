import re
import logging
from uuid import UUID
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document, DocumentSection, SectionDependency

logger = logging.getLogger(__name__)


class DependencyService:

    # Patterns for finding cross-references in markdown
    LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')  # [text](url)
    REFERENCE_PATTERN = re.compile(r'(?:see|refer to|check|read)\s+["\']?([^"\'.\n]+)["\']?', re.IGNORECASE)
    CODE_REFERENCE_PATTERN = re.compile(r'`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)`')

    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_and_store_dependencies(self, section: DocumentSection) -> list[SectionDependency]:
        """Parse a section's content for references and store dependencies."""
        dependencies = []
        
        # Find all potential references
        references = self._extract_references(section.content)
        
        for ref_type, ref_value in references:
            # Try to resolve the reference to an actual section
            target_section = await self._resolve_reference(ref_value, section.document_id)
            
            if target_section and target_section.id != section.id:
                # Check if dependency already exists
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
        """Extract all references from content."""
        references = []
        
        # Markdown links
        for match in self.LINK_PATTERN.finditer(content):
            link_text, link_url = match.groups()
            if not link_url.startswith(('http://', 'https://', '#')):
                references.append(('link', link_url))
        
        # Text references ("see X", "refer to Y")
        for match in self.REFERENCE_PATTERN.finditer(content):
            references.append(('reference', match.group(1).strip()))
        
        # Code references (function names, class names)
        for match in self.CODE_REFERENCE_PATTERN.finditer(content):
            references.append(('code', match.group(1)))
        
        return references

    async def _resolve_reference(
        self, 
        reference: str, 
        current_doc_id: UUID
    ) -> DocumentSection | None:
        """Try to resolve a reference to an actual section."""
        
        # Try exact file path match
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
        
        # Try section title match
        result = await self.db.execute(
            select(DocumentSection)
            .where(DocumentSection.section_title.ilike(f'%{reference}%'))
            .limit(1)
        )
        section = result.scalar_one_or_none()
        if section:
            return section
        
        # Try content match for code references
        result = await self.db.execute(
            select(DocumentSection)
            .where(DocumentSection.content.ilike(f'%{reference}%'))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_dependencies(
        self,
        section_id: UUID,
        direction: str = "both"
    ) -> dict[str, list[dict]]:
        """Get dependencies for a section.
        
        Args:
            section_id: The section to get dependencies for
            direction: "incoming" (sections that reference this one),
                      "outgoing" (sections this one references),
                      or "both"
        
        Returns:
            Dict with "incoming" and/or "outgoing" lists of dependencies
        """
        result = {"incoming": [], "outgoing": []}
        
        if direction in ("outgoing", "both"):
            # Sections this one references
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
                    "section_title": dep.target_section.section_title if dep.target_section else None,
                    "dependency_type": dep.dependency_type
                })
        
        if direction in ("incoming", "both"):
            # Sections that reference this one
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
                    "section_title": dep.source_section.section_title if dep.source_section else None,
                    "dependency_type": dep.dependency_type
                })
        
        return result

    async def build_dependency_graph(self, document_id: UUID | None = None) -> dict:
        """Build a full dependency graph for visualization.
        
        Returns:
            Dict with "nodes" (sections) and "edges" (dependencies)
        """
        # Get all sections
        query = select(DocumentSection).options(selectinload(DocumentSection.document))
        if document_id:
            query = query.where(DocumentSection.document_id == document_id)
        
        sections_result = await self.db.execute(query)
        sections = sections_result.scalars().all()
        
        nodes = [
            {
                "id": str(s.id),
                "title": s.section_title,
                "file_path": s.document.file_path if s.document else None
            }
            for s in sections
        ]
        
        # Get all dependencies
        section_ids = [s.id for s in sections]
        deps_result = await self.db.execute(
            select(SectionDependency).where(
                or_(
                    SectionDependency.source_section_id.in_(section_ids),
                    SectionDependency.target_section_id.in_(section_ids)
                )
            )
        )
        
        edges = [
            {
                "source": str(d.source_section_id),
                "target": str(d.target_section_id),
                "type": d.dependency_type
            }
            for d in deps_result.scalars()
        ]
        
        return {"nodes": nodes, "edges": edges}

    async def rebuild_all_dependencies(self) -> int:
        """Rebuild dependency graph for all sections. Returns count of dependencies created."""
        # Clear existing
        await self.db.execute(
            SectionDependency.__table__.delete()
        )
        
        # Get all sections
        result = await self.db.execute(
            select(DocumentSection).options(selectinload(DocumentSection.document))
        )
        sections = result.scalars().all()
        
        total = 0
        for section in sections:
            deps = await self.parse_and_store_dependencies(section)
            total += len(deps)
        
        await self.db.commit()
        logger.info(f"Rebuilt dependency graph: {total} dependencies")
        return total
