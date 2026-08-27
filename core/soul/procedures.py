"""Qué métodos se le ofrecen al dispatcher — y cuáles dejan de ofrecerse.

Soul-4 le dio a los agentes la capacidad de compilar un método después de
resolver algo con deliberación. Lo que no le dio fue un freno, y era un hueco
conocido: nada impedía acumular métodos mediocres, y un catálogo lleno de
métodos vagos es peor que un catálogo vacío. El dispatcher los toma por buenos y
manda a un modelo barato trabajo que había que pensar.

Este módulo es el freno, y la forma que toma es conductual: **extinción**. Un
método que se aplica y funciona se sigue ofreciendo. Uno que se aplica y las
corridas fallan deja de ofrecerse — sin borrarlo.

Tres decisiones que importan:

**No se borra nada.** Un método retirado sigue en la libreta del agente: se deja
de ofrecer al dispatcher, nada más. Borrar memoria de un agente por una
estadística es irreversible, y la estadística puede estar midiendo otra cosa (un
mal día de la API, un archivo que no estaba).

**Hace falta muestra.** Con menos de `_MIN_MUESTRA` aplicaciones no se retira
nada. Un método nuevo tiene derecho a fallar una vez sin morir por eso; si no,
lo único que sobrevive es lo que tuvo suerte al principio.

**El orden también es información.** Lo más usado va primero: cuando hay que
recortar el catálogo, lo que se cae es lo que nadie usa, no lo que quedó último
alfabéticamente.
"""
from __future__ import annotations

import logging

from sqlalchemy import case, func, select

from core.db import async_session_factory
from core.db.models import Agent, Run
from core.memory.store import list_procedures

logger = logging.getLogger(__name__)

# Aplicaciones mínimas antes de juzgar un método. Debajo de esto, se ofrece.
_MIN_MUESTRA = 4
# Si de las aplicadas fallaron más que esta proporción, se retira.
_MAX_FRACASO = 0.5
# Tope de lo que viaja al clasificador. Más que esto es prompt caro y una
# decisión peor: con cuarenta opciones, "el que más se parece" deja de
# significar algo.
_TOPE = 20


async def _track_record(agent_name: str) -> dict[str, tuple[int, int]]:
    """Por método: (aplicaciones, fallos). Una sola consulta."""
    async with async_session_factory() as session:
        agente = (await session.execute(
            select(Agent).where(Agent.name == agent_name)
        )).scalar_one_or_none()
        if agente is None:
            return {}
        filas = (await session.execute(
            select(
                Run.procedure,
                func.count(Run.id),
                func.sum(case((Run.status == "failed", 1), else_=0)),
            )
            .where(Run.agent_id == agente.id)
            .where(Run.procedure.is_not(None))
            .group_by(Run.procedure)
        )).all()
    return {p: (int(total or 0), int(fallos or 0)) for p, total, fallos in filas}


async def catalogue_for(agent_name: str) -> str:
    """El catálogo que ve el dispatcher: nombre y para qué sirve.

    Sin los pasos a propósito — el clasificador sólo decide SI hay método; los
    pasos los lee después quien ejecuta. Mandarlos acá es pagar tokens por nada.
    """
    procs = list_procedures(agent_name)
    if not procs:
        return ""
    try:
        historial = await _track_record(agent_name)
    except Exception:
        # Si la consulta falla, se ofrece todo: quedarse sin métodos por un
        # problema de base sería perder la capacidad entera por un rasguño.
        logger.exception("no pude leer el historial de métodos de %s", agent_name)
        historial = {}

    vivos: list[tuple[int, str]] = []
    for m in procs:
        aplicadas, fallos = historial.get(m.name, (0, 0))
        if aplicadas >= _MIN_MUESTRA and fallos / aplicadas > _MAX_FRACASO:
            logger.info(
                "soul-4: método %r de %s retirado del catálogo (%d/%d fallaron)",
                m.name, agent_name, fallos, aplicadas,
            )
            continue
        vivos.append((aplicadas, f"- {m.name}: {m.description}"))

    vivos.sort(key=lambda par: -par[0])
    return "\n".join(linea for _, linea in vivos[:_TOPE])


async def count_for(agent_name: str) -> int:
    """Cuántos métodos tiene compilados. Lo usa el compilador para saber si
    está en el tope y le toca reemplazar en vez de agregar."""
    return len(list_procedures(agent_name))
