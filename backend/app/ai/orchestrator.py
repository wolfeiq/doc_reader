from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncGenerator, Literal, Callable, Awaitable
from uuid import UUID

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageToolCall
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools import TOOLS, Tool
from app.ai.tool_schemas import (
    validate_tool_args,
    SearchResult,
    ToolErrorResponse,
)
from app.config import settings
from app.models.document_base import Document
from app.models.document import DocumentSection
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.services.dependency_service import DependencyService
from app.services.search_service import SearchService

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessage

logger = logging.getLogger(__name__)


MAX_ITERATIONS = 15
DEFAULT_CONFIDENCE = 0.5


MessageDict = dict[str, Any]
ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class AgentState:

    query_id: UUID
    query_text: str
    searched_queries: list[str] = field(default_factory=list)
    analyzed_sections: set[str] = field(default_factory=set)
    proposed_edits: list[dict[str, Any]] = field(default_factory=list)
    messages: list[MessageDict] = field(default_factory=list)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "searches_performed": len(self.searched_queries),
            "sections_analyzed": len(self.analyzed_sections),
            "suggestions_created": len(self.proposed_edits),
        }


class ToolExecutor:
    def __init__(self, db: AsyncSession, state: AgentState) -> None:
        self.db = db
        self.state = state
        self._search_service: SearchService | None = None
        self._dependency_service: DependencyService | None = None

    @property
    def search_service(self) -> SearchService:
        """Lazy-loaded search service instance."""
        if self._search_service is None:
            self._search_service = SearchService()
        return self._search_service

    @property
    def dependency_service(self) -> DependencyService:
        """Lazy-loaded dependency service instance."""
        if self._dependency_service is None:
            self._dependency_service = DependencyService(self.db)
        return self._dependency_service

    async def execute(
        self, 
        tool_name: str, 
        tool_args: dict[str, Any]
    ) -> dict[str, Any]:

        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Tool args: {tool_args}")
        try:
            validated_args = validate_tool_args(tool_name, tool_args)
        except ValueError as e:
            logger.error(f"Invalid tool arguments: {e}")
            return {"error": f"Validation error: {str(e)}"}

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
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return await handler(validated_args.model_dump())
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return {"error": str(e)}

    async def _handle_semantic_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args["query"]
        n_results = min(args.get("n_results", 10), 20)
        file_filter = args.get("file_path_filter")

        self.state.searched_queries.append(query)

        results = await self.search_service.search(
            query=query,
            n_results=n_results,
            file_path_filter=file_filter,
        )

        return {"results": results, "count": len(results), "query": query}

    async def _handle_get_section(self, args: dict[str, Any]) -> dict[str, Any]:
        section_id_str = args["section_id"]

        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == UUID(section_id_str))
        )
        section = result.scalar_one_or_none()

        if not section:
            return {"error": f"Section {section_id_str} not found"}

        self.state.analyzed_sections.add(section_id_str)

        return {
            "section_id": section_id_str,
            "section_title": section.section_title,
            "content": section.content,
            "file_path": section.document.file_path if section.document else None,
            "order": section.order,
        }

    async def _handle_find_dependencies(self, args: dict[str, Any]) -> dict[str, Any]:

        section_id_str = args["section_id"]
        direction = args.get("direction", "both")

        deps = await self.dependency_service.get_dependencies(
            section_id=UUID(section_id_str),
            direction=direction,  # type: ignore[arg-type]
        )

        return {"section_id": section_id_str, "dependencies": deps}

    async def _handle_propose_edit(self, args: dict[str, Any]) -> dict[str, Any]:
        section_id_str = args["section_id"]
        suggested_text = args["suggested_text"]
        reasoning = args["reasoning"]
        confidence = max(0.0, min(1.0, args.get("confidence", DEFAULT_CONFIDENCE)))

        result = await self.db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == UUID(section_id_str))
        )
        section = result.scalar_one_or_none()

        if not section:
            return {"error": f"Section {section_id_str} not found"}

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

        edit_info: dict[str, Any] = {
            "suggestion_id": str(suggestion.id),
            "section_id": section_id_str,
            "section_title": section.section_title,
            "file_path": section.document.file_path if section.document else None,
            "confidence": confidence,
        }
        self.state.proposed_edits.append(edit_info)

        return {"success": True, **edit_info}

    async def _handle_get_document_structure(
        self, 
        args: dict[str, Any]
    ) -> dict[str, Any]:
        document_id_str = args["document_id"]

        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == UUID(document_id_str))
        )
        doc = result.scalar_one_or_none()

        if not doc:
            return {"error": f"Document {document_id_str} not found"}

        return {
            "document_id": document_id_str,
            "file_path": doc.file_path,
            "title": doc.title,
            "sections": [
                {
                    "section_id": str(s.id),
                    "title": s.section_title,
                    "order": s.order
                }
                for s in sorted(doc.sections, key=lambda x: x.order)
            ],
        }

    async def _handle_search_by_file_path(self, args: dict[str, Any]) -> dict[str, Any]:

        path_pattern = args["path_pattern"]
        
        results = await self.search_service.search_by_file_path(
            path_pattern=path_pattern,
            n_results=20,
        )
        
        return {"results": results, "count": len(results), "pattern": path_pattern}


