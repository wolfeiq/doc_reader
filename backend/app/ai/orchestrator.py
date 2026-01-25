from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.app.ai.tool_executor import AgentState, ToolExecutor
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.ai.prompts import SYSTEM_PROMPT
from app.ai.tools import TOOLS
from app.config import settings
from app.models.query import Query, QueryStatus
from app.services.event_service import EventEmitter
from backend.app.schemas.tool_schemas import ProcessResult

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessage

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 15
DEFAULT_CONFIDENCE = 0.5

MessageDict = dict[str, Any]


class QueryOrchestrator:

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
                        "content": json.dumps(tool_result),
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