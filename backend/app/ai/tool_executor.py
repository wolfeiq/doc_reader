from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools import TOOLS
from app.schemas.tool_schemas import (
    validate_tool_args,
    SemanticSearchArgs,
    GetSectionContentArgs,
    FindDependenciesArgs,
    ProposeEditArgs,
    GetDocumentStructureArgs,
    SearchByFilePathArgs,
)
from app.config import settings
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.services.dependency_service import DependencyService
from app.services.search_service import SearchService
from app.services.event_service import EventEmitter
from app.schemas.tool_schemas import AgentStats, ToolError, ToolResult, ProposeEditResult, SectionResult
from app.schemas.tool_schemas import FilePathSearchResult, DocumentStructureResult, DocumentStructureSection, DependencyResult, SearchResult, DependencyInfo, SearchResultItem


logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15
DEFAULT_CONFIDENCE = 0.5

MessageDict = dict[str, str | list[dict[str, Any]]]
ToolArgs = SemanticSearchArgs | GetSectionContentArgs | FindDependenciesArgs | ProposeEditArgs | GetDocumentStructureArgs | SearchByFilePathArgs
ToolHandler = Callable[[ToolArgs], Awaitable[ToolResult]]

@dataclass
class AgentState:

    query_id: UUID
    query_text: str
    searched_queries: list[str] = field(default_factory=list)
    analyzed_sections: set[str] = field(default_factory=set)
    proposed_edits: list[ProposeEditResult] = field(default_factory=list)
    messages: list[MessageDict] = field(default_factory=list)

    @property
    def stats(self) -> AgentStats:
        return AgentStats(
            searches_performed=len(self.searched_queries),
            sections_analyzed=len(self.analyzed_sections),
            suggestions_created=len(self.proposed_edits),
        )


