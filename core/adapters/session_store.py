"""Persistent storage for conversational session_ids per chat / channel.

The Telegram and Slack adapters both need the same thing: remember the
last `session_id` for each chat so that, after an uvicorn restart, the
agent picks up the conversation where it left off instead of starting
fresh ("no tengo contexto de la conversación anterior" — the bug Edu
hit before this existed).

Backed by the `chat_sessions` table (see core/db/models.py::ChatSession).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select

from core.db import async_session_factory
from core.db.models import ChatSession

logger = logging.getLogger(__name__)


async def load_all(channel_type: str) -> dict[str, str]:
    """Return {external_id: session_id} for warm-up at adapter start."""
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(ChatSession).where(ChatSession.channel_type == channel_type)
            )
        ).scalars().all()
        return {r.external_id: r.session_id for r in rows}


async def save(channel_type: str, external_id: str, session_id: str) -> None:
    """Upsert (channel_type, external_id) → session_id with current timestamp."""
    if not session_id:
        return
    async with async_session_factory() as session:
        existing = (
            await session.execute(
                select(ChatSession).where(
                    ChatSession.channel_type == channel_type,
                    ChatSession.external_id == external_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.session_id = session_id
            existing.last_used_at = datetime.now(UTC)
        else:
            session.add(
                ChatSession(
                    channel_type=channel_type,
                    external_id=external_id,
                    session_id=session_id,
                )
            )
        await session.commit()


async def delete_one(channel_type: str, external_id: str) -> bool:
    """Drop the row for that chat. Returns True if a row existed."""
    async with async_session_factory() as session:
        result = await session.execute(
            delete(ChatSession).where(
                ChatSession.channel_type == channel_type,
                ChatSession.external_id == external_id,
            )
        )
        await session.commit()
        return (result.rowcount or 0) > 0
