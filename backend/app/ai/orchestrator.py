import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import UUID
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.ai.prompts import ANALYSIS_PROMPT, EDIT_SUGGESTION_PROMPT, SYSTEM_PROMPT
from app.config import settings
from app.models.document import DocumentSection
from app.models.query import Query, QueryStatus
from app.models.suggestion import EditSuggestion, SuggestionStatus
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": "Search the documentation for sections relevant to the query. Returns the most relevant sections based on semantic similarity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant documentation sections",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_edit",
            "description": "Propose a specific edit to a documentation section",
            "parameters": {
                "type": "object",
                "properties": {
                    "section_id": {
                        "type": "string",
                        "description": "The UUID of the section to edit",
                    },
                    "original_text": {
                        "type": "string",
                        "description": "The specific text that should be changed",
                    },
                    "suggested_text": {
                        "type": "string",
                        "description": "The new text to replace it with",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of why this change is needed",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score (0.0-1.0)",
                    },
                },
                "required": ["section_id", "original_text", "suggested_text", "reasoning", "confidence"],
            },
        },
    },
]


async def process_query(
    query_id: UUID,
    query_text: str,
    db: AsyncSession,
    search_service: SearchService,
) -> AsyncGenerator[dict, None]:

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    try:

        result = await db.execute(select(Query).where(Query.id == query_id))
        query = result.scalar_one_or_none()
        if not query:
            yield {"event": "error", "data": {"error": "Query not found"}}
            return
        
        query.status = QueryStatus.PROCESSING
        query.status_message = "Starting analysis..."
        await db.commit()
        
        yield {
            "event": "status",
            "data": {"status": "processing", "message": "Starting analysis..."},
        }
        

        query.status = QueryStatus.ANALYZING
        query.status_message = "Analyzing update request..."
        await db.commit()
        
        yield {
            "event": "status",
            "data": {"status": "analyzing", "message": "Analyzing update request..."},
        }
        

        analysis_response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": ANALYSIS_PROMPT.format(query=query_text)},
            ],
            temperature=0.3,
        )
        
        analysis = analysis_response.choices[0].message.content
        logger.info(f"Query analysis: {analysis}")
        
        yield {
            "event": "analysis",
            "data": {"analysis": analysis},
        }
        

        query.status = QueryStatus.SEARCHING
        query.status_message = "Searching documentation..."
        await db.commit()
        
        yield {
            "event": "status",
            "data": {"status": "searching", "message": "Searching documentation..."},
        }
        

        search_results = await search_service.search(query_text, n_results=15)

        keywords = [w for w in query_text.split() if len(w) > 3]
        for keyword in keywords[:3]:
            additional_results = await search_service.search(keyword, n_results=5)
            for r in additional_results:
                if r["section_id"] not in [s["section_id"] for s in search_results]:
                    search_results.append(r)
        
        yield {
            "event": "search_progress",
            "data": {
                "sections_found": len(search_results),
                "message": f"Found {len(search_results)} potentially relevant sections",
            },
        }
        

        query.status = QueryStatus.GENERATING
        query.status_message = "Generating suggestions..."
        await db.commit()
        
        yield {
            "event": "status",
            "data": {"status": "generating", "message": "Generating edit suggestions..."},
        }
        
        suggestions_created = 0
        
        for i, result in enumerate(search_results):
            section_id = result["section_id"]
            content = result["content"]
            metadata = result["metadata"]
            
            yield {
                "event": "progress",
                "data": {
                    "current": i + 1,
                    "total": len(search_results),
                    "section": metadata.get("section_title", "Unknown"),
                    "file": metadata.get("file_path", "Unknown"),
                },
            }
            

            section_result = await db.execute(
                select(DocumentSection)
                .options(selectinload(DocumentSection.document))
                .where(DocumentSection.id == section_id)
            )
            section = section_result.scalar_one_or_none()
            
            if not section:
                continue
            

            suggestion_response = await openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": EDIT_SUGGESTION_PROMPT.format(
                            query=query_text,
                            section_title=section.section_title or "Untitled",
                            file_path=section.document.file_path if section.document else "Unknown",
                            content=section.content,
                        ),
                    },
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            
            try:
                suggestion_data = json.loads(suggestion_response.choices[0].message.content)

                if suggestion_data.get("needs_update") is False:
                    logger.debug(f"Section {section_id} doesn't need update: {suggestion_data.get('reasoning')}")
                    continue

                confidence = suggestion_data.get("confidence", 0)
                if confidence < 0.3:
                    logger.debug(f"Skipping low-confidence suggestion for {section_id}: {confidence}")
                    continue

                suggestion = EditSuggestion(
                    query_id=query_id,
                    section_id=section_id,
                    original_text=suggestion_data.get("original_text", ""),
                    suggested_text=suggestion_data.get("suggested_text", ""),
                    reasoning=suggestion_data.get("reasoning", ""),
                    confidence=confidence,
                    status=SuggestionStatus.PENDING,
                )
                db.add(suggestion)
                await db.flush()
                
                suggestions_created += 1
                
                yield {
                    "event": "suggestion",
                    "data": {
                        "suggestion_id": str(suggestion.id),
                        "section_id": str(section_id),
                        "section_title": section.section_title,
                        "file_path": section.document.file_path if section.document else None,
                        "confidence": confidence,
                        "reasoning": suggestion_data.get("reasoning", ""),
                        "preview": suggestion_data.get("suggested_text", "")[:200],
                    },
                }
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse suggestion response: {e}")
                continue
        

        query.status = QueryStatus.COMPLETED
        query.status_message = f"Generated {suggestions_created} suggestions"
        query.completed_at = datetime.utcnow()
        await db.commit()
        
        yield {
            "event": "completed",
            "data": {
                "total_suggestions": suggestions_created,
                "query_id": str(query_id),
            },
        }
        
    except Exception as e:
        logger.error(f"Error processing query {query_id}: {e}", exc_info=True)

        result = await db.execute(select(Query).where(Query.id == query_id))
        query = result.scalar_one_or_none()
        if query:
            query.status = QueryStatus.FAILED
            query.error_message = str(e)
            await db.commit()
        
        yield {
            "event": "error",
            "data": {"error": str(e)},
        }