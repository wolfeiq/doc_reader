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

STREAM_MAX_LEN = 1000 
STREAM_TTL_SECONDS = 3600 


class EventType(str, Enum):
    STATUS = "status"
    TOOL_CALL = "tool_call"
    SEARCH_COMPLETE = "search_complete"
    SUGGESTION = "suggestion"
    COMPLETED = "completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class QueryEvent:
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
    return f"query_stream:{query_id}"


class EventPublisher(Protocol):

    async def publish(self, event: QueryEvent) -> None:
        ...

    async def close(self) -> None:
        ...


class DirectEventPublisher:
    def __init__(self, query_id: str | UUID) -> None:
        self.query_id = str(query_id)
        self._events: asyncio.Queue[QueryEvent] = asyncio.Queue()
        self._closed = False

    async def publish(self, event: QueryEvent) -> None:
        if not self._closed:
            await self._events.put(event)

    async def close(self) -> None:
        self._closed = True
        await self._events.put(
            QueryEvent(
                event=EventType.COMPLETED,
                data={"_stream_end": True},
                query_id=self.query_id,
            )
        )

    async def events(self) -> AsyncGenerator[QueryEvent, None]:
        while True:
            event = await self._events.get()
            if event.data.get("_stream_end"):
                break
            yield event


class RedisEventPublisher:
    def __init__(self, query_id: str | UUID) -> None:
        self.query_id = str(query_id)
        self.stream_name = _get_stream_name(query_id)
        self._sync_redis: SyncRedis[str] | None = None
        logger.info(f"RedisEventPublisher created for stream: {self.stream_name}")

    def _ensure_sync_connected(self) -> SyncRedis[str]:
        if self._sync_redis is None:
            logger.info(f"Connecting to Redis: {settings.redis_url}")
            self._sync_redis = sync_redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            self._sync_redis.ping()
            logger.info("Redis connection established")
        return self._sync_redis

    def publish_sync(self, event: QueryEvent) -> None:
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
        self.publish_sync(event)

    def close_sync(self) -> None:
        try:
            redis = self._ensure_sync_connected()
            
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
            
            redis.expire(self.stream_name, STREAM_TTL_SECONDS)
            
            logger.info(f"Closed stream {self.stream_name}")

            if self._sync_redis:
                self._sync_redis.close()
                self._sync_redis = None
        except Exception as e:
            logger.error(f"Error closing publisher: {e}", exc_info=True)

    async def close(self) -> None:
        self.close_sync()


class RedisEventSubscriber:
    def __init__(
        self,
        query_id: str | UUID,
        timeout: float = 300.0, 
    ) -> None:
        self.query_id = str(query_id)
        self.stream_name = _get_stream_name(query_id)
        self.timeout = timeout
        self._redis: Redis | None = None
        self._last_id = "0" 

    async def _connect(self) -> Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            logger.debug(f"Connected to stream {self.stream_name}")
        return self._redis

    async def events(self) -> AsyncGenerator[QueryEvent, None]:

        redis = await self._connect()
        heartbeat_interval = 15.0
        last_heartbeat = time.time()
        start_time = time.time()

        try:
            while True:

                if time.time() - start_time > self.timeout:
                    logger.warning(f"Timeout reading from stream {self.stream_name}")
                    yield QueryEvent(
                        event=EventType.ERROR,
                        data={"error": "Event stream timeout"},
                        query_id=self.query_id,
                    )
                    break
                try:
                    messages = await redis.xread(
                        {self.stream_name: self._last_id},
                        count=10,
                        block=5000,
                    )
                except Exception as e:
                    logger.error(f"Error reading stream {self.stream_name}: {e}")
                    await asyncio.sleep(1)
                    continue

                current_time = time.time()

                if not messages:
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield QueryEvent(
                            event=EventType.HEARTBEAT,
                            data={},
                            query_id=self.query_id,
                        )
                        last_heartbeat = current_time
                    continue

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
                            
                            if event.data.get("_stream_end"):
                                logger.info(f"Stream end received for {self.query_id}")
                                return  
                            
                            yield event
                            
                        except Exception as e:
                            logger.error(f"Error parsing event from {message_id}: {e}, data: {message_data}")
                            continue

        finally:
            await self.close()

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None


class EventEmitter:
    
    def __init__(self, publisher: EventPublisher, query_id: str | UUID):
        self.query_id = str(query_id)
        self.publisher = publisher

    async def emit(self, event: EventType, **data) -> None:
        query_event = QueryEvent(
            event=event,
            data=data,
            query_id=self.query_id,
        )
        await self.publisher.publish(query_event)

    async def status(self, status: str, message: str = "") -> None:
        await self.emit(EventType.STATUS, status=status, message=message)

    async def tool_call(self, tool: str, args: dict[str, Any]) -> None:
        await self.emit(EventType.TOOL_CALL, tool=tool, args=args)

    async def search_complete(
        self,
        sections_found: int,
        message: str = "",
        tool_name: str = "",
        results: list[dict[str, Any]] | None = None,
    ) -> None:
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
        await self.emit(
            EventType.COMPLETED,
            total_suggestions=total_suggestions,
            query_id=self.query_id,
        )

    async def error(self, error: str, details: str | None = None) -> None:
        await self.emit(EventType.ERROR, error=error, details=details)

    async def close(self) -> None:
        await self.publisher.close()