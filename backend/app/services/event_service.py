"""
Event service for publishing and subscribing to query processing events.

Supports two modes:
1. Direct mode - yields events directly (for SSE without Celery)
2. Redis Stream mode - uses Redis Streams for reliable delivery (for Celery workers)

Note: We use Redis Streams instead of Pub/Sub because:
- Streams persist messages (no race condition if subscriber connects late)
- Streams support consumer groups for reliability
- Messages can be read from a specific point in time
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Protocol
from uuid import UUID

import redis.asyncio as aioredis
from redis.asyncio.client import Redis

from app.config import settings

logger = logging.getLogger(__name__)

# Stream settings
STREAM_MAX_LEN = 1000  # Max messages per stream
STREAM_TTL_SECONDS = 3600  # 1 hour TTL for streams


class EventType(str, Enum):
    """Query processing event types."""
    STATUS = "status"
    TOOL_CALL = "tool_call"
    SEARCH_COMPLETE = "search_complete"
    SUGGESTION = "suggestion"
    COMPLETED = "completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class QueryEvent:
    """Represents a query processing event."""
    event: EventType
    data: dict[str, Any]
    query_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event.value,
            "data": self.data,
            "query_id": self.query_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, data: str) -> QueryEvent:
        parsed = json.loads(data)
        return cls(
            event=EventType(parsed["event"]),
            data=parsed["data"],
            query_id=parsed["query_id"],
            timestamp=parsed.get("timestamp", datetime.utcnow().isoformat()),
        )


def _get_stream_name(query_id: str | UUID) -> str:
    """Get Redis stream name for a query."""
    return f"query_stream:{query_id}"


class EventPublisher(Protocol):
    """Protocol for event publishers."""

    async def publish(self, event: QueryEvent) -> None:
        """Publish an event."""
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...


class DirectEventPublisher:
    """
    Publisher that collects events in memory.
    Used when processing directly in FastAPI without Celery.
    """

    def __init__(self, query_id: str | UUID) -> None:
        self.query_id = str(query_id)
        self._events: asyncio.Queue[QueryEvent] = asyncio.Queue()
        self._closed = False

    async def publish(self, event: QueryEvent) -> None:
        if not self._closed:
            await self._events.put(event)

    async def close(self) -> None:
        self._closed = True
        # Signal end of stream
        await self._events.put(
            QueryEvent(
                event=EventType.COMPLETED,
                data={"_stream_end": True},
                query_id=self.query_id,
            )
        )

    async def events(self) -> AsyncGenerator[QueryEvent, None]:
        """Iterate over published events."""
        while True:
            event = await self._events.get()
            if event.data.get("_stream_end"):
                break
            yield event


class RedisEventPublisher:
    """
    Publisher that sends events to Redis Streams.
    Used by Celery workers.
    
    Uses Redis Streams instead of Pub/Sub for reliable delivery.
    This version uses synchronous Redis for Celery compatibility.
    """

    def __init__(self, query_id: str | UUID) -> None:
        self.query_id = str(query_id)
        self.stream_name = _get_stream_name(query_id)
        self._sync_redis: Any | None = None  # Sync redis client
        logger.info(f"RedisEventPublisher created for stream: {self.stream_name}")

    def _ensure_sync_connected(self) -> Any:
        """Get synchronous Redis connection for Celery workers."""
        if self._sync_redis is None:
            import redis as sync_redis
            logger.info(f"Connecting to Redis: {settings.redis_url}")
            self._sync_redis = sync_redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            # Test connection
            self._sync_redis.ping()
            logger.info("Redis connection established")
        return self._sync_redis

    def publish_sync(self, event: QueryEvent) -> None:
        """Publish event synchronously (for Celery workers)."""
        try:
            redis = self._ensure_sync_connected()
            event_json = event.to_json()
            logger.info(f"Publishing to {self.stream_name}: {event.event.value}")
            message_id = redis.xadd(
                self.stream_name,
                {"event": event_json},
                maxlen=STREAM_MAX_LEN,
            )
            logger.info(f"Published {event.event.value} to {self.stream_name}, message_id: {message_id}")
        except Exception as e:
            logger.error(f"Failed to publish event: {e}", exc_info=True)
            raise

    async def publish(self, event: QueryEvent) -> None:
        """Publish event to Redis Stream - uses sync version for Celery compatibility."""
        self.publish_sync(event)

    def close_sync(self) -> None:
        """Close synchronously (for Celery workers)."""
        try:
            redis = self._ensure_sync_connected()
            
            # Send stream end signal
            end_event = QueryEvent(
                event=EventType.COMPLETED,
                data={"_stream_end": True},
                query_id=self.query_id,
            )
            logger.info(f"Publishing stream end to {self.stream_name}")
            redis.xadd(
                self.stream_name,
                {"event": end_event.to_json()},
                maxlen=STREAM_MAX_LEN,
            )
            
            # Set TTL on the stream for cleanup
            redis.expire(self.stream_name, STREAM_TTL_SECONDS)
            
            logger.info(f"Closed stream {self.stream_name}")

            if self._sync_redis:
                self._sync_redis.close()
                self._sync_redis = None
        except Exception as e:
            logger.error(f"Error closing publisher: {e}", exc_info=True)

    async def close(self) -> None:
        """Publish completion signal and close connection."""
        self.close_sync()


class RedisEventSubscriber:
    """
    Subscriber that reads from Redis Streams.
    Used by FastAPI SSE endpoints to stream Celery task events.
    
    Reads from the beginning of the stream, so no events are missed
    even if the subscriber connects after some events are published.
    """

    def __init__(
        self,
        query_id: str | UUID,
        timeout: float = 300.0,  # 5 minutes default
    ) -> None:
        self.query_id = str(query_id)
        self.stream_name = _get_stream_name(query_id)
        self.timeout = timeout
        self._redis: Redis | None = None
        self._last_id = "0"  # Start from beginning of stream

    async def _connect(self) -> Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            logger.debug(f"Connected to stream {self.stream_name}")
        return self._redis

    async def events(self) -> AsyncGenerator[QueryEvent, None]:
        """
        Read events from the stream.
        Yields events until completion or timeout.
        """
        redis = await self._connect()
        heartbeat_interval = 15.0
        last_heartbeat = time.time()
        start_time = time.time()

        try:
            while True:
                # Check overall timeout
                if time.time() - start_time > self.timeout:
                    logger.warning(f"Timeout reading from stream {self.stream_name}")
                    yield QueryEvent(
                        event=EventType.ERROR,
                        data={"error": "Event stream timeout"},
                        query_id=self.query_id,
                    )
                    break

                # Read from stream with short block time for responsiveness
                try:
                    messages = await redis.xread(
                        {self.stream_name: self._last_id},
                        count=10,
                        block=5000,  # 5 second block
                    )
                except Exception as e:
                    logger.error(f"Error reading stream {self.stream_name}: {e}")
                    await asyncio.sleep(1)
                    continue

                current_time = time.time()

                if not messages:
                    # No messages, send heartbeat if needed
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield QueryEvent(
                            event=EventType.HEARTBEAT,
                            data={},
                            query_id=self.query_id,
                        )
                        last_heartbeat = current_time
                    continue

                # Process messages
                logger.info(f"Received {len(messages)} message batches from stream {self.stream_name}")
                for stream_name, stream_messages in messages:
                    logger.info(f"Processing {len(stream_messages)} messages from {stream_name}")
                    for message_id, message_data in stream_messages:
                        self._last_id = message_id
                        logger.debug(f"Processing message {message_id}: {message_data}")
                        
                        try:
                            event_json = message_data.get("event", "{}")
                            event = QueryEvent.from_json(event_json)
                            
                            logger.info(f"Parsed event: {event.event.value}")
                            
                            # Check for stream end signal
                            if event.data.get("_stream_end"):
                                logger.info(f"Stream end received for {self.query_id}")
                                return  # Exit the generator
                            
                            yield event
                            
                        except Exception as e:
                            logger.error(f"Error parsing event from {message_id}: {e}, data: {message_data}")
                            continue

        finally:
            await self.close()

    async def close(self) -> None:
        """Close connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None


