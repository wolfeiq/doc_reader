"""
Dependency Service - Section Cross-Reference Graph
===================================================

This service analyzes documentation content to find and track
relationships between sections. When one section references another,
we create a "dependency" edge in the graph.

Why Track Dependencies?
-----------------------
1. Impact Analysis - When editing a section, know what else might break
2. Suggested Edits - If section A changes, suggest updating section B
3. Navigation - Help users explore related content
4. Consistency - Detect outdated cross-references

Reference Types Detected:
-------------------------
1. Markdown Links: [link text](../path/file.md#anchor)
   - Internal file links with optional anchors
   - Relative paths resolved against current file

2. Explicit References: "see the 'Authentication' section"
   - Natural language references to section titles
   - Common patterns: "refer to", "described in", "explained in"

3. Code References: `module.ClassName.method`
   - Dotted identifiers in code blocks
   - Links sections that document the same code

Resolution Strategy:
--------------------
References are resolved in order of specificity:
1. Exact file path match
2. File path with anchor → section title
3. Section title exact match
4. Section title fuzzy match
5. Content search for code references

Production Considerations:
--------------------------
- Dependency graph is rebuilt on document update
- Consider caching for frequently queried dependency paths
- Add graph visualization endpoint for debugging
- Monitor false positive rate in reference detection
"""

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
    """
    Service for building and querying the section dependency graph.

    Parses documentation content to find cross-references and stores
    them as edges in a directed graph (source → target).

    Usage:
        async with get_db() as db:
            service = DependencyService(db)
            # Build dependencies for a section
            deps = await service.parse_and_store_dependencies(section)
            # Query dependencies
            graph = await service.build_dependency_graph(document_id)
    """

    # Regex: [link text](url) - captures link text and URL
    MARKDOWN_LINK_PATTERN: re.Pattern[str] = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    # Regex: Natural language references like 'see "Authentication"'
    EXPLICIT_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
        r'(?:see|refer to|check|read|described in|explained in)\s+(?:the\s+)?'
        r'["\']([^"\']{3,})["\'](?:\s+section)?',
        re.IGNORECASE
    )

    # Regex: Dotted code identifiers like `module.Class.method`
    CODE_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
        r'`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*){1,})`'
    )

    # Common words to ignore in code reference detection (too generic)
    COMMON_CODE_WORDS: set[str] = {
        'id', 'name', 'type', 'value', 'data', 'item', 'user', 'result',
        'error', 'status', 'code', 'message', 'text', 'true', 'false',
        'null', 'none', 'self', 'this', 'var', 'let', 'const'
    }

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def parse_and_store_dependencies(
        self,
        section: DocumentSection
    ) -> Sequence[SectionDependency]:
        """
        Extract references from section content and store as dependencies.

        Scans the section's markdown content for cross-references,
        resolves them to actual sections, and creates dependency edges.

        Process:
        1. Extract all potential references (links, explicit, code)
        2. For each reference, try to resolve to a section
        3. If resolved and not self-reference, create dependency
        4. Skip duplicates (same source→target already exists)

        Args:
            section: The DocumentSection to analyze

        Returns:
            List of newly created SectionDependency objects

        Note:
            Only creates new dependencies - doesn't delete stale ones.
            Call rebuild_all_dependencies() for full refresh.
        """
        dependencies: list[SectionDependency] = []

        # Ensure document relationship is loaded
        if not section.document:
            await self.db.refresh(section, ["document"])

        # Extract all reference patterns from content
        references = self._extract_references(
            section.content,
            section.document.file_path if section.document else ""
        )

        # Try to resolve each reference to an actual section
        for ref_type, ref_value, anchor in references:
            target_section = await self._resolve_reference(
                ref_value,
                anchor,
                section.document_id,
                section.document.file_path if section.document else ""
            )

            # Create dependency if target found and not self-reference
            if target_section and target_section.id != section.id:
                # Check if this dependency already exists
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
                        dependency_type=ref_type  # 'link', 'reference', or 'code'
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
        """
        Extract all potential cross-references from markdown content.

        Scans content for three types of references:
        1. Markdown links: [text](path.md#anchor)
        2. Explicit references: 'see "Section Name"'
        3. Code references: `module.Class.method`

        Args:
            content: The markdown content to scan
            current_file_path: Path of the containing document (for relative resolution)

        Returns:
            List of tuples: (ref_type, ref_value, anchor)
            - ref_type: 'link', 'anchor', 'reference', or 'code'
            - ref_value: The reference target (path, title, or code identifier)
            - anchor: Optional anchor/fragment (e.g., section title from #anchor)

        Note:
            External URLs (http://, https://) are ignored.
            Duplicates are deduplicated via `seen` set.
        """
        references: list[tuple[str, str, str | None]] = []
        seen = set()  # Avoid duplicate references

        # 1. Extract markdown links: [text](url)
        for match in self.MARKDOWN_LINK_PATTERN.finditer(content):
            link_text, link_url = match.groups()

            # Skip external URLs
            if link_url.startswith(('http://', 'https://', 'mailto:')):
                continue

            # Handle same-page anchors: #section-name
            if link_url.startswith('#'):
                anchor = link_url[1:]  # Remove # prefix
                ref_key = f"anchor:{anchor}"
                if ref_key not in seen:
                    references.append(('anchor', current_file_path, anchor))
                    seen.add(ref_key)
                continue

            # Handle file links with optional anchors: path/file.md#anchor
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

        # 2. Extract explicit references: 'see "Authentication"'
        for match in self.EXPLICIT_REFERENCE_PATTERN.finditer(content):
            reference_text = match.group(1).strip()

            # Filter out very short or very long references (likely false positives)
            if len(reference_text) < 3 or len(reference_text) > 100:
                continue

            ref_key = f"reference:{reference_text}"
            if ref_key not in seen:
                references.append(('reference', reference_text, None))
                seen.add(ref_key)

        # 3. Extract code references: `module.Class.method`
        for match in self.CODE_REFERENCE_PATTERN.finditer(content):
            code_ref = match.group(1)

            # Skip common generic words
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
        """
        Get dependencies for a specific section.

        Returns both incoming (sections that reference this one) and
        outgoing (sections this one references) dependencies.

        Args:
            section_id: UUID of the section to query
            direction: Which dependencies to return:
                - "outgoing": Sections THIS section references
                - "incoming": Sections that reference THIS section
                - "both": All dependencies (default)

        Returns:
            Dict with "incoming" and "outgoing" lists, each containing:
            - dependency_id: UUID of the dependency edge
            - section_id: UUID of the related section
            - section_title: Title of the related section
            - dependency_type: How they're related ('link', 'reference', 'code')

        Use Cases:
            - Show "Related sections" sidebar in UI
            - Impact analysis: "If I change this, what else might break?"
            - Navigation: "See also" links
        """
        result: dict[str, list[dict[str, str | None]]] = {
            "incoming": [],
            "outgoing": []
        }

        # Outgoing: sections this section references
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

        # Incoming: sections that reference this section
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
        """
        Build a graph representation of section dependencies.

        Returns nodes (sections) and edges (dependencies) suitable
        for visualization or graph algorithms.

        Args:
            document_id: Optional - limit to sections in one document.
                         If None, returns full cross-document graph.

        Returns:
            DependencyGraphResponse with:
            - nodes: List of sections with id, title, file_path
            - edges: List of dependencies with source_id, target_id, type

        Use Cases:
            - Graph visualization (D3.js, Mermaid)
            - Finding isolated sections (no dependencies)
            - Detecting circular dependencies
            - Computing impact radius (N hops from changed section)
        """
        # Get all sections (optionally filtered by document)
        query = select(DocumentSection).options(
            selectinload(DocumentSection.document)
        )
        if document_id:
            query = query.where(DocumentSection.document_id == document_id)

        sections_result = await self.db.execute(query)
        sections = sections_result.scalars().all()

        # Build node list
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

        # Build edge list (dependencies involving these sections)
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
        """
        Delete all dependencies and rebuild from scratch.

        DESTRUCTIVE OPERATION - Clears the entire dependency graph
        and re-parses all section content to rebuild it.

        Use Cases:
            - After bulk document import
            - After changing reference detection patterns
            - Fixing corrupted dependency data
            - Schema migration

        Returns:
            Total number of dependencies created

        Note:
            This can be slow for large documentation sets.
            Consider running as background task for production.
        """
        # Clear all existing dependencies
        await self.db.execute(
            SectionDependency.__table__.delete()
        )

        # Load all sections with their documents
        result = await self.db.execute(
            select(DocumentSection).options(
                selectinload(DocumentSection.document)
            )
        )
        sections = result.scalars().all()

        # Re-parse each section for references
        total = 0
        for section in sections:
            deps = await self.parse_and_store_dependencies(section)
            total += len(deps)

        await self.db.commit()
        logger.info(f"Rebuilt dependency graph: {total} dependencies")
        return total