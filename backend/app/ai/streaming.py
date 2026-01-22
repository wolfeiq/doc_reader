import asyncio
import json
from typing import Any, AsyncGenerator


def format_sse_event(
    event_type: str,
    data: dict[str, Any],
    event_id: str | None = None,
    retry: int | None = None,
) -> str:

    lines: list[str] = []
    
    if event_id:
        lines.append(f"id: {event_id}")
    
    if event_type:
        lines.append(f"event: {event_type}")
    
    if retry is not None:
        lines.append(f"retry: {retry}")
    
    lines.append(f"data: {json.dumps(data)}")
    
    return "\n".join(lines) + "\n\n"


async def create_sse_stream(
    events: AsyncGenerator[dict[str, Any], None],
) -> AsyncGenerator[str, None]:

    try:
        async for event in events:
            yield format_sse_event(
                event_type=event.get("event", "message"),
                data=event.get("data", {}),
                event_id=event.get("id"),
            )
    except Exception as e:
        yield format_sse_event(
            event_type="error",
            data={"error": str(e), "type": type(e).__name__},
        )


async def sse_heartbeat(interval: int = 30) -> AsyncGenerator[str, None]:

    while True:
        await asyncio.sleep(interval)
        yield ": heartbeat\n\n"


class SSEEventBuilder:

    __slots__ = ("event_type", "data", "event_id", "retry")
    
    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        self.data: dict[str, Any] = {}
        self.event_id: str | None = None
        self.retry: int | None = None
    
    def with_data(self, **kwargs: Any) -> "SSEEventBuilder":
        self.data.update(kwargs)
        return self
    
    def with_id(self, event_id: str) -> "SSEEventBuilder":
        self.event_id = event_id
        return self
    
    def with_retry(self, retry_ms: int) -> "SSEEventBuilder":

        self.retry = retry_ms
        return self
    
    def build(self) -> str:
        return format_sse_event(
            event_type=self.event_type,
            data=self.data,
            event_id=self.event_id,
            retry=self.retry,
        )
    
    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event_type, "data": self.data}


def status_event(status: str, message: str) -> str:
    return SSEEventBuilder("status").with_data(status=status, message=message).build()


def error_event(error: str, details: str | None = None) -> str:
    builder = SSEEventBuilder("error").with_data(error=error)
    if details:
        builder.with_data(details=details)
    return builder.build()


def progress_event(current: int, total: int, message: str | None = None) -> str:
    percent = int((current / total) * 100) if total > 0 else 0
    builder = SSEEventBuilder("progress").with_data(
        current=current, total=total, percent=percent
    )
    if message:
        builder.with_data(message=message)
    return builder.build()


def complete_event(**data: Any) -> str:
    return SSEEventBuilder("complete").with_data(**data).build()