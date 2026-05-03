"""Slack adapter — Bolt for Python, socket mode (no public webhook needed).

Capa 13 (channel bindings + reply-on-completion):
- Each Slack channel must be bound to an agent via /api/channels.
- Listens to BOTH `app_mention` (in channels) AND `message.im` (DMs).
- Background bus subscriber posts the run's final text back to the channel
  in a thread under the original message.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from core import runtime_state
from core.adapters.base import Adapter
from core.bus import bus
from core.db import async_session_factory
from core.db.models import Agent, ChannelBinding
from core.runner.orchestrator import RunRequest, get_orchestrator

logger = logging.getLogger(__name__)


# In-flight runs we dispatched: run_id → {channel, thread_ts}.
_PENDING: dict[int, dict] = {}


class SlackAdapter(Adapter):
    name = "slack"

    def __init__(self) -> None:
        self._app = None
        self._handler = None
        self._task: asyncio.Task | None = None
        self._bus_task: asyncio.Task | None = None

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
            await self._dispatch(event, say, kind="mention")

        @app.event("message")
        async def on_message(event, say):
            # Only DMs (channel_type == "im"). Bot's own messages skipped.
            if event.get("subtype") or event.get("bot_id"):
                return
            if event.get("channel_type") != "im":
                return
            await self._dispatch(event, say, kind="dm")

        handler = AsyncSocketModeHandler(app, app_token)
        self._app = app
        self._handler = handler
        self._task = asyncio.create_task(handler.start_async())
        self._bus_task = asyncio.create_task(self._consume_bus())
        logger.info("slack adapter started (socket mode)")

    async def stop(self) -> None:
        if self._bus_task:
            self._bus_task.cancel()
            try:
                await self._bus_task
            except asyncio.CancelledError:
                pass
            self._bus_task = None
        if self._handler:
            try:
                await self._handler.close_async()
            except Exception:
                logger.exception("slack handler close failed")
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

    # Dispatch ---------------------------------------------------------------

    async def _dispatch(self, event: dict, say, *, kind: str) -> None:
        text = (event.get("text") or "").strip()
        if not text:
            return
        # Strip the bot's own user mention from the text in `app_mention` events.
        if kind == "mention":
            # text looks like "<@U0BOTID> hola" — drop the first token.
            parts = text.split(maxsplit=1)
            text = parts[1].strip() if len(parts) > 1 else ""
            if not text:
                await say("¿En qué te ayudo? Envíame algo después del mention.")
                return
        channel = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")  # reply in thread

        # Built-in commands (handle before dispatch).
        lowered = text.lower()
        if lowered.startswith("bind "):
            await self._cmd_bind(text[5:].strip(), channel, thread_ts, say)
            return
        if lowered in ("agents", "list agents"):
            await self._cmd_agents(thread_ts, say)
            return

        bound = await _lookup_binding(str(channel))
        if not bound:
            await say(
                text=f"Este canal (`{channel}`) no está vinculado todavía. "
                     f"Prueba `@bot bind <agente>` o usa el dashboard.",
                thread_ts=thread_ts,
            )
            return

        try:
            placeholder = await say(
                text=f":hourglass_flowing_sand: {bound['agent_name']} pensando…",
                thread_ts=thread_ts,
            )
            run_id = await get_orchestrator().enqueue(RunRequest(
                agent_name=bound["agent_name"],
                prompt=text,
                source="slack",
                metadata={"channel": channel, "thread_ts": thread_ts},
            ))
            _PENDING[run_id] = {
                "channel": channel,
                "thread_ts": thread_ts,
                "placeholder_ts": placeholder.get("ts") if isinstance(placeholder, dict) else None,
            }
        except Exception as e:
            logger.exception("slack dispatch failed")
            await say(text=f"Error: {e}", thread_ts=thread_ts)

    async def _cmd_bind(self, agent_name: str, channel: str, thread_ts: str, say) -> None:
        agent_name = agent_name.strip()
        if not agent_name:
            await say(text="Uso: `bind <nombre-del-agente>`", thread_ts=thread_ts)
            return
        async with async_session_factory() as session:
            agent = (await session.execute(
                select(Agent).where(Agent.name == agent_name)
            )).scalar_one_or_none()
            if agent is None:
                await say(text=f"No existe el agente `{agent_name}`. Prueba `agents`.", thread_ts=thread_ts)
                return
            existing = (await session.execute(
                select(ChannelBinding).where(
                    ChannelBinding.channel_type == "slack",
                    ChannelBinding.external_id == str(channel),
                )
            )).scalar_one_or_none()
            if existing:
                existing.agent_id = agent.id
                action = "reasignado"
            else:
                session.add(ChannelBinding(
                    channel_type="slack",
                    external_id=str(channel),
                    agent_id=agent.id,
                ))
                action = "vinculado"
            await session.commit()
        await say(text=f"Canal {action} a *{agent_name}*. Envíame algo y va.", thread_ts=thread_ts)

    async def _cmd_agents(self, thread_ts: str, say) -> None:
        async with async_session_factory() as session:
            agents = (await session.execute(
                select(Agent).order_by(Agent.name)
            )).scalars().all()
        if not agents:
            await say(text="No hay agentes registrados todavía.", thread_ts=thread_ts)
            return
        lines = [f"• `{a.name}` — {a.description[:60]}" for a in agents]
        await say(text="Agentes:\n" + "\n".join(lines), thread_ts=thread_ts)

    # Bus consumer -----------------------------------------------------------

    async def _consume_bus(self) -> None:
        try:
            async for evt in bus.subscribe("run:*"):
                if not self._app:
                    continue
                if evt.topic not in {"run:completed", "run:failed", "run:cancelled"}:
                    continue
                run_id = evt.data.get("run_id")
                if run_id is None:
                    continue
                pend = _PENDING.pop(run_id, None)
                if not pend:
                    continue
                try:
                    if evt.topic == "run:completed":
                        body = (evt.data.get("final_text") or "(sin texto)").strip()
                        cost = evt.data.get("cost_usd", 0.0)
                        suffix = f"\n\n_run #{run_id} · ${cost:.4f}_"
                        text = _trim_for_slack(body) + suffix
                    elif evt.topic == "run:failed":
                        text = f":x: Run #{run_id} falló: {evt.data.get('error', 'unknown')}"
                    else:
                        text = f":warning: Run #{run_id} cancelado."
                    await self._app.client.chat_postMessage(
                        channel=pend["channel"],
                        thread_ts=pend["thread_ts"],
                        text=text,
                    )
                except Exception:
                    logger.exception("slack reply post failed for run %s", run_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("slack bus consumer crashed")


# Helpers --------------------------------------------------------------------

async def _lookup_binding(channel_id: str) -> dict | None:
    async with async_session_factory() as session:
        b = (await session.execute(
            select(ChannelBinding).where(
                ChannelBinding.channel_type == "slack",
                ChannelBinding.external_id == channel_id,
            )
        )).scalar_one_or_none()
        if b is None:
            return None
        agent = await session.get(Agent, b.agent_id)
        if agent is None:
            return None
        return {"agent_name": agent.name, "agent_id": agent.id, "binding_id": b.id}


def _trim_for_slack(text: str, max_len: int = 3800) -> str:
    """Slack max message is 40k but readability tanks past ~4k. Be kind."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 60] + "\n\n…(truncado)"
