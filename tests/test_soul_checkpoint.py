"""Soul-1.5 — auto memory checkpoint tests.

We don't exercise the LLM call itself (that needs API). We exercise the
gating: when should the checkpoint fire? when should it skip? The
checkpoint's prompt-rendering correctness is covered by the smoke
import in test_smoke.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from core.runner.orchestrator import RuntimeOrchestrator
from core.soul.checkpoint import run_checkpoint


@pytest.mark.asyncio
async def test_checkpoint_skips_when_disabled(monkeypatch, tmp_path):
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_AUTO_CHECKPOINT_ENABLED", False, raising=False
    )
    ran = await run_checkpoint(
        agent_name="x",
        user_prompt="hola",
        agent_response="¡hola!",
        workspace_dir=tmp_path,
    )
    assert ran is False


@pytest.mark.asyncio
async def test_checkpoint_skips_when_prompts_empty(monkeypatch, tmp_path):
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_AUTO_CHECKPOINT_ENABLED", True, raising=False
    )
    ran = await run_checkpoint(
        agent_name="x", user_prompt="", agent_response="resp",
        workspace_dir=tmp_path,
    )
    assert ran is False
    ran = await run_checkpoint(
        agent_name="x", user_prompt="hola", agent_response="",
        workspace_dir=tmp_path,
    )
    assert ran is False


def test_orchestrator_skips_checkpoint_for_advocate_source(tmp_path):
    """Devil's advocate runs must NOT trigger checkpoints."""
    orch = RuntimeOrchestrator(max_concurrent=1, workspace_dir=tmp_path)
    spawned: list = []
    with patch("core.runner.orchestrator.asyncio.create_task") as mock_create:
        mock_create.side_effect = lambda coro: spawned.append(coro) or None
        orch._maybe_spawn_checkpoint(
            agent_name="gugol", source="devils-advocate",
            user_prompt="hello", agent_response="world",
            advocate_for_run_id=None,
        )
    assert mock_create.call_count == 0


def test_orchestrator_skips_checkpoint_when_advocate_for_run_id_set(tmp_path):
    """A run that IS a devil's advocate output should not checkpoint."""
    orch = RuntimeOrchestrator(max_concurrent=1, workspace_dir=tmp_path)
    with patch("core.runner.orchestrator.asyncio.create_task") as mock_create:
        orch._maybe_spawn_checkpoint(
            agent_name="gugol", source="telegram",
            user_prompt="x", agent_response="y",
            advocate_for_run_id=42,
        )
    assert mock_create.call_count == 0


def test_orchestrator_skips_checkpoint_for_checkpoint_runs(tmp_path):
    """Prevent checkpoint-of-checkpoint recursion."""
    orch = RuntimeOrchestrator(max_concurrent=1, workspace_dir=tmp_path)
    with patch("core.runner.orchestrator.asyncio.create_task") as mock_create:
        orch._maybe_spawn_checkpoint(
            agent_name="gugol-checkpoint", source="telegram",
            user_prompt="x", agent_response="y",
            advocate_for_run_id=None,
        )
    assert mock_create.call_count == 0


def test_orchestrator_skips_checkpoint_for_schedule_source_by_default(
    monkeypatch, tmp_path,
):
    """Scheduled runs are unattended — no human feedback to capture."""
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_AUTO_CHECKPOINT_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        config.get_settings(),
        "SOUL_AUTO_CHECKPOINT_SKIP_SOURCES",
        "devils-advocate,schedule",
        raising=False,
    )
    orch = RuntimeOrchestrator(max_concurrent=1, workspace_dir=tmp_path)
    with patch("core.runner.orchestrator.asyncio.create_task") as mock_create:
        orch._maybe_spawn_checkpoint(
            agent_name="delichul", source="schedule",
            user_prompt="run morning brief", agent_response="done",
            advocate_for_run_id=None,
        )
    assert mock_create.call_count == 0


def test_orchestrator_fires_checkpoint_for_telegram_source(
    monkeypatch, tmp_path,
):
    """Conversational sources should trigger the checkpoint."""
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_AUTO_CHECKPOINT_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        config.get_settings(),
        "SOUL_AUTO_CHECKPOINT_SKIP_SOURCES",
        "devils-advocate,schedule",
        raising=False,
    )
    orch = RuntimeOrchestrator(max_concurrent=1, workspace_dir=tmp_path)
    def _swallow(coro):
        coro.close()
        return None

    with patch("core.runner.orchestrator.asyncio.create_task", side_effect=_swallow) as mock_create:
        orch._maybe_spawn_checkpoint(
            agent_name="gugol", source="telegram",
            user_prompt="recuerda mi preferencia", agent_response="ok",
            advocate_for_run_id=None,
        )
    assert mock_create.call_count == 1


def test_orchestrator_fires_checkpoint_for_dashboard_source(
    monkeypatch, tmp_path,
):
    from core import config
    monkeypatch.setattr(
        config.get_settings(), "SOUL_AUTO_CHECKPOINT_ENABLED", True, raising=False
    )
    monkeypatch.setattr(
        config.get_settings(),
        "SOUL_AUTO_CHECKPOINT_SKIP_SOURCES",
        "devils-advocate,schedule",
        raising=False,
    )
    orch = RuntimeOrchestrator(max_concurrent=1, workspace_dir=tmp_path)
    def _swallow(coro):
        coro.close()
        return None

    with patch("core.runner.orchestrator.asyncio.create_task", side_effect=_swallow) as mock_create:
        orch._maybe_spawn_checkpoint(
            agent_name="moragent", source="dashboard",
            user_prompt="brief de hoy", agent_response="acá va",
            advocate_for_run_id=None,
        )
    assert mock_create.call_count == 1


# ── El checkpoint no puede duplicar lo que el agente ya guardó ────────────────
# Medido en vivo: el agente guardó "reportes BI jueves 10h · Versuni en miles"
# durante el run (tiene las mismas herramientas), y el checkpoint guardó lo
# mismo 23 segundos después con otro nombre. Dos memorias del mismo hecho
# degradan el recall: la lista crece y las descripciones compiten.

def test_the_checkpoint_prompt_requires_listing_first():
    from core.soul.checkpoint import _CHECKPOINT_PROMPT

    assert "list_my_memories" in _CHECKPOINT_PROMPT
    bajo = _CHECKPOINT_PROMPT.lower()
    # La instrucción de listar tiene que venir ANTES de la de guardar.
    assert bajo.index("list_my_memories") < bajo.index("save_memory"), (
        "si la orden de listar aparece después de la de guardar, el modelo "
        "guarda primero y pregunta después"
    )
    assert "duplicado" in bajo or "de nuevo" in bajo
    assert "forget_memory" in _CHECKPOINT_PROMPT, (
        "si lo guardado es peor, hay que poder reemplazarlo en vez de sumar"
    )
