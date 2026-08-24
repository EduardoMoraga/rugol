"""Soul Layer tests (ADR-006).

Covers:
- identity block renders for new and seasoned agents
- auto-memory rules are present and mention the four kinds
- soul context composes both pieces
- soul MCP server exposes the three tools by name
- save_memory tool writes a real file via the existing memory store
- list_my_memories surfaces what was just saved
- forget_memory removes it
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.memory import memory_dir
from core.soul import build_soul_context
from core.soul.auto_memory import AUTO_MEMORY_RULES
from core.soul.identity import build_identity_block

AGENT = "test-soul-agent"


@pytest.fixture(autouse=True)
def _clean_agent_memory():
    """Each test starts with no memory for the test agent."""
    d = memory_dir(AGENT)
    if d.exists():
        shutil.rmtree(d)
    yield
    if d.exists():
        shutil.rmtree(d)


def test_identity_block_fresh_agent():
    block = build_identity_block(AGENT, "A test agent.", run_count=0)
    assert AGENT in block
    assert "A test agent." in block
    # Fresh agent → no Historial line
    assert "Historial" not in block


def test_identity_block_seasoned_agent():
    block = build_identity_block(
        AGENT, "A test agent.", run_count=12, last_run_at_iso="2026-05-10T09:00:00+00:00"
    )
    assert "12 run" in block
    assert "2026-05-10T09:00:00+00:00" in block


def test_identity_block_truncates_long_description():
    long_desc = "x" * 500
    block = build_identity_block(AGENT, long_desc)
    assert "…" in block or len(block) < 600


def test_auto_memory_rules_mention_four_kinds():
    rules = AUTO_MEMORY_RULES
    for kind in ("user", "feedback", "project", "reference"):
        assert kind in rules, f"auto-memory rules missing kind: {kind}"
    # And the three tools
    for tool in ("save_memory", "list_my_memories", "forget_memory"):
        assert tool in rules


def test_soul_context_composes_identity_and_rules():
    ctx = build_soul_context(AGENT, "desc", run_count=1)
    assert "Tu identidad" in ctx
    assert "Cómo usar tu memoria persistente" in ctx

# ── Memoria: un solo camino ───────────────────────────────────────────────────
# El servidor MCP in-process (core/soul/tools.py) se eliminó en 2.0. Había DOS
# implementaciones de memoria —una para el runtime, otra para el checkpoint
# automático— y dos implementaciones de lo mismo se separan con el tiempo. Ahora
# todo pasa por core/mcp/memory_service, que es lo que usan los dos motores.

def test_the_in_process_memory_server_is_gone():
    """Si alguien lo reintroduce, esto lo cuenta."""
    import core.soul as soul

    assert not hasattr(soul, "build_soul_mcp_server")
    assert not hasattr(soul, "SOUL_TOOL_NAMES")
    assert not (Path(soul.__file__).parent / "tools.py").exists()


def test_memory_tool_names_target_the_shared_service():
    from core.mcp.memory_service import MCP_SERVER_NAME, MEMORY_TOOL_NAMES

    assert MCP_SERVER_NAME == "rugol-memory"
    assert len(MEMORY_TOOL_NAMES) == 4
    for name in MEMORY_TOOL_NAMES:
        assert name.startswith(f"mcp__{MCP_SERVER_NAME}__")


def test_the_checkpoint_writes_to_the_agents_store_not_the_checkpoints(tmp_path, monkeypatch):
    """La CORRIDA del checkpoint se llama "<agente>-checkpoint" para no contar
    como corrida del agente. Pero la memoria tiene que caer en el almacén del
    AGENTE — si el token se emitiera con el nombre sufijado, cada auto-memoria
    terminaría en una carpeta fantasma."""
    import inspect

    from core.mcp.memory_service import issue_token, resolve_token
    from core.soul import checkpoint

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    fuente = inspect.getsource(checkpoint)

    assert "issue_token(agent_name" in fuente, (
        "el token debe emitirse con el nombre SIN sufijo"
    )
    assert 'issue_token(f"{agent_name}-checkpoint"' not in fuente
    assert "revoke_token(memory_token)" in fuente, "el token debe revocarse al terminar"

    # Y la garantía misma: el token resuelve al agente, no al checkpoint.
    token = issue_token("mi-agente")
    assert resolve_token(token) == "mi-agente"


