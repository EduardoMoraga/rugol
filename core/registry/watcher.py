"""Watchdog-based folder watcher for hot-reload of agents and skills."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class _DebouncedHandler(FileSystemEventHandler):
    """Coalesces bursts of events into one callback per file in 200ms."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[Path], Awaitable[None]],
        debounce_ms: int = 200,
    ) -> None:
        self._loop = loop
        self._cb = callback
        self._debounce_ms = debounce_ms
        self._pending: dict[str, asyncio.TimerHandle] = {}

    def _schedule(self, path: str) -> None:
        if not path.endswith(".md"):
            return
        if path in self._pending:
            self._pending[path].cancel()

        def _fire() -> None:
            self._pending.pop(path, None)
            asyncio.run_coroutine_threadsafe(self._cb(Path(path)), self._loop)

        handle = self._loop.call_later(self._debounce_ms / 1000.0, _fire)
        self._pending[path] = handle

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(str(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._schedule(str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            dest = getattr(event, "dest_path", None)
            if dest:
                self._schedule(str(dest))


class RegistryWatcher:
    """Watches AGENTS_DIR and SKILLS_DIR. Calls back into the registry."""

    def __init__(
        self,
        agents_dir: Path,
        skills_dir: Path,
        on_agent: Callable[[Path], Awaitable[None]],
        on_skill: Callable[[Path], Awaitable[None]],
    ) -> None:
        self.agents_dir = agents_dir
        self.skills_dir = skills_dir
        self._on_agent = on_agent
        self._on_skill = on_skill
        self._observer: Observer | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        observer = Observer()
        observer.schedule(_DebouncedHandler(loop, self._on_agent), str(self.agents_dir), recursive=True)
        observer.schedule(_DebouncedHandler(loop, self._on_skill), str(self.skills_dir), recursive=True)
        observer.start()
        self._observer = observer
        logger.info("registry watcher started: agents=%s skills=%s", self.agents_dir, self.skills_dir)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
