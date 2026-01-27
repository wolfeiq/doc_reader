"""
Query Orchestrator - AI Agent for Documentation Analysis
=========================================================

This module implements the core AI agent that processes documentation update
queries. It uses OpenAI's function calling (tools) to enable the AI to search,
analyze, and propose edits to documentation.

Agent Architecture:
-------------------
The orchestrator implements a ReAct-style agent loop:
1. User submits a query ("Update API authentication docs")
2. AI receives the query and available tools
3. AI decides which tool to call (search, analyze, propose_edit)
4. Tool executes and returns results
5. AI decides next action based on results
6. Loop continues until AI has enough info to stop (max 15 iterations)
7. All proposed edits are saved as EditSuggestion records

Available Tools:
----------------
- search_documentation: Semantic search across all docs
- search_by_file_path: Search within a specific file
- analyze_section: Deep analysis of a section's content
- propose_edit: Create an edit suggestion

Why Function Calling vs Fine-Tuning?
------------------------------------
Function calling is preferred because:
1. No training data needed
2. Works with base models (gpt-4o)
3. Flexible - add new tools easily
4. Transparent - we see what tools are called

Production Considerations:
--------------------------
- Add token budget tracking (prevent runaway costs)
- Implement streaming for tool results to UI
- Add human-in-the-loop for high-impact edits
- Consider caching repeated searches
- Add safety checks (don't edit critical sections)
- Implement rollback capability for bad edits
- Monitor and log all AI decisions for auditing
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.ai.tool_executor import AgentState, ToolExecutor
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools import TOOLS
from app.config import settings
from app.models.query import Query, QueryStatus
from app.services.event_service import EventEmitter
from app.schemas.tool_schemas import ProcessResult

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessage

logger = logging.getLogger(__name__)

# Safety limit to prevent infinite loops (API costs)
MAX_ITERATIONS = 15
DEFAULT_CONFIDENCE = 0.5

MessageDict = dict[str, Any]


class QueryOrchestrator:
    """
    Orchestrates AI-powered documentation analysis.

    The orchestrator manages the conversation between the user's query
    and the AI model, coordinating tool calls and accumulating results.

    Flow:
    1. Initialize with database session and event emitter
    2. Call process() with query details
    3. AI enters tool-calling loop
    4. Events are emitted for frontend progress display
    5. Final suggestions are committed to database

    Attributes:
        db: Database session for persisting results
        emitter: Event emitter for real-time progress updates
        openai: OpenAI client for API calls
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

        state = AgentState(query_id=query_id, query_text=query_text)
        tool_executor = ToolExecutor(self.db, state, self.emitter)


        result = await self.db.execute(select(Query).where(Query.id == query_id))
        query = result.scalar_one_or_none()

        if not query:
            await self.emitter.error("Query not found")
            return ProcessResult(
                query_id=str(query_id),
                status="failed",
                error="Query not found",
            )

        query.status = QueryStatus.PROCESSING
        query.status_message = "Starting analysis..."
        await self.db.commit()

        await self.emitter.status("processing", "Starting analysis...")

        try:
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

                if not message.tool_calls:
                    await self.emitter.status("finalizing", "Completing analysis...")
                    break

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    await self.emitter.tool_call(tool_name, tool_args)

                    tool_result = await tool_executor.execute(tool_name, tool_args)

                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result.model_dump())
                    })

            await self.db.commit()
            query.status = QueryStatus.COMPLETED
            query.status_message = f"Generated {len(state.proposed_edits)} suggestions"
            query.completed_at = datetime.utcnow()
            await self.db.commit()
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
    return message.model_dump()