"""Channel adapters — bridge external chat platforms to the orchestrator."""
from .base import Adapter
from .telegram import TelegramAdapter

__all__ = ["Adapter", "TelegramAdapter"]
