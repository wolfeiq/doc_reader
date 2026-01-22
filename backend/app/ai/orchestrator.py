"""AI Orchestrator with OpenAI function calling for documentation updates."""

import json
import logging
from datetime import datetime
from typing import AsyncGenerator
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.document import Document, DocumentSection
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.ai.tools import TOOLS
from app.ai.prompts import SYSTEM_PROMPT
from app.services.search_service import SearchService
from app.services.dependency_service import DependencyService

logger = logging.getLogger(__name__)


class AgentState:
    """Track agent state during query processing."""
    
    def __init__(self, query_id: UUID, query_text: str):
        self.query_id = query_id
        self.query_text = query_text
        self.searched_queries: list[str] = []
        self.analyzed_sections: set[str] = set()
        self.proposed_edits: list[dict] = []
        self.messages: list[dict] = []


async def execute_tool(
    tool_name: str,
    tool_args: dict,
    db: AsyncSession,
    state: AgentState
) -> dict:
    """Execute a tool and return the result."""
    
    search_service = SearchService()
    dependency_service = DependencyService(db)
    
    logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
    
    if tool_name == "semantic_search":
        query = tool_args["query"]
        n_results = tool_args.get("n_results", 10)
        file_filter = tool_args.get("file_path_filter")
        
        state.searched_queries.append(query)
        results = await search_service.search(
            query=query,
            n_results=n_results,
            file_path_filter=file_filter
        )
        
        return {
            "results": results,
            "count": len(results),
            "query": query
        }
    
    elif tool_name == "get_section_content":
        section_id = tool_args["section_id"]
        
        result = await db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == UUID(section_id))
        )
        section = result.scalar_one_or_none()
        
        if not section:
            return {"error": f"Section {section_id} not found"}
        
        state.analyzed_sections.add(section_id)
        
        return {
            "section_id": section_id,
            "section_title": section.section_title,
            "content": section.content,
            "file_path": section.document.file_path if section.document else None,
            "order": section.order
        }
    
    elif tool_name == "find_dependencies":
        section_id = tool_args["section_id"]
        direction = tool_args.get("direction", "both")
        
        deps = await dependency_service.get_dependencies(
            section_id=UUID(section_id),
            direction=direction
        )
        
        return {
            "section_id": section_id,
            "dependencies": deps
        }
    
    elif tool_name == "propose_edit":
        section_id = tool_args["section_id"]
        suggested_text = tool_args["suggested_text"]
        reasoning = tool_args["reasoning"]
        confidence = tool_args["confidence"]
        
        # Get original content
        result = await db.execute(
            select(DocumentSection)
            .options(selectinload(DocumentSection.document))
            .where(DocumentSection.id == UUID(section_id))
        )
        section = result.scalar_one_or_none()
        
        if not section:
            return {"error": f"Section {section_id} not found"}
        
        # Create suggestion in DB
        suggestion = EditSuggestion(
            query_id=state.query_id,
            section_id=UUID(section_id),
            original_text=section.content,
            suggested_text=suggested_text,
            reasoning=reasoning,
            confidence=confidence,
            status=SuggestionStatus.PENDING
        )
        db.add(suggestion)
        await db.flush()
        
        state.proposed_edits.append({
            "suggestion_id": str(suggestion.id),
            "section_id": section_id,
            "section_title": section.section_title,
            "file_path": section.document.file_path if section.document else None,
            "confidence": confidence
        })
        
        return {
            "success": True,
            "suggestion_id": str(suggestion.id),
            "section_title": section.section_title,
            "file_path": section.document.file_path if section.document else None
        }
    
    elif tool_name == "get_document_structure":
        document_id = tool_args["document_id"]
        
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.sections))
            .where(Document.id == UUID(document_id))
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            return {"error": f"Document {document_id} not found"}
        
        return {
            "document_id": document_id,
            "file_path": doc.file_path,
            "title": doc.title,
            "sections": [
                {
                    "section_id": str(s.id),
                    "title": s.section_title,
                    "order": s.order
                }
                for s in sorted(doc.sections, key=lambda x: x.order)
            ]
        }
    
    elif tool_name == "search_by_file_path":
        path_pattern = tool_args["path_pattern"]
        results = await search_service.search_by_file_path(path_pattern)
        return {
            "results": results,
            "count": len(results),
            "pattern": path_pattern
        }
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}


async def process_query(
    query_id: UUID,
    query_text: str,
    db: AsyncSession
) -> AsyncGenerator[dict, None]:
    """Process a query using the AI agent with tool calling.
    
    Yields SSE events as processing progresses.
    """
    
    # Initialize
    openai = AsyncOpenAI(api_key=settings.openai_api_key)
    state = AgentState(query_id, query_text)
    
    # Update query status
    result = await db.execute(select(Query).where(Query.id == query_id))
    query = result.scalar_one_or_none()
    if not query:
        yield {"event": "error", "data": {"error": "Query not found"}}
        return
    
    query.status = QueryStatus.PROCESSING
    query.status_message = "Starting analysis..."
    await db.commit()
    
    yield {"event": "status", "data": {"status": "processing", "message": "Starting analysis..."}}
    
    try:
        # Initial message
        state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"User request: {query_text}\n\nPlease analyze the documentation and propose necessary updates."}
        ]
        
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Call OpenAI with tools
            response = await openai.chat.completions.create(
                model=settings.openai_model,
                messages=state.messages,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            state.messages.append(message.model_dump())
            
            # Check if done (no tool calls)
            if not message.tool_calls:
                yield {"event": "status", "data": {"status": "finalizing", "message": "Completing analysis..."}}
                break
            
            # Execute tool calls
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                yield {
                    "event": "tool_call",
                    "data": {
                        "tool": tool_name,
                        "args": tool_args
                    }
                }
                
                # Execute tool
                tool_result = await execute_tool(tool_name, tool_args, db, state)
                
                # Add tool result to messages
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })
                
                # Yield events for specific tools
                if tool_name == "semantic_search":
                    yield {
                        "event": "search_complete",
                        "data": {
                            "query": tool_args["query"],
                            "results_count": tool_result.get("count", 0)
                        }
                    }
                
                elif tool_name == "propose_edit" and tool_result.get("success"):
                    yield {
                        "event": "suggestion",
                        "data": {
                            "suggestion_id": tool_result["suggestion_id"],
                            "section_title": tool_result.get("section_title"),
                            "file_path": tool_result.get("file_path"),
                            "confidence": tool_args["confidence"]
                        }
                    }
        
        # Finalize
        await db.commit()
        
        query.status = QueryStatus.COMPLETED
        query.status_message = f"Generated {len(state.proposed_edits)} suggestions"
        query.completed_at = datetime.utcnow()
        await db.commit()
        
        yield {
            "event": "completed",
            "data": {
                "query_id": str(query_id),
                "total_suggestions": len(state.proposed_edits),
                "sections_analyzed": len(state.analyzed_sections),
                "searches_performed": len(state.searched_queries)
            }
        }
    
    except Exception as e:
        logger.error(f"Error processing query {query_id}: {e}", exc_info=True)
        
        query.status = QueryStatus.FAILED
        query.error_message = str(e)
        await db.commit()
        
        yield {"event": "error", "data": {"error": str(e)}}
