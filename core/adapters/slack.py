"""Slack adapter — Bolt for Python, socket mode (no public webhook needed)."""
from __future__ import annotations

import asyncio
import logging

from core import runtime_state
from core.adapters.base import Adapter
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
        bot_token, signing_secret, app_token = runtime_state.slack_tokens()
        if not (bot_token and app_token):
            logger.info("slack disabled (no tokens)")
            return

        try:
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
            from slack_bolt.async_app import AsyncApp
        except ImportError:
            logger.warning("slack-bolt not installed, slack adapter inactive")
            return

        app = AsyncApp(
            token=bot_token,
            signing_secret=signing_secret or None,
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

        handler = AsyncSocketModeHandler(app, app_token)
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
