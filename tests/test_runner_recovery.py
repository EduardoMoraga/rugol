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


class ResultMessage:  # idem: el runner despacha por type(msg).__name__
    def __init__(self, session_id, result=None):
        self.session_id = session_id
        self.usage = {"input_tokens": 1, "output_tokens": 1}
        self.total_cost_usd = 0.0
        self.result = result


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


# ── Sesión perdida: el chat tiene que curarse solo ───────────────────────────
# El bug real: un chat de Telegram guardó un session_id en julio, el archivo de
# esa conversación desapareció del disco, y desde entonces CADA mensaje falló
# con "Command failed with exit code 1". Dos meses de chat inservible.

def test_detects_a_lost_session():
    from core.runner.claude_runner import _looks_like_a_lost_session

    assert _looks_like_a_lost_session(
        RuntimeError("No conversation found with session ID: 908bc41c-020f")
    )
    assert _looks_like_a_lost_session(
        RuntimeError("Command failed with exit code 1 (exit code: 1)\n"
                     "Error output: Check stderr output for details")
    )
    # Un fallo de verdad NO debe disfrazarse de sesión perdida.
    assert not _looks_like_a_lost_session(RuntimeError("rate limit exceeded"))
    assert not _looks_like_a_lost_session(RuntimeError("401 unauthorized"))


@pytest.mark.asyncio
async def test_retries_with_a_fresh_session_and_returns_the_new_id(tmp_path, monkeypatch):
    attempts: list[str | None] = []

    def gen_factory(prompt, options):
        attempts.append(options.resume)
        async def gen():
            if options.resume is not None:
                raise RuntimeError(
                    f"No conversation found with session ID: {options.resume}"
                )
            yield AssistantMessage("Hola de nuevo.")
            yield ResultMessage("sesion-nueva-456")
        return gen()

    _patch_query(monkeypatch, gen_factory)

    result = await run_agent(
        agent_name="a", prompt="hola", workspace_dir=tmp_path,
        model="claude-sonnet-5", session_id="sesion-muerta-123",
    )
    assert attempts == ["sesion-muerta-123", None], "primero resume, después sesión nueva"
    assert result.final_text == "Hola de nuevo."
    assert result.session_id == "sesion-nueva-456", (
        "hay que devolver el id nuevo: si devolvemos el muerto, el próximo "
        "mensaje vuelve a fallar y el chat sigue roto"
    )


@pytest.mark.asyncio
async def test_a_real_failure_is_not_retried(tmp_path, monkeypatch):
    """Un 401 no se arregla reintentando sin sesión: hay que propagarlo."""
    attempts: list[str | None] = []

    def gen_factory(prompt, options):
        attempts.append(options.resume)
        async def gen():
            raise RuntimeError("API Error: 401 unauthorized")
            yield  # pragma: no cover
        return gen()

    _patch_query(monkeypatch, gen_factory)

    with pytest.raises(RuntimeError, match="401"):
        await run_agent(
            agent_name="a", prompt="hola", workspace_dir=tmp_path,
            model="claude-sonnet-5", session_id="s-1",
        )
    assert len(attempts) == 1, "no debe reintentar"


@pytest.mark.asyncio
async def test_no_retry_when_there_was_no_session(tmp_path, monkeypatch):
    attempts: list[str | None] = []

    def gen_factory(prompt, options):
        attempts.append(options.resume)
        async def gen():
            raise RuntimeError("Command failed with exit code 1\nCheck stderr output")
            yield  # pragma: no cover
        return gen()

    _patch_query(monkeypatch, gen_factory)
    with pytest.raises(RuntimeError):
        await run_agent(agent_name="a", prompt="x", workspace_dir=tmp_path,
                        model="claude-sonnet-5", session_id=None)
    assert len(attempts) == 1
