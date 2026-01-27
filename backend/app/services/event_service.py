"""
Event Service - Real-time Query Processing Updates via SSE
===========================================================

This module enables real-time streaming of query processing events
to the frontend using Server-Sent Events (SSE). It supports two modes:

1. Direct Mode (DirectEventPublisher):
   - Events flow directly via async queue
   - Used when processing happens in same process as HTTP server
   - Simpler, lower latency, no external dependencies

2. Redis Mode (RedisEventPublisher/RedisEventSubscriber):
   - Events flow through Redis Streams
   - Used when processing happens in Celery worker (separate process)
   - Required for production with background task processing

Architecture:
-------------
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Celery    │────▶│   Redis     │────▶│   FastAPI   │────▶ SSE
│   Worker    │     │   Stream    │     │   Server    │
└─────────────┘     └─────────────┘     └─────────────┘
      │                                        │
      └── RedisEventPublisher       RedisEventSubscriber ──┘

Event Types:
------------
- STATUS: Processing phase updates ("Analyzing query...", "Searching...")
- TOOL_CALL: AI agent tool invocations (search, get_section, etc.)
- SEARCH_COMPLETE: Search results summary
- SUGGESTION: New edit suggestion generated
- COMPLETED: Processing finished
- ERROR: Processing failed
- HEARTBEAT: Keep-alive signal (prevents connection timeout)

Redis Streams vs Pub/Sub:
-------------------------
We use Redis Streams instead of Pub/Sub because:
1. Persistence - Events survive brief disconnections
2. Replay - Can read events from a specific point
3. Backpressure - MAXLEN prevents unbounded memory growth
4. Acknowledgment - Know when messages are delivered

Production Considerations:
--------------------------
- Set appropriate STREAM_MAX_LEN based on expected events per query
- Adjust STREAM_TTL_SECONDS based on max expected client reconnect time
- Monitor Redis memory usage
- Add dead letter queue for failed event processing
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
import redis as sync_redis
from redis.client import Redis as SyncRedis

from app.config import settings

logger = logging.getLogger(__name__)

# Maximum events to retain in a stream (oldest are evicted when exceeded)
STREAM_MAX_LEN = 1000

# How long to keep completed streams before auto-deletion (1 hour)
STREAM_TTL_SECONDS = 3600 


class EventType(str, Enum):
    """
    Types of events emitted during query processing.

    Each event type corresponds to a processing phase or outcome
    that the frontend needs to display to the user.
    """
    STATUS = "status"           # Processing phase update (e.g., "Analyzing...")
    TOOL_CALL = "tool_call"     # AI agent invoked a tool
    SEARCH_COMPLETE = "search_complete"  # Vector search finished
    SUGGESTION = "suggestion"   # New edit suggestion generated
    COMPLETED = "completed"     # All processing finished
    ERROR = "error"             # Processing failed
    HEARTBEAT = "heartbeat"     # Keep-alive (prevents browser timeout)


@dataclass
class QueryEvent:
    """
    A single event in the query processing stream.

    Represents one update that should be sent to the frontend via SSE.
    Serializes to JSON for transmission and storage in Redis.

    Fields:
        event: The event type (STATUS, SUGGESTION, etc.)
        data: Event-specific payload (varies by event type)
        query_id: Links event to originating query
        timestamp: ISO format timestamp for ordering/debugging
    """
    event: EventType
    data: dict[str, Any]
    query_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event": self.event.value,
            "data": self.data,
            "query_id": self.query_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Serialize to JSON string for Redis/SSE transmission."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, data: str) -> QueryEvent:
        """Deserialize from JSON string (used by subscriber)."""
        parsed = json.loads(data)
        return cls(
            event=EventType(parsed["event"]),
            data=parsed["data"],
            query_id=parsed["query_id"],
            timestamp=parsed.get("timestamp", datetime.utcnow().isoformat()),
        )


def _get_stream_name(query_id: str | UUID) -> str:
    """Generate Redis stream key for a query. Format: 'query_stream:{uuid}'"""
    return f"query_stream:{query_id}"


class EventPublisher(Protocol):
    """
    Protocol defining the publisher interface.

    Both DirectEventPublisher and RedisEventPublisher implement this,
    allowing the AI agent code to work identically in both modes.
    """

    async def publish(self, event: QueryEvent) -> None:
        """Publish an event to subscribers."""
        ...

    async def close(self) -> None:
        """Signal end of stream and cleanup resources."""
        ...


class DirectEventPublisher:
    """
    In-process event publisher using asyncio Queue.

    Used when query processing happens in the same process as the
    HTTP server (no Celery). Events flow directly from AI agent
    to SSE endpoint without Redis.

    Pros:
        - No external dependencies
        - Lower latency (no network hop)
        - Simpler debugging

    Cons:
        - Doesn't work with Celery workers (separate processes)
        - Events lost if HTTP connection drops

    Usage:
        publisher = DirectEventPublisher(query_id)
        await publisher.publish(QueryEvent(...))
        async for event in publisher.events():
            yield format_sse(event)
        await publisher.close()
    """

    def __init__(self, query_id: str | UUID) -> None:
        self.query_id = str(query_id)
        self._events: asyncio.Queue[QueryEvent] = asyncio.Queue()
        self._closed = False

    async def publish(self, event: QueryEvent) -> None:
        """Add event to queue for consumption by SSE endpoint."""
        if not self._closed:
            await self._events.put(event)

    async def close(self) -> None:
        """Signal end of stream with sentinel event."""
        self._closed = True
        await self._events.put(
            QueryEvent(
                event=EventType.COMPLETED,
                data={"_stream_end": True},
                query_id=self.query_id,
            )
        )

    async def events(self) -> AsyncGenerator[QueryEvent, None]:
        """
        Async generator yielding events as they arrive.

        Blocks until events are available, yields them one by one,
        and terminates when stream end sentinel is received.
        """
        while True:
            event = await self._events.get()
            if event.data.get("_stream_end"):
                break
            yield event


class RedisEventPublisher:
    """
    Redis Streams-based event publisher for Celery workers.

    When query processing runs in a Celery worker (separate process),
    we can't use in-memory queues. Instead, events are published to
    a Redis Stream that the HTTP server subscribes to.

    Why Synchronous Redis Client?
    -----------------------------
    Celery workers use their own event loop, and mixing async Redis
    with Celery's concurrency model causes issues. We use sync Redis
    client (redis-py) here, which works reliably in Celery tasks.

    Stream Lifecycle:
    -----------------
    1. Created when first event is published (XADD auto-creates)
    2. Events accumulate up to STREAM_MAX_LEN (oldest evicted)
    3. Stream end marker published on close()
    4. TTL set on close() for automatic cleanup

    Usage (in Celery task):
        publisher = RedisEventPublisher(query_id)
        publisher.publish_sync(QueryEvent(...))  # Use sync version in Celery
        publisher.close_sync()
    """

    def __init__(self, query_id: str | UUID) -> None:
        self.query_id = str(query_id)
        self.stream_name = _get_stream_name(query_id)
        self._sync_redis: SyncRedis[str] | None = None
        logger.info(f"RedisEventPublisher created for stream: {self.stream_name}")

    def _ensure_sync_connected(self) -> SyncRedis[str]:
        """Lazily connect to Redis on first use."""
        if self._sync_redis is None:
            logger.info(f"Connecting to Redis: {settings.redis_url}")
            self._sync_redis = sync_redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            self._sync_redis.ping()  # Verify connection works
            logger.info("Redis connection established")
        return self._sync_redis

    def publish_sync(self, event: QueryEvent) -> None:
        """
        Publish event to Redis Stream (synchronous version for Celery).

        Uses XADD command which:
        - Auto-creates stream if it doesn't exist
        - Appends event with auto-generated message ID
        - Trims stream to MAXLEN, evicting oldest events

        Args:
            event: The QueryEvent to publish

        Raises:
            Exception: If Redis connection fails
        """
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
        """Async wrapper for publish_sync (implements EventPublisher protocol)."""
        self.publish_sync(event)

    def close_sync(self) -> None:
        """
        Close the stream and cleanup resources.

        Operations:
        1. Publish stream end sentinel event
        2. Set TTL on stream for automatic cleanup
        3. Close Redis connection

        The TTL ensures streams are eventually deleted even if
        no subscriber ever connects to consume them.
        """
        try:
            redis = self._ensure_sync_connected()

            # Publish sentinel event to signal stream end
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

            # Set expiration so stream is auto-deleted after TTL
            redis.expire(self.stream_name, STREAM_TTL_SECONDS)

            logger.info(f"Closed stream {self.stream_name}")

            if self._sync_redis:
                self._sync_redis.close()
                self._sync_redis = None
        except Exception as e:
            logger.error(f"Error closing publisher: {e}", exc_info=True)

    async def close(self) -> None:
        """Async wrapper for close_sync (implements EventPublisher protocol)."""
        self.close_sync()


class RedisEventSubscriber:
    """
    Redis Streams subscriber for SSE endpoint.

    Connects to a Redis Stream and yields events as they arrive.
    Used by the FastAPI SSE endpoint to stream events to the browser.

    XREAD Behavior:
    ---------------
    - Blocks waiting for new events (5 second timeout)
    - Returns in batches for efficiency
    - Tracks last_id to resume from where we left off
    - Survives brief connection interruptions

    Timeout and Heartbeats:
    -----------------------
    - Overall timeout prevents infinite waits for dead streams
    - Heartbeat events sent every 15s to prevent browser/proxy timeouts
    - Most browsers/proxies close idle connections after 60-120s

    Usage (in FastAPI SSE endpoint):
        subscriber = RedisEventSubscriber(query_id)
        async for event in subscriber.events():
            yield f"data: {event.to_json()}\\n\\n"
    """

    def __init__(
        self,
        query_id: str | UUID,
        timeout: float = 300.0,  # 5 minute overall timeout
    ) -> None:
        self.query_id = str(query_id)
        self.stream_name = _get_stream_name(query_id)
        self.timeout = timeout
        self._redis: Redis | None = None
        self._last_id = "0"  # Start from beginning of stream

    async def _connect(self) -> Redis:
        """Lazily connect to Redis on first use (async client)."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            logger.debug(f"Connected to stream {self.stream_name}")
        return self._redis

    async def events(self) -> AsyncGenerator[QueryEvent, None]:
        """
        Async generator that yields events from the Redis Stream.

        This is the main consumption loop. It:
        1. Connects to Redis
        2. Uses XREAD with blocking to wait for events
        3. Parses and yields each event
        4. Sends heartbeats during idle periods
        5. Terminates on stream end sentinel or timeout

        Yields:
            QueryEvent objects as they arrive

        Error Handling:
            - Redis read errors: sleep and retry
            - Parse errors: log and skip
            - Timeout: yield error event and return
        """
        redis = await self._connect()
        heartbeat_interval = 15.0  # Send heartbeat every 15 seconds
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

                # Read from stream with 5 second block timeout
                try:
                    messages = await redis.xread(
                        {self.stream_name: self._last_id},
                        count=10,  # Process up to 10 messages per iteration
                        block=5000,  # 5 second block timeout
                    )
                except Exception as e:
                    logger.error(f"Error reading stream {self.stream_name}: {e}")
                    await asyncio.sleep(1)  # Brief pause before retry
                    continue

                current_time = time.time()

                # No messages - check if heartbeat needed
                if not messages:
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield QueryEvent(
                            event=EventType.HEARTBEAT,
                            data={},
                            query_id=self.query_id,
                        )
                        last_heartbeat = current_time
                    continue

                # Process received messages
                logger.info(f"Received {len(messages)} message batches from stream {self.stream_name}")
                for stream_name, stream_messages in messages:
                    logger.info(f"Processing {len(stream_messages)} messages from {stream_name}")
                    for message_id, message_data in stream_messages:
                        self._last_id = message_id  # Track position for resumption
                        logger.debug(f"Processing message {message_id}: {message_data}")

                        try:
                            event_json = message_data.get("event", "{}")
                            event = QueryEvent.from_json(event_json)

                            logger.info(f"Parsed event: {event.event.value}")

                            # Check for stream end sentinel
                            if event.data.get("_stream_end"):
                                logger.info(f"Stream end received for {self.query_id}")
                                return  # Exit generator cleanly

                            yield event

                        except Exception as e:
                            logger.error(f"Error parsing event from {message_id}: {e}, data: {message_data}")
                            continue  # Skip malformed events

        finally:
            await self.close()

    async def close(self) -> None:
        """Close Redis connection and cleanup."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None


class EventEmitter:
    """
    High-level helper for emitting typed events.

    Wraps EventPublisher with convenient methods for each event type.
    Used by the AI agent code to emit events without constructing
    QueryEvent objects manually.

    This abstraction keeps the AI agent code clean:
        # Instead of:
        await publisher.publish(QueryEvent(
            event=EventType.STATUS,
            data={"status": "searching", "message": "..."},
            query_id=query_id,
        ))

        # We can write:
        await emitter.status("searching", "Finding relevant sections...")

    Usage:
        emitter = EventEmitter(publisher, query_id)
        await emitter.status("analyzing", "Parsing your request...")
        await emitter.search_complete(sections_found=5)
        await emitter.suggestion(...)
        await emitter.completed(total_suggestions=3)
    """

    def __init__(self, publisher: EventPublisher, query_id: str | UUID):
        self.query_id = str(query_id)
        self.publisher = publisher

    async def emit(self, event: EventType, **data) -> None:
        """Low-level emit - prefer using typed methods below."""
        query_event = QueryEvent(
            event=event,
            data=data,
            query_id=self.query_id,
        )
        await self.publisher.publish(query_event)

    async def status(self, status: str, message: str = "") -> None:
        """
        Emit processing status update.

        Args:
            status: Short status code (e.g., "analyzing", "searching", "generating")
            message: Human-readable description for UI display
        """
        await self.emit(EventType.STATUS, status=status, message=message)

    async def tool_call(self, tool: str, args: dict[str, Any]) -> None:
        """
        Emit AI agent tool invocation.

        Sent when the AI agent uses a tool (search, get_section, etc.).
        Useful for debugging and showing users what the AI is doing.

        Args:
            tool: Tool name (e.g., "semantic_search", "get_section_content")
            args: Arguments passed to the tool
        """
        await self.emit(EventType.TOOL_CALL, tool=tool, args=args)

    async def search_complete(
        self,
        sections_found: int,
        message: str = "",
        tool_name: str = "",
        results: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Emit search completion event.

        Sent after vector search completes. Tells the UI how many
        relevant sections were found.

        Args:
            sections_found: Number of sections matching the query
            message: Optional custom message (default: "Found N sections")
            tool_name: Which search tool was used
            results: Optional - search results (not currently used)
        """
        await self.emit(
            EventType.SEARCH_COMPLETE,
            sections_found=sections_found,
            message=message or f"Found {sections_found} sections",
            tool_name=tool_name,
        )

    async def suggestion(
        self,
        suggestion_id: str,
        document_id: str,
        section_title: str | None,
        file_path: str,
        confidence: float,
        preview: str = "",
    ) -> None:
        """
        Emit new edit suggestion.

        Sent when AI generates a suggestion for a section edit.
        The frontend uses this to render suggestion cards in real-time.

        Args:
            suggestion_id: UUID of the created suggestion (for accept/reject)
            document_id: UUID of the affected document
            section_title: Title of the section to edit
            file_path: Document file path (for display)
            confidence: AI confidence score (0.0-1.0)
            preview: Short preview of the suggested change
        """
        await self.emit(
            EventType.SUGGESTION,
            suggestion_id=suggestion_id,
            document_id=document_id,
            section_title=section_title,
            file_path=file_path,
            confidence=confidence,
            preview=preview,
        )

    async def completed(self, total_suggestions: int) -> None:
        """
        Emit processing completion event.

        Signals that all processing is done. The frontend uses this
        to stop showing loading indicators and display final results.

        Args:
            total_suggestions: Total number of suggestions generated
        """
        await self.emit(
            EventType.COMPLETED,
            total_suggestions=total_suggestions,
            query_id=self.query_id,
        )

    async def error(self, error: str, details: str | None = None) -> None:
        """
        Emit error event.

        Sent when processing fails. The frontend displays error message.

        Args:
            error: Short error message for display
            details: Optional detailed error info (for debugging)
        """
        await self.emit(EventType.ERROR, error=error, details=details)

    async def close(self) -> None:
        """Close the underlying publisher."""
        await self.publisher.close()