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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from telegram import Update
from telegram.error import Conflict, NetworkError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from core import runtime_state
from core.config import get_settings
from core.adapters.base import Adapter
from core.adapters import session_store, telegram_wizards as wizards
from core.attachments import classify_path, extract_text
from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, ChannelBinding
from core.memory import add_memory, list_memories
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

        # v0.6.x — warm up the in-memory session cache from DB so that
        # conversations resume across uvicorn restarts.
        global _CHAT_SESSIONS
        try:
            persisted = await session_store.load_all("telegram")
            _CHAT_SESSIONS.update(persisted)
            if persisted:
                logger.info("telegram session cache warmed: %d chats", len(persisted))
        except Exception:
            logger.exception("could not warm telegram session cache from db")

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
        app.add_handler(CommandHandler("remember", self._cmd_remember))
        app.add_handler(CommandHandler("memories", self._cmd_list_memories))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
        # v0.6 — non-text inputs. Each handler downloads the file, then dispatches
        # to the bound agent with an enriched prompt.
        app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        app.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice))
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
        bound = await _resolve_binding_or_default(str(chat_id))
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
        # No parse_mode — wizard messages may contain tool names and other
        # tokens with Markdown-special chars that would crash MD V1.
        await update.message.reply_text(msg)

    async def _cmd_list_mcps(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        msg = await wizards.list_mcps_for_chat()
        await update.message.reply_text(msg)

    async def _cmd_test_mcp(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        msg = await wizards.test_mcp_for_chat(ctx.args or [])
        await update.message.reply_text(msg)

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
        had_mem = _CHAT_SESSIONS.pop(chat_id, None)
        had_db = False
        try:
            had_db = await session_store.delete_one("telegram", chat_id)
        except Exception:
            logger.exception("session_store.delete_one failed")
        if had_mem or had_db:
            await update.message.reply_text(
                "Memoria de la conversación borrada (RAM y DB). Próximo mensaje empieza de cero."
            )
        else:
            await update.message.reply_text(
                "(no había memoria que borrar — ya estabas en una conversación nueva)"
            )

    async def _cmd_remember(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Add a memory to the agent currently bound to this chat.

        Usage: /remember <texto libre que el agente debe recordar>
        Anything after the command becomes the memory body. The first ~80
        chars are used as the title. The agent will read this memory
        before every future run.
        """
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        bound = await _lookup_binding(str(chat_id))
        if not bound:
            await update.message.reply_text(
                "Antes de recordar algo, vinculá el chat a un agente con /bind."
            )
            return
        text = (update.message.text or "").strip()
        # Drop the leading /remember command itself.
        body = text.split(maxsplit=1)[1].strip() if " " in text else ""
        if not body:
            await update.message.reply_text(
                "Uso: /remember <texto>\nEjemplo: /remember edu prefiere videos en español de más de 30 minutos"
            )
            return
        title = body[:80] if len(body) <= 80 else body[:77] + "..."
        try:
            mem = add_memory(
                agent_name=bound["agent_name"],
                name=title,
                description=title,
                content=body,
                kind="note",
            )
        except Exception as e:
            logger.exception("memory add failed")
            await update.message.reply_text(f"No pude guardar la memoria: {e}")
            return
        await update.message.reply_text(
            f"Guardado en la memoria de {bound['agent_name']} (archivo: {mem.file}). "
            "Lo va a leer antes de cada corrida."
        )

    async def _cmd_list_memories(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        bound = await _lookup_binding(str(chat_id))
        if not bound:
            await update.message.reply_text(
                "Antes de listar memorias, vinculá el chat a un agente con /bind."
            )
            return
        mems = list_memories(bound["agent_name"])
        if not mems:
            await update.message.reply_text(
                f"{bound['agent_name']} no tiene memorias todavía. "
                "Agregá una con /remember <texto>."
            )
            return
        lines = [f"Memorias de {bound['agent_name']} ({len(mems)}):"]
        for m in mems[-15:]:
            lines.append(f"• {m.name}")
        if len(mems) > 15:
            lines.append(f"... +{len(mems) - 15} más antiguas")
        await update.message.reply_text("\n".join(lines))

    async def _cmd_help_prompt(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        await update.message.reply_text(
            "Cómo armar un buen prompt para el Architect\n\n"
            "1. Idea (1 línea) — qué tiene que entregar el equipo, no qué herramientas usa.\n"
            "2. Constraints — USUARIO, EQUIPO (con modelos sugeridos), LECCIONES INICIALES, SCHEDULES, RESTRICCIONES.\n\n"
            "Anti-patrones a evitar:\n"
            "• Restricciones temporales en el body (\"sin Gmail por ahora\") → contaminan al modelo después.\n"
            "• Roles superpuestos entre agentes.\n"
            "• Detalles de implementación (paquetes npm, comandos) → eso lo configurás con /setup_mcp.\n\n"
            "Guía completa con ejemplos copiables: dashboard → /architect → expandí 'Cómo armar un buen prompt'."
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
                # No parse_mode — wizard text is plain to avoid MD parse errors.
                await update.message.reply_text(reply)
            except Exception as e:
                logger.exception("wizard step crashed")
                wizards.cancel_wizard(chat_id)
                await update.message.reply_text(
                    f"El wizard falló inesperadamente: {e}. Cancelado."
                )
            return

        bound = await _resolve_binding_or_default(str(chat_id))
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

    # v0.6 — Non-text dispatch ----------------------------------------------

    async def _download_to_uploads(
        self,
        ctx: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        file_id: str,
        suggested_name: str | None,
    ) -> Path:
        """Persist an attachment under data/uploads/<chat_id>/<timestamp>-<name>.

        Files are kept on disk so the agent can re-read them later (Read tool
        does the right thing with images and PDFs). Old uploads can be swept
        manually from data/uploads/ — we don't auto-rotate.
        """
        repo_root = Path(__file__).resolve().parent.parent.parent
        out_dir = repo_root / "data" / "uploads" / str(chat_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        clean_name = (suggested_name or "file.bin").replace("/", "_").replace("\\", "_")
        out_path = out_dir / f"{ts}-{clean_name}"
        tg_file = await ctx.bot.get_file(file_id)
        await tg_file.download_to_drive(custom_path=str(out_path))
        return out_path

    async def _dispatch_with_prompt(
        self,
        update: Update,
        chat_id: int,
        prompt: str,
    ) -> None:
        """Dispatch an enriched prompt to the bound agent. Mirrors _handle's tail."""
        bound = await _lookup_binding(str(chat_id))
        if not bound:
            await update.message.reply_text(
                f"Este chat ({chat_id}) no está vinculado. Usá /bind <agente> o /agents.",
            )
            return
        placeholder = await update.message.reply_text(
            f"⏳ {bound['agent_name']} procesando…"
        )
        session_id = _CHAT_SESSIONS.get(str(chat_id))
        try:
            run_id = await get_orchestrator().enqueue(RunRequest(
                agent_name=bound["agent_name"],
                prompt=prompt,
                source="telegram",
                session_id=session_id,
                metadata={"chat_id": chat_id, "placeholder_msg_id": placeholder.message_id},
            ))
            _PENDING[run_id] = {
                "chat_id": chat_id,
                "placeholder_msg_id": placeholder.message_id,
            }
        except Exception as e:
            logger.exception("telegram dispatch failed (attachment)")
            await placeholder.edit_text(f"Error: {e}")

    async def _handle_photo(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        # Telegram entrega la foto en varios tamaños; el último es el más grande.
        photos = update.message.photo
        if not photos:
            return
        largest = photos[-1]
        try:
            local_path = await self._download_to_uploads(
                ctx, chat_id, largest.file_id,
                suggested_name=f"photo-{largest.file_unique_id}.jpg",
            )
        except Exception as e:
            logger.exception("telegram photo download failed")
            await update.message.reply_text(f"No pude descargar la imagen: {e}")
            return
        caption = (update.message.caption or "").strip()
        prompt = (
            (f"{caption}\n\n" if caption else "")
            + "El usuario te envió una imagen por Telegram. "
            + "Usá tu herramienta Read para abrirla y describí/respondé según corresponda. "
            + f"Path absoluto del archivo: {local_path}"
        )
        await self._dispatch_with_prompt(update, chat_id, prompt)

    async def _handle_document(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        doc = update.message.document
        if doc is None:
            return
        try:
            local_path = await self._download_to_uploads(
                ctx, chat_id, doc.file_id, suggested_name=doc.file_name,
            )
        except Exception as e:
            logger.exception("telegram document download failed")
            await update.message.reply_text(f"No pude descargar el archivo: {e}")
            return
        caption = (update.message.caption or "").strip()
        kind = classify_path(local_path)

        if kind == "text-extracted":
            text = extract_text(local_path)
            if text is None:
                # Library missing or extraction failed — fall back to path.
                prompt = (
                    (f"{caption}\n\n" if caption else "")
                    + f"El usuario te envió el archivo {local_path.name}. "
                    + f"No pude extraer texto automáticamente. Usá Read si querés inspeccionarlo. "
                    + f"Path: {local_path}"
                )
            else:
                # Trim very long extracted text to avoid blowing the prompt budget.
                snippet = text if len(text) <= 18000 else text[:18000] + "\n\n[...truncado...]"
                prompt = (
                    (f"{caption}\n\n" if caption else "")
                    + f"El usuario te envió el archivo {local_path.name}. "
                    + f"Acá va el contenido extraído (delimitado por triple guión):\n\n"
                    + f"---\n{snippet}\n---\n\n"
                    + "Respondé al usuario sobre este contenido."
                )
        elif kind == "multimodal":
            prompt = (
                (f"{caption}\n\n" if caption else "")
                + f"El usuario te envió un {local_path.suffix.lstrip('.').upper()} "
                + f"({local_path.name}). Usá tu herramienta Read para abrirlo "
                + "(soporta imágenes y PDFs nativos) y respondé al usuario.\n\n"
                + f"Path absoluto: {local_path}"
            )
        else:
            prompt = (
                (f"{caption}\n\n" if caption else "")
                + f"El usuario te envió un archivo de tipo desconocido: {local_path.name}. "
                + f"Probá con tu herramienta Read; si no podés leerlo, decile al usuario qué tipo de archivo te sirve.\n\n"
                + f"Path absoluto: {local_path}"
            )

        await self._dispatch_with_prompt(update, chat_id, prompt)

    async def _handle_voice(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_authorized(update):
            return
        chat_id = update.effective_chat.id
        media = update.message.voice or update.message.audio
        if media is None:
            return

        # Inform the user that transcription may take a moment (and 30-60s
        # the very first time while the model downloads).
        notice = await update.message.reply_text(
            "🎙️ Transcribiendo audio... (la primera vez puede tardar más mientras se descarga el modelo Whisper)"
        )
        try:
            local_path = await self._download_to_uploads(
                ctx, chat_id, media.file_id,
                suggested_name=getattr(media, "file_name", None) or f"voice-{media.file_unique_id}.ogg",
            )
        except Exception as e:
            logger.exception("telegram voice download failed")
            await notice.edit_text(f"No pude descargar el audio: {e}")
            return

        # Lazy import — keeps backend startup fast even if faster-whisper
        # isn't installed yet.
        try:
            from core.attachments import transcribe_audio
        except Exception as e:
            await notice.edit_text(
                f"El módulo de transcripción no cargó: {e}. "
                f"Verificá que faster-whisper esté instalado: pip install faster-whisper"
            )
            return

        # Whisper is sync and CPU-bound; offload to a thread so the event
        # loop doesn't stall while transcription runs.
        try:
            text, detected_lang = await asyncio.to_thread(transcribe_audio, local_path, None)
        except RuntimeError as e:
            await notice.edit_text(str(e))
            return
        except Exception as e:
            logger.exception("whisper transcription failed")
            await notice.edit_text(f"La transcripción falló: {e}")
            return

        if not text.strip():
            await notice.edit_text(
                "No se entendió nada en el audio (silencio o ruido). Probá hablando más cerca del micrófono."
            )
            return

        # Replace the placeholder with the transcript so the user sees what
        # we heard and can trust/correct it.
        await notice.edit_text(
            f"📝 Transcripción ({detected_lang or 'auto'}):\n\n{text}\n\n⏳ procesando…"
        )

        caption = (update.message.caption or "").strip()
        prompt = (
            (f"{caption}\n\n" if caption else "")
            + "El usuario te envió un mensaje de voz por Telegram. "
            + f"Esta es la transcripción literal (idioma: {detected_lang or 'desconocido'}):\n\n"
            + f"\"{text}\"\n\n"
            + "Respondele al usuario como si te hubiera escrito ese texto."
        )
        await self._dispatch_with_prompt(update, chat_id, prompt)

    # Bus consumer -----------------------------------------------------------

    async def _consume_bus(self) -> None:
        """Edit the placeholder message with the final text when the run ends.

        v0.7.1 — auto-restart on inner failures. Until v0.7.0 a single
        exception inside the `async for` killed the consumer for the rest
        of the session, leaving every subsequent run hanging on its
        placeholder. Now we wrap the inner loop and re-subscribe after a
        short backoff so the adapter is self-healing.
        """
        while True:
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
                        # Could be a scheduled run (no Telegram placeholder)
                        # or an event whose placeholder was already consumed.
                        # Log at debug-level so we keep visibility without
                        # spamming. If a Telegram-sourced run loses its
                        # placeholder, the backend log + dashboard still
                        # show the result.
                        logger.debug(
                            "telegram: no pending placeholder for run %s (topic=%s)",
                            run_id, topic,
                        )
                        continue
                    await self._deliver_terminal_event(topic, run_id, evt.data, pend)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "telegram bus consumer crashed; auto-restarting in 2s"
                )
                await asyncio.sleep(2)
                continue

    async def _deliver_terminal_event(
        self,
        topic: str,
        run_id: int,
        data: dict,
        pend: dict,
    ) -> None:
        """Edit (or replace) the placeholder with the run's final state.

        Markdown is best-effort: if Telegram rejects it (escape mistake,
        unbalanced backticks, etc.) we retry in plain text. If even the
        edit itself fails (placeholder lost, permission, race), we fall
        back to sending a fresh message so the user always sees the reply.
        """
        chat_id = pend.get("chat_id")
        msg_id = pend.get("placeholder_msg_id")
        if not self._app or chat_id is None or msg_id is None:
            return

        if topic == "run:completed":
            text = (data.get("final_text") or "").strip() or "(sin texto)"
            cost = data.get("cost_usd", 0.0)
            body = _trim_for_telegram(text)
            suffix = f"\n\n_run #{run_id} · ${cost:.4f}_"
            new_session = data.get("session_id")
            if new_session:
                chat_key = str(chat_id)
                _CHAT_SESSIONS[chat_key] = new_session
                try:
                    await session_store.save("telegram", chat_key, new_session)
                except Exception:
                    logger.exception("session_store.save failed")
            final_text = body + suffix
        elif topic == "run:failed":
            final_text = f"❌ Run #{run_id} falló: {data.get('error', 'unknown')}"
        else:  # cancelled
            final_text = f"⚠️ Run #{run_id} cancelado."

        # 1st attempt: Markdown.
        try:
            await self._app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=final_text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            return
        except Exception as e_md:
            logger.warning(
                "telegram edit Markdown failed for run %s (%s); retrying plain",
                run_id, e_md,
            )
        # 2nd attempt: plain text edit (no parse_mode).
        try:
            await self._app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=final_text,
                disable_web_page_preview=True,
            )
            return
        except Exception as e_plain:
            logger.warning(
                "telegram edit plain failed for run %s (%s); sending fresh message",
                run_id, e_plain,
            )
        # 3rd attempt: send a brand-new message so the user always sees the answer.
        try:
            await self._app.bot.send_message(
                chat_id=chat_id,
                text=final_text,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception(
                "telegram fallback send_message also failed for run %s", run_id
            )

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


async def _resolve_binding_or_default(chat_id_str: str) -> dict | None:
    """Return the agent this chat talks to.

    If there's an explicit binding, use it. Otherwise, if DEFAULT_AGENT is set,
    auto-bind this chat to it so messaging the bot "just works" on first
    contact (Hermes-style: token -> chat, no /bind). The auto-created binding
    persists and shows up in the dashboard, where the user can reassign it.
    When DEFAULT_AGENT is empty, returns None (strict fleet model).
    """
    bound = await _lookup_binding(chat_id_str)
    if bound:
        return bound

    default_name = get_settings().DEFAULT_AGENT.strip()
    if not default_name:
        return None

    async with async_session_factory() as session:
        agent = (await session.execute(
            select(Agent).where(Agent.name == default_name)
        )).scalar_one_or_none()
        if agent is None:
            logger.warning(
                "DEFAULT_AGENT '%s' not found — falling back to /bind prompt",
                default_name,
            )
            return None
        binding = ChannelBinding(
            channel_type="telegram",
            external_id=chat_id_str,
            agent_id=agent.id,
        )
        session.add(binding)
        await session.commit()
        await session.refresh(binding)
        logger.info(
            "auto-bound telegram chat %s to default agent '%s'",
            chat_id_str, default_name,
        )
        return {"agent_name": agent.name, "agent_id": agent.id, "binding_id": binding.id}


def _trim_for_telegram(text: str, max_len: int = 3800) -> str:
    """Telegram message limit is 4096 chars. Leave headroom for the suffix."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 60] + "\n\n…(truncado)"
