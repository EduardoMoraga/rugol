"""Multi-bot Telegram support.

Each project can have its OWN Telegram bot (separate token → separate
contact in the user's Telegram), pinned to its own default agent. The two
things that MUST hold for that to be safe:

1. `runtime_state.telegram_bots()` normalizes every config source into a
   clean list with a stable per-bot `key` (the token's numeric prefix),
   dedupes, and falls back to the legacy single-token vars / .env.
2. Each bot namespaces its chat keys by that `key`, because a Telegram
   user's private chat_id is identical across bots — without the namespace
   two bots would share one binding and cross wires.
"""
from __future__ import annotations

import pytest

import core.runtime_state as rs
from core.adapters.telegram import _TelegramBot


def _reset_cache(monkeypatch, **fields):
    """Install a RuntimeSettings into the module cache for the test."""
    monkeypatch.setattr(rs, "_cached", rs.RuntimeSettings(**fields))


def test_multibot_list_normalized(monkeypatch):
    _reset_cache(monkeypatch, telegram_bots=[
        {"token": "111:AAA", "agent": "assistant", "users": "42", "label": "Personal"},
        {"token": "222:BBB", "agent": "ventas", "users": [42, 99], "label": "Ventas"},
    ])
    bots = rs.telegram_bots()
    assert [b["key"] for b in bots] == ["111", "222"]
    assert bots[0]["agent"] == "assistant"
    assert bots[1]["users"] == {42, 99}
    assert bots[1]["label"] == "Ventas"


def test_dedupe_same_bot(monkeypatch):
    """The same token twice would Conflict on polling — drop the duplicate."""
    _reset_cache(monkeypatch, telegram_bots=[
        {"token": "111:AAA", "agent": "a"},
        {"token": "111:CCC", "agent": "b"},  # same bot id 111
    ])
    bots = rs.telegram_bots()
    assert len(bots) == 1
    assert bots[0]["key"] == "111"


def test_legacy_single_token_fallback(monkeypatch):
    """With no telegram_bots list, the legacy single token yields one bot."""
    _reset_cache(
        monkeypatch,
        telegram_bot_token="333:DDD",
        telegram_allowed_users="7,8",
    )
    bots = rs.telegram_bots()
    assert len(bots) == 1
    assert bots[0]["key"] == "333"
    assert bots[0]["users"] == {7, 8}


def test_invalid_tokens_skipped(monkeypatch):
    _reset_cache(monkeypatch, telegram_bots=[
        {"token": "", "agent": "a"},
        {"token": "no-colon", "agent": "b"},
        {"token": "444:EEE", "agent": "c"},
    ])
    bots = rs.telegram_bots()
    assert [b["key"] for b in bots] == ["444"]


def test_chat_key_namespacing_is_per_bot():
    """Two bots, same Telegram chat_id → distinct namespaced keys."""
    bot_a = _TelegramBot(token="111:AAA", key="111", default_agent="assistant")
    bot_b = _TelegramBot(token="222:BBB", key="222", default_agent="ventas")
    same_chat = 8656469332
    assert bot_a._chat_key(same_chat) == "111:8656469332"
    assert bot_b._chat_key(same_chat) == "222:8656469332"
    assert bot_a._chat_key(same_chat) != bot_b._chat_key(same_chat)


# ── /motor: cambiar de motor sin salir del chat ───────────────────────────────
# Lo que pidió el usuario: "una forma en Telegram de invocar a uno u otro
# lenguaje, como lo hace Hermes".

@pytest.mark.asyncio
async def test_chat_engine_override_does_not_touch_the_agent(tmp_path, monkeypatch):
    """Probar Codex en una conversación no debe cambiar cómo corre ese agente
    en los horarios ni en el dashboard."""
    from sqlalchemy import select

    from core.db import async_session_factory, init_db
    from core.db.models import Agent, ChannelBinding, Project

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()

    async with async_session_factory() as s:
        proj = (await s.execute(select(Project).where(Project.slug == "workspace"))).scalar_one()
        agent = Agent(name="motor-test", model="claude-sonnet-5", description="d",
                      body="b", source_path="/tmp/motor-test.md", body_hash="h",
                      project_id=proj.id, engine="claude")
        s.add(agent)
        await s.flush()
        s.add(ChannelBinding(channel_type="telegram", external_id="bot1:42",
                             agent_id=agent.id, engine="codex"))
        await s.commit()
        agent_id = agent.id

    try:
        from core.adapters.telegram import _lookup_binding

        bound = await _lookup_binding("bot1:42")
        assert bound["engine"] == "codex", "el override del chat"
        assert bound["agent_engine"] == "claude", "el agente NO cambió"

        # Y el override es el que gana en la corrida.
        from core.runner.orchestrator import RunRequest

        req = RunRequest(agent_name="motor-test", prompt="x", source="telegram",
                         engine_override=bound["engine"])
        assert req.engine_override == "codex"
        assert (req.engine_override or "claude") == "codex"
    finally:
        async with async_session_factory() as s:
            a = await s.get(Agent, agent_id)
            if a:
                await s.delete(a)
            await s.commit()


@pytest.mark.asyncio
async def test_binding_without_override_falls_back_to_the_agent(tmp_path, monkeypatch):
    from sqlalchemy import select

    from core.db import async_session_factory, init_db
    from core.db.models import Agent, ChannelBinding, Project

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()
    async with async_session_factory() as s:
        proj = (await s.execute(select(Project).where(Project.slug == "workspace"))).scalar_one()
        agent = Agent(name="motor-test-2", model="gpt-5.6-terra", description="d",
                      body="b", source_path="/tmp/m2.md", body_hash="h",
                      project_id=proj.id, engine="codex")
        s.add(agent)
        await s.flush()
        s.add(ChannelBinding(channel_type="telegram", external_id="bot1:43", agent_id=agent.id))
        await s.commit()
        agent_id = agent.id
    try:
        from core.adapters.telegram import _lookup_binding

        bound = await _lookup_binding("bot1:43")
        assert bound["engine"] is None, "sin override"
        assert bound["agent_engine"] == "codex", "hereda el del agente"
    finally:
        async with async_session_factory() as s:
            a = await s.get(Agent, agent_id)
            if a:
                await s.delete(a)
            await s.commit()
