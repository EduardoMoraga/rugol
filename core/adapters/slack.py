"""Slack adapter — Bolt for Python, socket mode (no public webhook needed)."""
from __future__ import annotations

import asyncio
import logging

from core.adapters.base import Adapter
from core.config import get_settings
from core.runner.orchestrator import RunRequest, get_orchestrator

logger = logging.getLogger(__name__)


class SlackAdapter(Adapter):
    name = "slack"

    def __init__(self, default_agent: str = "default") -> None:
        self._app = None
        self._handler = None
        self._task: asyncio.Task | None = None
        self._default_agent = default_agent

    async def start(self) -> None:
        settings = get_settings()
        if not settings.slack_enabled:
            logger.info("slack disabled (no tokens)")
            return

        try:
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
            from slack_bolt.async_app import AsyncApp
        except ImportError:
            logger.warning("slack-bolt not installed, slack adapter inactive")
            return

        app = AsyncApp(
            token=settings.SLACK_BOT_TOKEN,
            signing_secret=settings.SLACK_SIGNING_SECRET,
        )

        @app.event("app_mention")
        async def on_mention(event, say):
            text = (event.get("text") or "").strip()
            try:
                run_id = await get_orchestrator().enqueue(RunRequest(
                    agent_name=self._default_agent,
                    prompt=text,
                    source="slack",
                    metadata={"channel": event.get("channel")},
                ))
                await say(f"Run #{run_id} queued.")
            except Exception as e:
                await say(f"Error: {e}")

        handler = AsyncSocketModeHandler(app, settings.SLACK_APP_TOKEN)
        self._app = app
        self._handler = handler
        self._task = asyncio.create_task(handler.start_async())
        logger.info("slack adapter started (socket mode)")

    async def stop(self) -> None:
        if self._handler:
            await self._handler.close_async()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def publish(self, channel_id: str, text: str) -> None:
        if not self._app:
            return
        await self._app.client.chat_postMessage(channel=channel_id, text=text)