class EventEmitter:
    """
    Helper class for emitting events during query processing.
    Wraps a publisher and provides convenient methods.
    
    All methods emit data that conforms to the Pydantic schemas in app.schemas.query.
    """

    def __init__(self, publisher: EventPublisher, query_id: str | UUID) -> None:
        self.publisher = publisher
        self.query_id = str(query_id)

    async def emit(self, event_type: EventType, **data: Any) -> None:
        """Emit an event."""
        event = QueryEvent(
            event=event_type,
            data=data,
            query_id=self.query_id,
        )
        await self.publisher.publish(event)

    async def status(self, status: str, message: str) -> None:
        """Emit status update. Matches StatusUpdateEvent schema."""
        await self.emit(EventType.STATUS, status=status, message=message)

    async def tool_call(self, tool: str, args: dict[str, Any]) -> None:
        """Emit tool call event (internal, no schema)."""
        await self.emit(EventType.TOOL_CALL, tool=tool, args=args)

    async def search_complete(self, query: str, results_count: int) -> None:
        """Emit search progress. Matches SearchProgressEvent schema."""
        await self.emit(
            EventType.SEARCH_COMPLETE,
            sections_found=results_count,
            message=f"Found {results_count} sections for: {query}",
        )

    async def suggestion(
        self,
        suggestion_id: str,
        section_title: str | None,
        file_path: str,
        confidence: float,
        preview: str = "",
    ) -> None:
        """Emit suggestion created. Matches SuggestionGeneratedEvent schema."""
        await self.emit(
            EventType.SUGGESTION,
            suggestion_id=suggestion_id,
            section_title=section_title,
            file_path=file_path,
            confidence=confidence,
            preview=preview,
        )

    async def completed(self, total_suggestions: int) -> None:
        """Emit completion. Matches CompletedEvent schema."""
        await self.emit(
            EventType.COMPLETED,
            total_suggestions=total_suggestions,
            query_id=self.query_id,
        )

    async def error(self, error: str, details: str | None = None) -> None:
        """Emit error. Matches ErrorEvent schema."""
        await self.emit(EventType.ERROR, error=error, details=details)

    async def close(self) -> None:
        await self.publisher.close()