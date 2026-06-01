"""Server-Sent Events stream — frontend subscribes to bus topics."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from core.bus import bus

router = APIRouter(tags=["stream"])


@router.get("/stream")
async def stream(
    request: Request,
    topics: str = "*",
    run_id: int | None = None,
) -> EventSourceResponse:
    """SSE feed.

    `topics` — comma-separated glob patterns over the bus topic. Default `*`.
    `run_id` — when provided, drops events whose payload doesn't carry the
               matching run_id (server-side filter, avoids burning bandwidth
               in a single-run detail panel).
    """
    patterns = [t.strip() for t in topics.split(",") if t.strip()] or ["*"]

    async def event_gen():
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
                    if run_id is not None and evt.data.get("run_id") != run_id:
                        continue
                    yield {
                        "event": "message",
                        "data": json.dumps({"topic": evt.topic, "data": evt.data, "ts": evt.ts}),
                    }
                except TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            for t in tasks:
                t.cancel()

    return EventSourceResponse(event_gen())
