"""El bucle self-improving: qué corridas mira y cada cuánto se dispara.

Dos defectos encontrados auditando, ambos en la feature que el usuario más
valora:

· El reflector recibía corridas `interrupted`. Una `interrupted` es un corte de
  luz. Mostrárselas lo hace proponer cambios de prompt para arreglar un reinicio
  de la máquina: el bucle aprendería la lección equivocada.

· La condición "cada 10 corridas" era en realidad "siempre, en cuanto tenés 10".
  Al rechazar una propuesta, la siguiente reflexión salía en el mensaje
  siguiente. Cuesta plata y molesta.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from core.db import async_session_factory, init_db
from core.db.models import Agent, Improvement, Project, Run


async def _agente(nombre: str) -> int:
    async with async_session_factory() as s:
        proj = (await s.execute(select(Project).where(Project.slug == "workspace"))).scalar_one()
        a = Agent(name=nombre, model="claude-sonnet-5", description="d", body="cuerpo",
                  source_path=f"/tmp/{nombre}.md", body_hash="h", project_id=proj.id)
        s.add(a)
        await s.commit()
        return a.id


async def _runs(agent_id: int, estados: list[str], base: dt.datetime | None = None) -> None:
    base = base or dt.datetime.now(dt.UTC)
    async with async_session_factory() as s:
        for i, st in enumerate(estados):
            s.add(Run(agent_id=agent_id, source="api", prompt=f"p{i}", status=st,
                      started_at=base + dt.timedelta(seconds=i)))
        await s.commit()


async def _limpiar(agent_id: int) -> None:
    async with async_session_factory() as s:
        a = await s.get(Agent, agent_id)
        if a:
            await s.delete(a)
        await s.commit()


@pytest.mark.asyncio
async def test_interrupted_runs_do_not_count_as_agent_activity(tmp_path, monkeypatch):
    from core.improvements.trigger import is_due

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()
    aid = await _agente("impr-interrupted")
    try:
        # Doce cortes de luz. Ninguno dice nada del agente.
        await _runs(aid, ["interrupted"] * 12)
        assert await is_due(aid) is False, (
            "un reinicio de la máquina no puede disparar una reflexión"
        )
    finally:
        await _limpiar(aid)


@pytest.mark.asyncio
async def test_three_interrupted_is_not_three_failures(tmp_path, monkeypatch):
    from core.improvements.trigger import is_due

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()
    aid = await _agente("impr-tres-cortes")
    try:
        await _runs(aid, ["interrupted", "interrupted", "interrupted"])
        assert await is_due(aid) is False
    finally:
        await _limpiar(aid)


@pytest.mark.asyncio
async def test_three_real_failures_still_trigger(tmp_path, monkeypatch):
    from core.improvements.trigger import is_due

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()
    aid = await _agente("impr-tres-fallos")
    try:
        await _runs(aid, ["failed", "failed", "failed"])
        assert await is_due(aid) is True
    finally:
        await _limpiar(aid)


@pytest.mark.asyncio
async def test_a_rejected_proposal_does_not_reflect_on_the_next_run(tmp_path, monkeypatch):
    from core.improvements.trigger import RUNS_BETWEEN_REFLECTIONS, is_due

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()
    aid = await _agente("impr-rechazada")
    try:
        base = dt.datetime.now(dt.UTC) - dt.timedelta(hours=2)
        await _runs(aid, ["completed"] * RUNS_BETWEEN_REFLECTIONS, base=base)
        assert await is_due(aid) is True, "con 10 corridas y sin propuestas, toca"

        # Se propuso y el humano la rechazó.
        async with async_session_factory() as s:
            s.add(Improvement(agent_id=aid, proposed_diff_md="d", rationale="r",
                              status="rejected",
                              created_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)))
            await s.commit()

        # Una corrida más NO debe alcanzar.
        await _runs(aid, ["completed"])
        assert await is_due(aid) is False, (
            "al rechazar una propuesta salía otra reflexión en el mensaje "
            "siguiente: cuesta plata y molesta"
        )

        # Diez más sí.
        await _runs(aid, ["completed"] * RUNS_BETWEEN_REFLECTIONS)
        assert await is_due(aid) is True
    finally:
        await _limpiar(aid)


@pytest.mark.asyncio
async def test_an_open_proposal_blocks_another(tmp_path, monkeypatch):
    from core.improvements.trigger import RUNS_BETWEEN_REFLECTIONS, is_due

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()
    aid = await _agente("impr-abierta")
    try:
        await _runs(aid, ["completed"] * (RUNS_BETWEEN_REFLECTIONS + 5))
        async with async_session_factory() as s:
            s.add(Improvement(agent_id=aid, proposed_diff_md="d", rationale="r",
                              status="proposed"))
            await s.commit()
        assert await is_due(aid) is False, "no encimamos propuestas sin decidir"
    finally:
        await _limpiar(aid)


@pytest.mark.asyncio
async def test_the_reflector_ignores_non_agent_runs(tmp_path, monkeypatch):
    """Si sólo hay cortes de luz, no hay nada que reflexionar."""
    from core.improvements.reflector import propose_improvement

    monkeypatch.setenv("RUGOL_DATA_DIR", str(tmp_path))
    await init_db()
    aid = await _agente("impr-reflector")
    try:
        await _runs(aid, ["interrupted", "queued", "cancelled"])
        assert await propose_improvement(aid, tmp_path) is None
    finally:
        await _limpiar(aid)
