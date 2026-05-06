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
from core.adapters import telegram_wizards as wizards
from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, ChannelBinding
from core.runner.orchestrator import RunRequest, get_orchestrator

logger = logging.getLogger(__name__)


# In-flight runs we dispatched: run_id → {chat_id, placeholder_msg_id}.
# Kept in-memory because it's cheap and the placeholder is short-lived.
_PENDING: dict[int, dict] = {}

# v0.6 — Session continuity per chat. Without this, every Telegram message
# spawns a fresh subprocess with no memory of the previous turn — gugol
# repeatedly says "no tengo contexto de la conversación anterior" which is
# unusable as an assistant. Mapping is chat_id (str) → session_id (str).
# When a run completes, we capture its session_id and reuse it on the next
# turn from the same chat. Cleared by the /reset command.
_CHAT_SESSIONS: dict[str, str] = {}


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
        # v0.6 — wizards conversacionales
        app.add_handler(CommandHandler("setup_mcp", self._cmd_setup_mcp))
        app.add_handler(CommandHandler("list_mcps", self._cmd_list_mcps))
        app.add_handler(CommandHandler("test_mcp", self._cmd_test_mcp))
        app.add_handler(CommandHandler("cancel", self._cmd_cancel))
        app.add_handler(CommandHandler("help_prompt", self._cmd_help_prompt))
        app.add_handler(CommandHandler("reset", self._cmd_reset))
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
                f"Hola. Este chat está vinculado a *{bound['agent_name']}*. "
                "Envía cualquier mensaje y se lo paso.\n\n"
                "Comandos: /agents · /bind <agente> · /status · /whoami",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"Hola. Este chat (id `{chat_id}`) todavía no está vinculado a ningún agente.\n\n"
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
            "Comparte estos ids al operador para que te agregue al allowlist.",
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
                await update.message.reply_text(f"No existe el agente `{agent_name}`. Prueba `/agents`.", parse_mode="Markdown")
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
                action = "vinculado"
            await session.commit()
        await update.message.reply_text(f"Chat {action} a *{agent_name}*. Envía un mensaje y va.", parse_mode="Markdown")

    # v0.6 — wizard commands -----------------------------------------------

    async def _cmd_setup_mcp(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        if wizards.is_in_wizard(chat_id):
            wizards.cancel_wizard(chat_id)
        msg = await wizards.start_setup_mcp(chat_id)
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_list_mcps(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        msg = await wizards.list_mcps_for_chat()
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_test_mcp(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        msg = await wizards.test_mcp_for_chat(ctx.args or [])
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_cancel(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        cancelled = wizards.cancel_wizard(chat_id)
        await update.message.reply_text(
            "Wizard cancelado." if cancelled else "(no había wizard activo)"
        )

    async def _cmd_reset(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Forget the conversational context for this chat — next message starts fresh."""
        if not self._is_authorized(update):
            return
        chat_id = str(update.effective_chat.id)
        had = _CHAT_SESSIONS.pop(chat_id, None)
        if had:
            await update.message.reply_text(
                "Memoria de la conversación borrada. Próximo mensaje empieza de cero."
            )
        else:
            await update.message.reply_text(
                "(no había memoria que borrar — ya estabas en una conversación nueva)"
            )

    async def _cmd_help_prompt(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        await update.message.reply_text(
            "*Cómo armar un buen prompt para el Architect*\n\n"
            "1. *Idea (1 línea)* — qué tiene que entregar el equipo, no qué herramientas usa.\n"
            "2. *Constraints* — USUARIO, EQUIPO (con modelos sugeridos), LECCIONES INICIALES, SCHEDULES, RESTRICCIONES.\n\n"
            "Anti-patrones a evitar:\n"
            "• Restricciones temporales en el body (\"sin Gmail por ahora\") → contaminan al modelo después.\n"
            "• Roles superpuestos entre agentes.\n"
            "• Detalles de implementación (paquetes npm, comandos) → eso lo configurás con `/setup_mcp`.\n\n"
            "Guía completa con ejemplos copiables: dashboard → /architect → expandí *Cómo armar un buen prompt*.",
            parse_mode="Markdown",
        )

    # Message dispatch -------------------------------------------------------

    async def _handle(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        chat_id = update.effective_chat.id

        # v0.6 — if a wizard is active, forward the input to it instead of
        # dispatching to the orchestrator. This is what makes /setup_mcp
        # feel conversational.
        if wizards.is_in_wizard(chat_id):
            try:
                reply, finished = await wizards.step_setup_mcp(chat_id, text)
                await update.message.reply_text(reply, parse_mode="Markdown")
            except Exception as e:
                logger.exception("wizard step crashed")
                wizards.cancel_wizard(chat_id)
                await update.message.reply_text(
                    f"El wizard falló inesperadamente: {e}. Cancelado."
                )
            return

        bound = await _lookup_binding(str(chat_id))
        if not bound:
            await update.message.reply_text(
                f"Este chat (`{chat_id}`) no está vinculado. Usa `/bind <agente>` o `/agents`.",
                parse_mode="Markdown",
            )
            return
        placeholder = await update.message.reply_text(f"⏳ {bound['agent_name']} pensando…")
        # v0.6 — thread conversational context: pass the previous turn's
        # session_id so claude-agent-sdk continues the same session.
        session_id = _CHAT_SESSIONS.get(str(chat_id))
        try:
            run_id = await get_orchestrator().enqueue(RunRequest(
                agent_name=bound["agent_name"],
                prompt=text,
                source="telegram",
                session_id=session_id,
                metadata={"chat_id": chat_id, "placeholder_msg_id": placeholder.message_id},
            ))
            _PENDING[run_id] = {
                "chat_id": chat_id,
                "placeholder_msg_id": placeholder.message_id,
            }
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
                        # v0.6 — capture the session_id so the next message
                        # from this chat continues the same conversation.
                        new_session = evt.data.get("session_id")
                        if new_session:
                            _CHAT_SESSIONS[str(pend["chat_id"])] = new_session
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
