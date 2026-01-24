from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Awaitable, TypedDict
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools import TOOLS
from app.ai.tool_schemas import validate_tool_args
from app.config import settings
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.services.dependency_service import DependencyService
from app.services.search_service import SearchService
from app.services.event_service import EventEmitter
from app.ai.tool_schemas import AgentStats, ToolError, ToolResult, ProposeEditResult, ProcessResult, SectionResult
from app.ai.tool_schemas import FilePathSearchResult, DocumentStructureResult, DocumentStructureSection, DependencyResult, SearchResultItem, SearchResult

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessage

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15
DEFAULT_CONFIDENCE = 0.5

MessageDict = dict[str, Any]
ToolHandler = Callable[[dict[str, Any]], Awaitable[ToolResult]]

@dataclass
class AgentState:
    """Tracks the state of query processing."""

    query_id: UUID
    query_text: str
    searched_queries: list[str] = field(default_factory=list)
    analyzed_sections: set[str] = field(default_factory=set)
    proposed_edits: list[ProposeEditResult] = field(default_factory=list)
    messages: list[MessageDict] = field(default_factory=list)

    @property
    def stats(self) -> AgentStats:
        """Get current processing statistics."""
        return AgentStats(
            searches_performed=len(self.searched_queries),
            sections_analyzed=len(self.analyzed_sections),
            suggestions_created=len(self.proposed_edits),
        )


class ToolExecutor:
    """Executes AI tool calls against the database and services."""

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
        """Lazy-loaded search service."""
        if self._search_service is None:
            self._search_service = SearchService()
        return self._search_service

    @property
    def dependency_service(self) -> DependencyService:
        """Lazy-loaded dependency service."""
        if self._dependency_service is None:
            self._dependency_service = DependencyService(self.db)
        return self._dependency_service

    async def execute(self, tool_name: str, tool_args: dict[str, Any]) -> ToolResult:
        """Execute a tool call and return the result."""
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
        """Emit SSE events for tool completion."""
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
        """Handle semantic search tool call."""
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
        """Handle get section content tool call."""
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
        """Handle find dependencies tool call."""
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
        """Handle propose edit tool call."""
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
        """Handle get document structure tool call."""
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
        """Handle search by file path tool call."""
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



class QueryOrchestrator:
    """
    Orchestrates query processing using an agentic RAG approach.
    
    This class is transport-agnostic - it emits events through an EventEmitter
    which can be configured for direct streaming or Redis pub/sub.
    """

    def __init__(
        self,
        db: AsyncSession,
        emitter: EventEmitter,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        self.db = db
        self.emitter = emitter
        self.openai = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)

    async def process(self, query_id: UUID, query_text: str) -> ProcessResult:
        """
        Process a documentation update query.
        
        Args:
            query_id: The UUID of the query to process.
            query_text: The user's query text.
        
        Returns:
            ProcessResult with status and statistics.
        """
        state = AgentState(query_id=query_id, query_text=query_text)
        tool_executor = ToolExecutor(self.db, state, self.emitter)

        # Get and validate query
        result = await self.db.execute(select(Query).where(Query.id == query_id))
        query = result.scalar_one_or_none()

        if not query:
            await self.emitter.error("Query not found")
            return ProcessResult(
                query_id=str(query_id),
                status="failed",
                error="Query not found",
            )

        # Update status to processing
        query.status = QueryStatus.PROCESSING
        query.status_message = "Starting analysis..."
        await self.db.commit()

        await self.emitter.status("processing", "Starting analysis...")

        try:
            # Initialize conversation
            state.messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Documentation update request: {query_text}\n\n"
                        "Please analyze the documentation and propose necessary updates."
                    ),
                },
            ]

            # Agentic loop
            for iteration in range(MAX_ITERATIONS):
                logger.debug(f"Iteration {iteration + 1}/{MAX_ITERATIONS}")

                response = await self.openai.chat.completions.create(
                    model=settings.openai_model,
                    messages=state.messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )

                message = response.choices[0].message
                state.messages.append(_message_to_dict(message))

                # Check if done (no more tool calls)
                if not message.tool_calls:
                    await self.emitter.status("finalizing", "Completing analysis...")
                    break

                # Process tool calls
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    await self.emitter.tool_call(tool_name, tool_args)

                    tool_result = await tool_executor.execute(tool_name, tool_args)

                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    })

            # Commit any pending changes
            await self.db.commit()

            # Update query status
            query.status = QueryStatus.COMPLETED
            query.status_message = f"Generated {len(state.proposed_edits)} suggestions"
            query.completed_at = datetime.utcnow()
            await self.db.commit()

            # Emit completion event
            await self.emitter.completed(
                total_suggestions=len(state.proposed_edits),
            )

            stats = state.stats
            return ProcessResult(
                query_id=str(query_id),
                status="completed",
                searches_performed=stats["searches_performed"],
                sections_analyzed=stats["sections_analyzed"],
                suggestions_created=stats["suggestions_created"],
            )

        except Exception as e:
            logger.error(f"Error processing query {query_id}: {e}", exc_info=True)

            query.status = QueryStatus.FAILED
            query.error_message = str(e)
            await self.db.commit()

            await self.emitter.error(str(e))

            return ProcessResult(
                query_id=str(query_id),
                status="failed",
                error=str(e),
            )


def _message_to_dict(message: ChatCompletionMessage) -> MessageDict:
    """Convert OpenAI message to dictionary."""
    return message.model_dump()