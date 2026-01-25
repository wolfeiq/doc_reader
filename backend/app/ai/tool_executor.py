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
from backend.app.schemas.tool_schemas import validate_tool_args
from app.config import settings
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.services.dependency_service import DependencyService
from app.services.search_service import SearchService
from app.services.event_service import EventEmitter
from backend.app.schemas.tool_schemas import AgentStats, ToolError, ToolResult, ProposeEditResult, SectionResult
from backend.app.schemas.tool_schemas import FilePathSearchResult, DocumentStructureResult, DocumentStructureSection, DependencyResult, SearchResult


logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15
DEFAULT_CONFIDENCE = 0.5

MessageDict = dict[str, Any]
ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]

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
            result = await handler(validated_args.model_dump())
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
        if tool_name == "semantic_search" and "count" in result:
            search_result = result  # type: SearchResult
            await self.emitter.search_complete(
                sections_found=search_result.get("count", 0),
                message=f"Found {search_result.get('count', 0)} relevant sections",
            )
        elif tool_name == "propose_edit" and result.get("success"):
            edit_result = result  # type: ProposeEditResult
            await self.emitter.suggestion(
                suggestion_id=edit_result["suggestion_id"],
                section_title=edit_result.get("section_title"),
                file_path=edit_result.get("file_path") or "",
                confidence=edit_result.get("confidence", DEFAULT_CONFIDENCE),
                preview=tool_args.get("suggested_text", "")[:200],
            )

    async def _handle_semantic_search(self, args: dict[str, Any]) -> SearchResult:
        query: str = args["query"]
        n_results: int = min(args.get("n_results", 10), 20)
        file_filter: str | None = args.get("file_path_filter")

        self.state.searched_queries.append(query)

        results = await self.search_service.search(
            query=query,
            n_results=n_results,
            file_path_filter=file_filter,
        )

        return SearchResult(
            results=results,
            count=len(results),
            query=query,
        )

    async def _handle_get_section(self, args: dict[str, Any]) -> SectionResult:
        section_id_str: str = args["section_id"]

        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == UUID(section_id_str))
        )
        section = result.scalar_one_or_none()

        if not section:
            return SectionResult(error=f"Section {section_id_str} not found")

        self.state.analyzed_sections.add(section_id_str)

        return SectionResult(
            section_id=section_id_str,
            section_title=section.section_title,
            content=section.content,
            file_path=section.document.file_path if section.document else None,
            order=section.order,
        )

    async def _handle_find_dependencies(self, args: dict[str, Any]) -> DependencyResult:
        section_id_str: str = args["section_id"]
        direction: str = args.get("direction", "both")

        deps = await self.dependency_service.get_dependencies(
            section_id=UUID(section_id_str),
            direction=direction,
        )

        return DependencyResult(
            section_id=section_id_str,
            dependencies=deps,
        )

    async def _handle_propose_edit(self, args: dict[str, Any]) -> ProposeEditResult:
        section_id_str: str = args["section_id"]
        suggested_text: str = args["suggested_text"]
        reasoning: str = args["reasoning"]
        confidence: float = max(0.0, min(1.0, args.get("confidence", DEFAULT_CONFIDENCE)))

        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == UUID(section_id_str))
        )
        section = result.scalar_one_or_none()

        if not section:
            return ProposeEditResult(error=f"Section {section_id_str} not found")

        suggestion = EditSuggestion(
            query_id=self.state.query_id,
            section_id=UUID(section_id_str),
            original_text=section.content,
            suggested_text=suggested_text,
            reasoning=reasoning,
            confidence=confidence,
            status=SuggestionStatus.PENDING,
        )
        self.db.add(suggestion)
        await self.db.flush()

        edit_info = ProposeEditResult(
            success=True,
            suggestion_id=str(suggestion.id),
            section_id=section_id_str,
            section_title=section.section_title,
            file_path=section.document.file_path if section.document else None,
            confidence=confidence,
        )
        self.state.proposed_edits.append(edit_info)

        return edit_info

    async def _handle_get_document_structure(
        self, args: dict[str, Any]
    ) -> DocumentStructureResult:
        document_id_str: str = args["document_id"]

        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == UUID(document_id_str))
        )
        doc = result.scalar_one_or_none()

        if not doc:
            return DocumentStructureResult(error=f"Document {document_id_str} not found")

        sections: list[DocumentStructureSection] = [
            DocumentStructureSection(
                section_id=str(s.id),
                title=s.section_title,
                order=s.order,
            )
            for s in sorted(doc.sections, key=lambda x: x.order)
        ]

        return DocumentStructureResult(
            document_id=document_id_str,
            file_path=doc.file_path,
            title=doc.title,
            sections=sections,
        )

    async def _handle_search_by_file_path(self, args: dict[str, Any]) -> FilePathSearchResult:
        path_pattern: str = args["path_pattern"]

        results = await self.search_service.search_by_file_path(
            path_pattern=path_pattern,
            n_results=20,
        )

        return FilePathSearchResult(
            results=results,
            count=len(results),
            pattern=path_pattern,
        )

