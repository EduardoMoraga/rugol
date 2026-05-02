"""Server-Sent Events stream — frontend subscribes to bus topics."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from core.bus import bus

router = APIRouter(tags=["stream"])


@router.get("/stream")
async def stream(request: Request, topics: str = "*") -> EventSourceResponse:
    """topics is a comma-separated list of glob patterns. Default: all events."""
    patterns = [t.strip() for t in topics.split(",") if t.strip()] or ["*"]

    async def event_gen():
        # Multiplex multiple subscriptions
        queues: list[asyncio.Queue] = []
        tasks: list[asyncio.Task] = []

        async def feed(pattern: str) -> None:
            async for evt in bus.subscribe(pattern):
                await out_q.put(evt)

        out_q: asyncio.Queue = asyncio.Queue()
        for p in patterns:
            tasks.append(asyncio.create_task(feed(p)))

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(out_q.get(), timeout=15.0)
                    yield {
                        "event": "message",
                        "data": json.dumps({"topic": evt.topic, "data": evt.data, "ts": evt.ts}),
                    }
                except asyncio.TimeoutError:
                    # Heartbeat to keep proxies happy
                    yield {"event": "ping", "data": "{}"}
        finally:
            for t in tasks:
                t.cancel()

    return EventSourceResponse(event_gen())
