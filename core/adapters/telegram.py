"""Telegram adapter — port of eduagent-gateway/gateway.py.

Long-polling, allowlist, single-instance enforced at process level via
docker-compose (one container, one poller).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from core import runtime_state
from core.adapters.base import Adapter
from core.runner.orchestrator import RunRequest, get_orchestrator

logger = logging.getLogger(__name__)


class TelegramAdapter(Adapter):
    name = "telegram"

    def __init__(self, default_agent: str = "default") -> None:
        self._app: Application | None = None
        self._default_agent = default_agent

    async def start(self) -> None:
        token = runtime_state.telegram_token()
        if not token:
            logger.info("telegram disabled (no token)")
            return

        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
        app.add_error_handler(self._on_error)

        self._app = app
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram adapter started (allowed=%s)", runtime_state.telegram_allowed_user_ids())

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    async def publish(self, channel_id: str, text: str) -> None:
        if not self._app:
            return
        await self._app.bot.send_message(chat_id=int(channel_id), text=text)

    # Handlers ---------------------------------------------------------------

    def _is_authorized(self, update: Update) -> bool:
        allowed = runtime_state.telegram_allowed_user_ids()
        user = update.effective_user
        if not user:
            return False
        if not allowed:
            return False  # no allowlist = nobody
        return user.id in allowed

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        await update.message.reply_text(
            "Rogologo Telegram adapter active. Send any message to dispatch it to the default agent."
        )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        orch = get_orchestrator()
        await update.message.reply_text(f"Active runs: {orch.active_count}")

    async def _handle(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        chat_id = update.effective_chat.id
        placeholder = await update.message.reply_text("Working…")

        try:
            run_id = await get_orchestrator().enqueue(RunRequest(
                agent_name=self._default_agent,
                prompt=text,
                source="telegram",
                metadata={"chat_id": chat_id, "placeholder_msg_id": placeholder.message_id},
            ))
            await placeholder.edit_text(f"Run #{run_id} queued. Results will follow.")
        except Exception as e:
            logger.exception("telegram dispatch failed")
            await placeholder.edit_text(f"Error: {e}")

    async def _on_error(self, update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        err = ctx.error
        if isinstance(err, Conflict):
            logger.warning("telegram conflict (another poller running?)")
            return
        if isinstance(err, NetworkError):
            logger.warning("telegram network error: %s", err)
            return
        logger.exception("telegram unhandled error", exc_info=err)
