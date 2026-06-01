"""Honcho adapter — shared agent-to-agent memory backed by Plastic Labs' Honcho.

Honcho is an external service that stores observations made by *peers*
(agents, end-users) in *sessions* and lets any caller ask natural-language
questions about the accumulated knowledge. Unlike the Soul Layer (which
gives every agent a private, on-disk memory scoped to its own name), Honcho
is a shared graph: agent A can ask "what does the team know about peer X?"
and Honcho synthesises an answer from everything A, B and C have observed.

This adapter is **opt-in**. With HONCHO_ENABLED=false (default) the SDK is
never imported, so Rugol runs perfectly without an internet connection
or a Honcho account. When enabled, missing credentials raise on first use
rather than at import time, so the rest of the stack keeps booting.

See ADR-009 for the full rationale and the Soul-vs-Honcho line.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)


class HonchoDisabledError(RuntimeError):
    """Raised when a Honcho call is attempted but the integration is off."""


class HonchoUnavailableError(RuntimeError):
    """Raised when honcho-ai is not installed but the user enabled the feature."""


# Backwards-compatible aliases — the short names read more naturally inside
# narrow except clauses, and the tests + tool layer already use them.
HonchoDisabled = HonchoDisabledError
HonchoUnavailable = HonchoUnavailableError


@dataclass(frozen=True)
class HonchoConfig:
    api_key: str
    workspace_id: str
    environment: str
    default_session_id: str


def _load_config() -> HonchoConfig:
    s = get_settings()
    if not s.HONCHO_ENABLED:
        raise HonchoDisabledError(
            "Honcho is disabled. Set HONCHO_ENABLED=true and HONCHO_API_KEY "
            "in your .env to use shared memory tools."
        )
    if not s.HONCHO_API_KEY:
        raise HonchoDisabledError(
            "HONCHO_ENABLED=true but HONCHO_API_KEY is empty. Get a key at "
            "honcho.dev and add it to your .env."
        )
    return HonchoConfig(
        api_key=s.HONCHO_API_KEY,
        workspace_id=s.HONCHO_WORKSPACE_ID or "rugol-default",
        environment=s.HONCHO_ENVIRONMENT or "production",
        default_session_id=s.HONCHO_DEFAULT_SESSION or date.today().isoformat(),
    )


@lru_cache(maxsize=1)
def _client() -> Any:
    cfg = _load_config()
    try:
        from honcho import Honcho  # type: ignore[import-not-found]
    except ImportError as e:
        raise HonchoUnavailableError(
            "honcho-ai is not installed. Run `pip install honcho-ai` in the "
            "core venv (or rebuild the Docker image) to enable shared memory."
        ) from e
    logger.info(
        "honcho: initialising client workspace=%s env=%s",
        cfg.workspace_id,
        cfg.environment,
    )
    return Honcho(
        api_key=cfg.api_key,
        environment=cfg.environment,
        workspace_id=cfg.workspace_id,
    )


def _session_id(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return _load_config().default_session_id


def save_observation(
    *,
    content: str,
    peer_id: str,
    session_id: str | None = None,
) -> dict[str, str]:
    """Attribute `content` to `peer_id` inside `session_id` (default: today)."""
    if not content.strip():
        raise ValueError("content is empty")
    if not peer_id.strip():
        raise ValueError("peer_id is empty")
    sid = _session_id(session_id)
    h = _client()
    peer = h.peer(peer_id.strip())
    session = h.session(sid)
    session.add_messages([peer.message(content.strip())])
    logger.info("honcho: saved observation peer=%s session=%s", peer_id, sid)
    return {"peer_id": peer_id, "session_id": sid}


def query_synthesis(*, query: str, peer_id: str) -> str:
    """Ask `peer_id` a natural-language question; Honcho returns a synthesised reply."""
    if not query.strip():
        raise ValueError("query is empty")
    if not peer_id.strip():
        raise ValueError("peer_id is empty")
    h = _client()
    peer = h.peer(peer_id.strip())
    response = peer.chat(query.strip())
    return str(response) if response is not None else ""


def search_raw(*, query: str, limit: int = 5, session_id: str | None = None) -> list[str]:
    """Semantic search across raw messages in `session_id` (default: today).

    Returns at most `limit` snippets. Honcho exposes search on sessions in
    v2 of the SDK; if that surface is missing on the installed version we
    fall back to peer.chat() with a search-style prompt so callers still
    get something useful.
    """
    if not query.strip():
        raise ValueError("query is empty")
    sid = _session_id(session_id)
    h = _client()
    session = h.session(sid)
    search_fn = getattr(session, "search", None)
    if callable(search_fn):
        try:
            raw = search_fn(query.strip(), limit=limit)
        except TypeError:
            raw = search_fn(query.strip())
        return _flatten_search_results(raw, limit)
    logger.warning("honcho: session.search() not available — falling back to chat()")
    return [query_synthesis(query=query, peer_id="rugol")]


def _flatten_search_results(raw: Any, limit: int) -> list[str]:
    out: list[str] = []
    items = raw if isinstance(raw, list) else getattr(raw, "items", None) or []
    for item in items[:limit]:
        text = getattr(item, "content", None) or getattr(item, "text", None) or str(item)
        out.append(text)
    return out


def reset_client_cache() -> None:
    """Clear the cached client — useful in tests when settings change.

    Safe to call even if `_client` was monkey-patched away from its
    lru_cache-decorated original (which is what most unit tests do).
    """
    clear = getattr(_client, "cache_clear", None)
    if callable(clear):
        clear()
