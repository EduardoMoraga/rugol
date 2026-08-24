"""Decide whether an agent is due for a self-improvement reflection."""
from __future__ import annotations

from sqlalchemy import desc, func, select

from core.db import async_session_factory
from core.db.models import Improvement, Run

# Cada cuántas corridas reales corresponde una reflexión.
RUNS_BETWEEN_REFLECTIONS = 10


async def is_due(agent_id: int) -> bool:
    """¿Toca reflexionar? Sí si las últimas 3 corridas fallaron, o si pasaron
    RUNS_BETWEEN_REFLECTIONS corridas desde la última propuesta.

    Dos correcciones sobre la versión anterior:

    · Sólo se cuentan corridas `completed` o `failed`. Una `interrupted` es un
      corte de la máquina y una `queued` nunca corrió: contarlas hacía que un
      reinicio pareciera actividad del agente, y peor, tres cortes seguidos casi
      disparaban una reflexión sobre un problema que no era del prompt.

    · Se cuentan las corridas DESDE la última propuesta, no las totales. Antes
      la condición era `len(últimas 10) >= 10`, que es verdadera para siempre en
      cuanto el agente tiene 10 corridas: al rechazar una propuesta, la
      siguiente reflexión salía en el mensaje siguiente. Cuesta plata y molesta.
    """
    async with async_session_factory() as session:
        reales = (
            select(Run)
            .where(Run.agent_id == agent_id)
            .where(Run.status.in_(("completed", "failed")))
            .order_by(desc(Run.id))
        )
        last = (await session.execute(reales.limit(RUNS_BETWEEN_REFLECTIONS))).scalars().all()
        if not last:
            return False

        last_three = last[:3]
        if len(last_three) == 3 and all(r.status == "failed" for r in last_three):
            return True

        # Una propuesta abierta espera decisión humana: no encimamos otra.
        open_proposal = (await session.execute(
            select(Improvement).where(
                Improvement.agent_id == agent_id, Improvement.status == "proposed"
            ).limit(1)
        )).scalar_one_or_none()
        if open_proposal is not None:
            return False

        # Corridas desde la última propuesta (aprobada o rechazada).
        ultima = (await session.execute(
            select(Improvement)
            .where(Improvement.agent_id == agent_id)
            .order_by(desc(Improvement.id))
            .limit(1)
        )).scalar_one_or_none()
        if ultima is None:
            return len(last) >= RUNS_BETWEEN_REFLECTIONS

        desde = (await session.execute(
            select(func.count(Run.id))
            .where(Run.agent_id == agent_id)
            .where(Run.status.in_(("completed", "failed")))
            .where(Run.started_at > ultima.created_at)
        )).scalar_one() or 0
        return desde >= RUNS_BETWEEN_REFLECTIONS
