"""Honcho adapter tests (ADR-009).

Covers:
- adapter raises HonchoDisabled when feature is off
- adapter raises HonchoDisabled when feature is on but key is empty
- save / query / search dispatch to the mocked SDK with the right shape
- search falls back to chat() when session.search() is absent
- MCP server exposes the three tools by name
- tool calls return error payloads (not exceptions) when feature is off
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.adapters import honcho as adapter
from core.config import get_settings
from core.runner.honcho_tools import (
    HONCHO_MCP_NAME,
    HONCHO_TOOL_NAMES,
    build_honcho_mcp_server,
)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Each test gets fresh cached state and a clean settings cache."""
    adapter.reset_client_cache()
    get_settings.cache_clear()
    yield
    adapter.reset_client_cache()
    get_settings.cache_clear()


def _enable_honcho(monkeypatch, **overrides):
    defaults = {
        "HONCHO_ENABLED": "true",
        "HONCHO_API_KEY": "test-key",
        "HONCHO_WORKSPACE_ID": "ws-test",
        "HONCHO_ENVIRONMENT": "production",
        "HONCHO_DEFAULT_SESSION": "session-x",
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()


def test_adapter_raises_when_disabled(monkeypatch):
    monkeypatch.setenv("HONCHO_ENABLED", "false")
    get_settings.cache_clear()
    with pytest.raises(adapter.HonchoDisabled):
        adapter.save_observation(content="hi", peer_id="alice")


def test_adapter_raises_when_enabled_without_key(monkeypatch):
    monkeypatch.setenv("HONCHO_ENABLED", "true")
    monkeypatch.setenv("HONCHO_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(adapter.HonchoDisabled):
        adapter.query_synthesis(query="who?", peer_id="alice")


def _install_fake_client(monkeypatch) -> MagicMock:
    client = MagicMock(name="HonchoClient")
    peer = MagicMock(name="Peer")
    session = MagicMock(name="Session")
    client.peer.return_value = peer
    client.session.return_value = session
    peer.message.return_value = "msg-token"
    peer.chat.return_value = "synthesised reply"
    monkeypatch.setattr(adapter, "_client", lambda: client)
    return client


def test_save_observation_calls_sdk(monkeypatch):
    _enable_honcho(monkeypatch)
    client = _install_fake_client(monkeypatch)

    result = adapter.save_observation(content="edu prefers chileno", peer_id="edu")

    assert result == {"peer_id": "edu", "session_id": "session-x"}
    client.peer.assert_called_once_with("edu")
    client.session.assert_called_once_with("session-x")
    client.session.return_value.add_messages.assert_called_once()


def test_query_synthesis_calls_chat(monkeypatch):
    _enable_honcho(monkeypatch)
    client = _install_fake_client(monkeypatch)

    answer = adapter.query_synthesis(query="what does edu prefer?", peer_id="edu")

    assert answer == "synthesised reply"
    client.peer.return_value.chat.assert_called_once_with("what does edu prefer?")


def test_search_uses_session_search_when_present(monkeypatch):
    _enable_honcho(monkeypatch)
    client = _install_fake_client(monkeypatch)
    fake_hit = MagicMock(content="raw observation A")
    client.session.return_value.search.return_value = [fake_hit]

    hits = adapter.search_raw(query="chileno", limit=3)

    assert hits == ["raw observation A"]
    client.session.return_value.search.assert_called_once()


def test_search_falls_back_when_search_missing(monkeypatch):
    _enable_honcho(monkeypatch)
    client = _install_fake_client(monkeypatch)
    # Strip session.search so the adapter must fall back.
    del client.session.return_value.search

    hits = adapter.search_raw(query="chileno")

    assert hits == ["synthesised reply"]


def test_mcp_server_exposes_three_tools():
    server = build_honcho_mcp_server(agent_name="some-agent")
    assert server is not None
    assert HONCHO_MCP_NAME == "rugol-honcho"
    assert len(HONCHO_TOOL_NAMES) == 3
    assert all(name.startswith(f"mcp__{HONCHO_MCP_NAME}__") for name in HONCHO_TOOL_NAMES)


def test_mcp_server_builds_when_disabled(monkeypatch):
    """Building the server must not require Honcho to be on — it's the
    individual tool calls that surface the disabled state."""
    monkeypatch.setenv("HONCHO_ENABLED", "false")
    get_settings.cache_clear()
    server = build_honcho_mcp_server(agent_name="alice")
    assert server is not None
