"""Telegram adapter — port of eduagent-gateway/gateway.py.

Long-polling, allowlist, single-instance enforced at process level via
docker-compose (one container, one poller).

Capa 13 (channel bindings + reply-on-completion):
- Each Telegram chat must be bound to an agent via /api/channels — no more
  silent default. Without a binding, the bot responds with help text and
  the chat_id so the user can bind it from the dashboard.
- A background bus subscriber listens for run:completed / run:failed events
  emitted by runs we dispatched, looks up the original chat + placeholder
  message, and edits the placeholder with the final text. The user actually
  sees the answer, not just "queued".
- /bind <agent-name> command lets the user bind from inside the chat
  without going to the dashboard.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from core import runtime_state
from core.adapters.base import Adapter
from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, ChannelBinding
from core.runner.orchestrator import RunRequest, get_orchestrator

logger = logging.getLogger(__name__)


# In-flight runs we dispatched: run_id → {chat_id, placeholder_msg_id}.
# Kept in-memory because it's cheap and the placeholder is short-lived.
_PENDING: dict[int, dict] = {}


class TelegramAdapter(Adapter):
    name = "telegram"

    def __init__(self) -> None:
        self._app: Application | None = None
        self._bus_task: asyncio.Task | None = None

    async def start(self) -> None:
        token = runtime_state.telegram_token()
        if not token:
            logger.info("telegram disabled (no token)")
            return

        app = Application.builder().token(token).build()
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("bind", self._cmd_bind))
        app.add_handler(CommandHandler("agents", self._cmd_agents))
        app.add_handler(CommandHandler("whoami", self._cmd_whoami))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
        app.add_error_handler(self._on_error)

        self._app = app
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram adapter started (allowed=%s)", runtime_state.telegram_allowed_user_ids())

        # Subscribe to run completion events and reply to the originating chat.
        self._bus_task = asyncio.create_task(self._consume_bus())

    async def stop(self) -> None:
        if self._bus_task:
            self._bus_task.cancel()
            try:
                await self._bus_task
            except asyncio.CancelledError:
                pass
            self._bus_task = None
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception:
                logger.exception("telegram graceful stop failed")
            self._app = None

    async def publish(self, channel_id: str, text: str) -> None:
        if not self._app:
            return
        await self._app.bot.send_message(chat_id=int(channel_id), text=text)

    # Authorization ----------------------------------------------------------

    def _is_authorized(self, update: Update) -> bool:
        allowed = runtime_state.telegram_allowed_user_ids()
        user = update.effective_user
        if not user:
            return False
        if not allowed:
            return False  # no allowlist = nobody (deliberate)
        return user.id in allowed

    # Commands ---------------------------------------------------------------

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        bound = await _lookup_binding(str(chat_id))
        if bound:
            await update.message.reply_text(
                f"Hola. Este chat está bindeado a *{bound['agent_name']}*. "
                "Mandá cualquier mensaje y se lo paso.\n\n"
                "Comandos: /agents · /bind <agente> · /status · /whoami",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"Hola. Este chat (id `{chat_id}`) todavía no está bindeado a ningún agente.\n\n"
                "Para usarlo:\n"
                "• `/agents` para ver agentes disponibles\n"
                "• `/bind <nombre-del-agente>` para asociar este chat\n"
                "• o desde el dashboard → Settings → Channels",
                parse_mode="Markdown",
            )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        orch = get_orchestrator()
        await update.message.reply_text(f"Active runs: {orch.active_count}")

    async def _cmd_whoami(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        # Whoami works WITHOUT auth so a new user can grab their id and ask
        # the operator to allowlist them. Returns user id + chat id.
        u = update.effective_user
        c = update.effective_chat
        await update.message.reply_text(
            f"user_id: `{u.id if u else '?'}`\nchat_id: `{c.id if c else '?'}`\n\n"
            "Compartile estos ids al operador para que te agregue al allowlist.",
            parse_mode="Markdown",
        )

    async def _cmd_agents(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        async with async_session_factory() as session:
            agents = (await session.execute(
                select(Agent).order_by(Agent.name)
            )).scalars().all()
        if not agents:
            await update.message.reply_text("No hay agentes registrados todavía.")
            return
        lines = [f"• `{a.name}` — {a.description[:60]}" for a in agents]
        await update.message.reply_text(
            "Agentes disponibles:\n" + "\n".join(lines),
            parse_mode="Markdown",
        )

    async def _cmd_bind(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        if not ctx.args:
            await update.message.reply_text(
                "Uso: `/bind <nombre-del-agente>` — ej. `/bind brand-architect`",
                parse_mode="Markdown",
            )
            return
        agent_name = ctx.args[0].strip()
        chat_id = str(update.effective_chat.id)
        async with async_session_factory() as session:
            agent = (await session.execute(
                select(Agent).where(Agent.name == agent_name)
            )).scalar_one_or_none()
            if agent is None:
                await update.message.reply_text(f"No existe el agente `{agent_name}`. Probá `/agents`.", parse_mode="Markdown")
                return
            existing = (await session.execute(
                select(ChannelBinding).where(
                    ChannelBinding.channel_type == "telegram",
                    ChannelBinding.external_id == chat_id,
                )
            )).scalar_one_or_none()
            if existing:
                existing.agent_id = agent.id
                action = "reasignado"
            else:
                session.add(ChannelBinding(
                    channel_type="telegram",
                    external_id=chat_id,
                    agent_id=agent.id,
                    label=update.effective_chat.title or update.effective_user.username if update.effective_user else None,
                ))
                action = "bindeado"
            await session.commit()
        await update.message.reply_text(f"Chat {action} a *{agent_name}*. Mandá un mensaje y va.", parse_mode="Markdown")

    # Message dispatch -------------------------------------------------------

    async def _handle(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        chat_id = update.effective_chat.id
        bound = await _lookup_binding(str(chat_id))
        if not bound:
            await update.message.reply_text(
                f"Este chat (`{chat_id}`) no está bindeado. Usá `/bind <agente>` o `/agents`.",
                parse_mode="Markdown",
            )
            return
        placeholder = await update.message.reply_text(f"⏳ {bound['agent_name']} pensando…")
        try:
            run_id = await get_orchestrator().enqueue(RunRequest(
                agent_name=bound["agent_name"],
                prompt=text,
                source="telegram",
                metadata={"chat_id": chat_id, "placeholder_msg_id": placeholder.message_id},
            ))
            _PENDING[run_id] = {"chat_id": chat_id, "placeholder_msg_id": placeholder.message_id}
        except Exception as e:
            logger.exception("telegram dispatch failed")
            await placeholder.edit_text(f"Error: {e}")

    # Bus consumer -----------------------------------------------------------

    async def _consume_bus(self) -> None:
        """Edit the placeholder message with the final text when the run ends."""
        try:
            async for evt in bus.subscribe("run:*"):
                if not self._app:
                    continue
                topic = evt.topic
                if topic not in {"run:completed", "run:failed", "run:cancelled"}:
                    continue
                run_id = evt.data.get("run_id")
                if run_id is None:
                    continue
                pend = _PENDING.pop(run_id, None)
                if not pend:
                    continue
                try:
                    if topic == "run:completed":
                        text = (evt.data.get("final_text") or "").strip() or "(sin texto)"
                        cost = evt.data.get("cost_usd", 0.0)
                        body = _trim_for_telegram(text)
                        suffix = f"\n\n_run #{run_id} · ${cost:.4f}_"
                        await self._app.bot.edit_message_text(
                            chat_id=pend["chat_id"],
                            message_id=pend["placeholder_msg_id"],
                            text=body + suffix,
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                        )
                    elif topic == "run:failed":
                        await self._app.bot.edit_message_text(
                            chat_id=pend["chat_id"],
                            message_id=pend["placeholder_msg_id"],
                            text=f"❌ Run #{run_id} falló: {evt.data.get('error', 'unknown')}",
                        )
                    else:  # cancelled
                        await self._app.bot.edit_message_text(
                            chat_id=pend["chat_id"],
                            message_id=pend["placeholder_msg_id"],
                            text=f"⚠️ Run #{run_id} cancelado.",
                        )
                except Exception:
                    logger.exception("telegram reply edit failed for run %s", run_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("telegram bus consumer crashed; will not auto-restart this session")

    # Error handler ----------------------------------------------------------

    async def _on_error(self, update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        err = ctx.error
        if isinstance(err, Conflict):
            logger.warning("telegram conflict (another poller running?)")
            return
        if isinstance(err, NetworkError):
            logger.warning("telegram network error: %s", err)
            return
        logger.exception("telegram unhandled error", exc_info=err)


# Helpers --------------------------------------------------------------------

async def _lookup_binding(chat_id_str: str) -> dict | None:
    async with async_session_factory() as session:
        b = (await session.execute(
            select(ChannelBinding).where(
                ChannelBinding.channel_type == "telegram",
                ChannelBinding.external_id == chat_id_str,
            )
        )).scalar_one_or_none()
        if b is None:
            return None
        agent = await session.get(Agent, b.agent_id)
        if agent is None:
            return None
        return {"agent_name": agent.name, "agent_id": agent.id, "binding_id": b.id}


def _trim_for_telegram(text: str, max_len: int = 3800) -> str:
    """Telegram message limit is 4096 chars. Leave headroom for the suffix."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 60] + "\n\n…(truncado)"
