"""Common interface for chat adapters (Telegram, Slack, future Discord/MSTeams)."""
from __future__ import annotations

import abc


class Adapter(abc.ABC):
    """An adapter listens on a chat channel and routes messages to the orchestrator."""

    name: str

    @abc.abstractmethod
    async def start(self) -> None: ...

    @abc.abstractmethod
    async def stop(self) -> None: ...

    @abc.abstractmethod
    async def publish(self, channel_id: str, text: str) -> None:
        """Send a message back to the channel."""