async def process_query(
    query_id: UUID,
    query_text: str,
    db: AsyncSession,
) -> AsyncGenerator[dict[str, Any], None]:

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    state = AgentState(query_id=query_id, query_text=query_text)
    tool_executor = ToolExecutor(db, state)
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()

    if not query:
        yield {"event": "error", "data": {"error": "Query not found"}}
        return

    query.status = QueryStatus.PROCESSING
    query.status_message = "Starting analysis..."
    await db.commit()

    yield _event("status", status="processing", message="Starting analysis...")

    try:
        state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Documentation update request: {query_text}\n\n"
                "Please analyze the documentation and propose necessary updates.",
            },
        ]

        for iteration in range(MAX_ITERATIONS):
            logger.debug(f"Iteration {iteration + 1}/{MAX_ITERATIONS}")
            response = await openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=state.messages,  # type: ignore[arg-type]
                tools=TOOLS,  # type: ignore[arg-type]
                tool_choice="auto",
            )

            message = response.choices[0].message
            state.messages.append(_message_to_dict(message))
            if not message.tool_calls:
                yield _event(
                    "status", 
                    status="finalizing", 
                    message="Completing analysis..."
                )
                break
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                yield _event("tool_call", tool=tool_name, args=tool_args)

                tool_result = await tool_executor.execute(tool_name, tool_args)

                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                })


                for event in _tool_events(tool_name, tool_args, tool_result):
                    yield event

        await db.commit()

        query.status = QueryStatus.COMPLETED
        query.status_message = f"Generated {len(state.proposed_edits)} suggestions"
        query.completed_at = datetime.utcnow()
        await db.commit()

        yield _event(
            "completed",
            query_id=str(query_id),
            **state.stats,
            total_suggestions=len(state.proposed_edits),
        )

    except Exception as e:
        logger.error(f"Error processing query {query_id}: {e}", exc_info=True)

        query.status = QueryStatus.FAILED
        query.error_message = str(e)
        await db.commit()

        yield _event("error", error=str(e))


def _event(event_type: str, **data: Any) -> dict[str, Any]:
    return {"event": event_type, "data": data}


def _message_to_dict(message: ChatCompletionMessage) -> MessageDict:
    return message.model_dump()


def _tool_events(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_result: dict[str, Any],
) -> list[dict[str, Any]]:

    events: list[dict[str, Any]] = []

    if tool_name == "semantic_search":
        events.append(
            _event(
                "search_complete",
                query=tool_args["query"],
                results_count=tool_result.get("count", 0),
            )
        )
    elif tool_name == "propose_edit" and tool_result.get("success"):
        events.append(
            _event(
                "suggestion",
                suggestion_id=tool_result["suggestion_id"],
                section_title=tool_result.get("section_title"),
                file_path=tool_result.get("file_path"),
                confidence=tool_args.get("confidence", DEFAULT_CONFIDENCE),
            )
        )

    return events