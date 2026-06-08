"""El runner recupera la respuesta cuando el CLI sale con error DESPUÉS de
haber producido texto (caso 'error result: success' / cierre sucio de un MCP).

Un bot de chat debe entregar lo que el agente respondió, no un error críptico.
Pero si NO hubo salida alguna, el fallo es real y debe propagarse.
"""
from __future__ import annotations

import claude_agent_sdk
import pytest

from core.runner.claude_runner import run_agent


class _TextBlock:
    type = "text"
    def __init__(self, text): self.text = text


class AssistantMessage:  # nombre exacto: el runner usa type(msg).__name__
    def __init__(self, text): self.content = [_TextBlock(text)]


def _patch_query(monkeypatch, gen_factory):
    monkeypatch.setattr(claude_agent_sdk, "query", gen_factory)


@pytest.mark.asyncio
async def test_recovers_text_when_cli_errors_after_output(tmp_path, monkeypatch):
    async def fake_query(prompt, options):
        yield AssistantMessage("Hola, esta es mi respuesta.")
        # El CLI sale con error tras responder (lo que vio Edu en run #21).
        raise RuntimeError("Claude Code returned an error result: success")
    _patch_query(monkeypatch, fake_query)

    res = await run_agent(
        agent_name="assistant", prompt="hola",
        workspace_dir=tmp_path, model="claude-sonnet-4-6", run_id=21,
    )
    assert "esta es mi respuesta" in res.final_text


@pytest.mark.asyncio
async def test_reraises_when_no_output(tmp_path, monkeypatch):
    async def fake_query(prompt, options):
        raise RuntimeError("crash real sin respuesta")
        yield  # pragma: no cover  (lo hace generador)
    _patch_query(monkeypatch, fake_query)

    with pytest.raises(RuntimeError, match="crash real"):
        await run_agent(
            agent_name="assistant", prompt="hola",
            workspace_dir=tmp_path, model="claude-sonnet-4-6", run_id=22,
        )
