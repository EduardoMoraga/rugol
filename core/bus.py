"""In-process pub/sub bus. Redis-ready abstraction.

Subscribers receive every event whose topic matches the subscribed pattern.
Patterns support a single trailing `*` (e.g. `run:*`).
"""
from __future__ import annotations

import asyncio
import fnmatch
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    topic: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class _Subscription:
    """A single subscriber. Backed by an asyncio queue with bounded buffer."""

    def __init__(self, pattern: str, maxsize: int = 1000) -> None:
        self.pattern = pattern
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)

    def matches(self, topic: str) -> bool:
        return fnmatch.fnmatchcase(topic, self.pattern)


class Bus:
    """In-process pub/sub. Drop-in replaceable with Redis pub/sub later."""

    def __init__(self) -> None:
        self._subs: dict[str, list[_Subscription]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, data: dict[str, Any] | None = None) -> None:
        evt = Event(topic=topic, data=data or {})
        async with self._lock:
            for _pattern, subs in list(self._subs.items()):
                for sub in subs:
                    if sub.matches(topic):
                        try:
                            sub.queue.put_nowait(evt)
                        except asyncio.QueueFull:
                            # Drop oldest if buffer full — slow consumer punishment
                            try:
                                sub.queue.get_nowait()
                                sub.queue.put_nowait(evt)
                            except (asyncio.QueueEmpty, asyncio.QueueFull):
                                pass

    async def subscribe(self, pattern: str = "*") -> AsyncIterator[Event]:
        sub = _Subscription(pattern=pattern)
        async with self._lock:
            self._subs[pattern].append(sub)
        try:
            while True:
                evt = await sub.queue.get()
                yield evt
        finally:
            async with self._lock:
                if sub in self._subs.get(pattern, []):
                    self._subs[pattern].remove(sub)


# Module-level singleton; FastAPI deps wire it everywhere.
bus = Bus()