class ToolExecutor:

    def __init__(
        self,
        db: AsyncSession,
        state: AgentState,
        emitter: EventEmitter,
    ) -> None:
        self.db = db
        self.state = state
        self.emitter = emitter
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

    def _to_uuid(self, value: str | UUID) -> UUID:
        return value if isinstance(value, UUID) else UUID(value)

    async def execute(self, tool_name: str, tool_args: dict[str, Any]) -> ToolResult:
        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Tool args: {tool_args}")

        try:
            validated_args = validate_tool_args(tool_name, tool_args)
        except ValueError as e:
            logger.error(f"Invalid tool arguments: {e}")
            return ToolError(error=f"Validation error: {str(e)}")

        handlers: dict[str, ToolHandler] = {
            "semantic_search": self._handle_semantic_search,
            "get_section_content": self._handle_get_section,
            "find_dependencies": self._handle_find_dependencies,
            "propose_edit": self._handle_propose_edit,
            "get_document_structure": self._handle_get_document_structure,
            "search_by_file_path": self._handle_search_by_file_path,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return ToolError(error=f"Unknown tool: {tool_name}")

        try:
            result = await handler(validated_args)
            await self._emit_tool_events(tool_name, tool_args, result)
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return ToolError(error=str(e))

    async def _emit_tool_events(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        result: ToolResult,
    ) -> None:
        if tool_name == "semantic_search" and isinstance(result, SearchResult):
            await self.emitter.search_complete(
                sections_found=result.count,
                message=f"Found {result.count} relevant sections",
            )
        elif tool_name == "propose_edit" and isinstance(result, ProposeEditResult):
            if result.success and result.suggestion_id:
                await self.emitter.suggestion(
                    suggestion_id=result.suggestion_id,
                    document_id=result.document_id or "",
                    section_title=result.section_title,
                    file_path=result.file_path or "",
                    confidence=result.confidence,
                    preview=tool_args.get("suggested_text", "")[:200],
                )

    async def _handle_semantic_search(self, args: ToolArgs) -> SearchResult:
        assert isinstance(args, SemanticSearchArgs)
        query = args.query
        n_results = min(args.n_results, 20)
        file_filter = args.file_path_filter

        self.state.searched_queries.append(query)

        raw_results = await self.search_service.search(
            query=query,
            n_results=n_results,
            file_path_filter=file_filter,
        )

        results: list[SearchResultItem] = []
        for r in raw_results:
            metadata = r.get("metadata", {})
            content = r.get("content")
            results.append(SearchResultItem(
                section_id=r.get("section_id", ""),
                document_id=metadata.get("document_id"),
                section_title=metadata.get("section_title"),
                file_path=metadata.get("file_path"),
                content_preview=content[:200] if content else None,
                score=r.get("score", 0.0),
            ))

        return SearchResult(
            results=results,
            count=len(results),
            query=query,
        )

    async def _handle_get_section(self, args: ToolArgs) -> SectionResult:
        assert isinstance(args, GetSectionContentArgs)
        section_id = args.section_id

        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == section_id)
        )
        section = result.scalar_one_or_none()

        if not section:
            return SectionResult(error=f"Section {section_id} not found")

        self.state.analyzed_sections.add(str(section_id))

        return SectionResult(
            section_id=str(section_id),
            section_title=section.section_title,
            content=section.content,
            file_path=section.document.file_path if section.document else None,
            order=section.order,
        )

    async def _handle_find_dependencies(self, args: ToolArgs) -> DependencyResult:
        assert isinstance(args, FindDependenciesArgs)
        section_id = args.section_id
        direction = args.direction

        deps = await self.dependency_service.get_dependencies(
            section_id=section_id,
            direction=direction,
        )

        all_deps: list[DependencyInfo] = []
        if direction in ("incoming", "both"):
            for d in deps.get("incoming", []):
                all_deps.append(DependencyInfo(
                    dependency_id=d["dependency_id"] or "",
                    section_id=d["section_id"] or "",
                    section_title=d.get("section_title"),
                    dependency_type=d["dependency_type"] or "",
                ))
        if direction in ("outgoing", "both"):
            for d in deps.get("outgoing", []):
                all_deps.append(DependencyInfo(
                    dependency_id=d["dependency_id"] or "",
                    section_id=d["section_id"] or "",
                    section_title=d.get("section_title"),
                    dependency_type=d["dependency_type"] or "",
                ))

        return DependencyResult(
            section_id=str(section_id),
            dependencies=all_deps,
        )

    async def _handle_propose_edit(self, args: ToolArgs) -> ProposeEditResult:
        assert isinstance(args, ProposeEditArgs)
        section_id = args.section_id
        suggested_text = args.suggested_text
        reasoning = args.reasoning
        confidence = max(0.0, min(1.0, args.confidence))

        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == section_id)
        )
        section = result.scalar_one_or_none()

        if not section:
            return ProposeEditResult(error=f"Section {section_id} not found")

        if section.document:
            logger.info(f"Document id: {section.document.id}")

        suggestion = EditSuggestion(
            query_id=self.state.query_id,
            section_id=section_id,
            document_id=section.document_id,
            original_text=section.content,
            suggested_text=suggested_text,
            reasoning=reasoning,
            confidence=confidence,
            status=SuggestionStatus.PENDING,
        )
        self.db.add(suggestion)
        await self.db.flush()
        await self.db.refresh(suggestion) 

        edit_info = ProposeEditResult(
            success=True,
            suggestion_id=str(suggestion.id),
            document_id=str(suggestion.document_id) if suggestion.document_id else None,
            section_id=str(section_id),
            section_title=section.section_title,
            file_path=section.document.file_path if section.document else None,
            confidence=confidence,
        )
        self.state.proposed_edits.append(edit_info)

        return edit_info

    async def _handle_get_document_structure(
        self, args: ToolArgs
    ) -> DocumentStructureResult:
        assert isinstance(args, GetDocumentStructureArgs)
        document_id = args.document_id

        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()

        if not doc:
            return DocumentStructureResult(error=f"Document {document_id} not found")

        sections: list[DocumentStructureSection] = [
            DocumentStructureSection(
                section_id=str(s.id),
                title=s.section_title,
                order=s.order,
            )
            for s in sorted(doc.sections, key=lambda x: x.order)
        ]

        return DocumentStructureResult(
            document_id=str(document_id),
            file_path=doc.file_path,
            title=doc.title,
            sections=sections,
        )

    async def _handle_search_by_file_path(self, args: ToolArgs) -> FilePathSearchResult:
        assert isinstance(args, SearchByFilePathArgs)
        path_pattern = args.path_pattern

        raw_results = await self.search_service.search_by_file_path(
            path_pattern=path_pattern,
            n_results=20,
        )

        results: list[SearchResultItem] = []
        for r in raw_results:
            metadata = r.get("metadata", {})
            content = r.get("content")
            results.append(SearchResultItem(
                section_id=r.get("section_id", ""),
                document_id=metadata.get("document_id"),
                section_title=metadata.get("section_title"),
                file_path=metadata.get("file_path"),
                content_preview=content[:200] if content else None,
                score=r.get("score", 0.0),
            ))

        return FilePathSearchResult(
            results=results,
            count=len(results),
            pattern=path_pattern,
        )