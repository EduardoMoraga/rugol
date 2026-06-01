"""In-process MCP server: gives every agent the ability to send Telegram
messages without having to call /bin/python telegram_send.py via Bash.

Surfaces a single tool, `send_telegram_message`, that posts to the bot's
chat. The bot token is read from settings; if it's not configured, the
server is not built (and the tool simply doesn't exist for the agent).

The chat_id can be:
- A literal Telegram chat id (number, possibly negative for groups).
- The string "default" — resolves to the most recently active channel
  binding the user has set up via `/bind` on Telegram.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig

from core.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_MCP_NAME = "rugol-telegram"
TELEGRAM_TOOL_NAMES: tuple[str, ...] = (
    f"mcp__{TELEGRAM_MCP_NAME}__send_telegram_message",
)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _text_result(text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": is_error}


async def _resolve_default_chat_id() -> str | None:
    """When chat_id='default', try the most recent Telegram channel binding."""
    try:
        from sqlalchemy import desc, select
        from core.db import async_session_factory
        from core.db.models import ChannelBinding
        async with async_session_factory() as session:
            row = (await session.execute(
                select(ChannelBinding)
                .where(ChannelBinding.channel_type == "telegram")
                .order_by(desc(ChannelBinding.id))
                .limit(1)
            )).scalar_one_or_none()
            return row.external_id if row else None
    except Exception:
        logger.exception("could not resolve default Telegram chat_id")
        return None


def build_telegram_mcp_server() -> McpSdkServerConfig | None:
    """Build the Telegram MCP server, or None if no bot token is configured."""
    settings = get_settings()
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        return None

    @tool(
        "send_telegram_message",
        "Send a text message to a Telegram chat via the Rugol bot. "
        "Use `chat_id=\"default\"` to reach the user on their primary "
        "Telegram channel (the most recent binding). Markdown supported "
        "when parse_mode='Markdown'.",
        {
            "chat_id": str,
            "text": str,
            "parse_mode": str,
        },
    )
    async def send_telegram_message(args: dict[str, Any]) -> dict[str, Any]:
        try:
            chat_id = str(args.get("chat_id") or "").strip()
            text = (args.get("text") or "").strip()
            parse_mode = (args.get("parse_mode") or "").strip() or None
            if not chat_id or not text:
                return _text_result(
                    "send_telegram_message needs both chat_id and text.",
                    is_error=True,
                )
            if chat_id.lower() == "default":
                resolved = await _resolve_default_chat_id()
                if not resolved:
                    return _text_result(
                        "No default Telegram binding found. Run /bind on the "
                        "bot from your chat first, or pass an explicit chat_id.",
                        is_error=True,
                    )
                chat_id = resolved
            payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            url = _TELEGRAM_API.format(token=token)
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(url, json=payload)
            if r.status_code != 200:
                logger.warning(
                    "telegram send failed status=%s body=%s",
                    r.status_code, r.text[:300],
                )
                return _text_result(
                    f"Telegram API returned {r.status_code}: {r.text[:200]}",
                    is_error=True,
                )
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            mid = (data.get("result") or {}).get("message_id")
            return _text_result(
                f"Sent (message_id={mid}, chat_id={chat_id})."
                if mid else f"Sent to {chat_id}."
            )
        except Exception as e:
            logger.exception("send_telegram_message failed")
            return _text_result(f"send_telegram_message error: {e}", is_error=True)

    return create_sdk_mcp_server(
        name=TELEGRAM_MCP_NAME,
        version="1.0.0",
        tools=[send_telegram_message],
    )
